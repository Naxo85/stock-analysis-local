"""Run isolated, repeatable Codex model/effort comparisons for one ticker."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.common.analysis_validator import validate_markdown
from src.local_runner.codex_generator import generate_markdown_with_codex
from src.local_runner.codex_rate_limits import read_codex_rate_limits
from src.local_runner.html_report import write_analysis_html
from src.local_runner.run_one import _find_repo_root, _prepare


DEFAULT_CANDIDATES = (
    "gpt-5.6-terra:xhigh",
    "gpt-5.6-sol:medium",
)
ALLOWED_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class Candidate:
    model: str
    effort: str

    @classmethod
    def parse(cls, value: str) -> "Candidate":
        model, separator, effort = str(value or "").strip().rpartition(":")
        if not separator or not MODEL_RE.fullmatch(model):
            raise ValueError(
                f"invalid_candidate: expected MODEL:EFFORT, received {value!r}"
            )
        if effort not in ALLOWED_EFFORTS:
            allowed = ", ".join(sorted(ALLOWED_EFFORTS))
            raise ValueError(f"invalid_effort: {effort!r}; allowed: {allowed}")
        return cls(model=model, effort=effort)

    def to_dict(self) -> dict[str, str]:
        return {"model": self.model, "reasoning_effort": self.effort}


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = _find_repo_root(Path.cwd())
    symbol = args.ticker.strip().upper()
    candidates = _parse_candidates(args.candidate)

    if args.input_path:
        source_input = Path(args.input_path)
        if not source_input.is_absolute():
            source_input = repo_root / source_input
        source_input = source_input.resolve()
    else:
        source_input = repo_root / "output" / symbol / "codex_input.md"

    if not args.reuse_input and not args.input_path:
        prepare_status = _prepare(repo_root, symbol)
        if prepare_status != 0:
            raise RuntimeError(f"benchmark_prepare_failed: exit_code={prepare_status}")

    if not source_input.exists():
        raise RuntimeError(
            f"missing_benchmark_input: {source_input}; run without --reuse-input "
            "or prepare the ticker first"
        )

    run_dir = _create_run_dir(repo_root, args.output_root, symbol)
    frozen_input = run_dir / "input" / "codex_input.md"
    frozen_input.parent.mkdir(parents=True, exist_ok=True)
    if args.scenario_price is None:
        shutil.copy2(source_input, frozen_input)
    else:
        frozen_input.write_text(
            _build_price_invariance_input(
                source_input.read_text(encoding="utf-8"),
                price=args.scenario_price,
            ),
            encoding="utf-8",
        )
    source_input_hash = _sha256(source_input)
    input_hash = _sha256(frozen_input)

    _write_json(
        run_dir / "input" / "manifest.json",
        {
            "symbol": symbol,
            "created_at": _now_iso(),
            "source_path": str(source_input),
            "source_sha256": source_input_hash,
            "frozen_input_path": str(frozen_input),
            "sha256": input_hash,
            "reused_existing_input": bool(args.reuse_input),
            "scenario_price": args.scenario_price,
        },
    )

    shuffled = list(candidates)
    random.SystemRandom().shuffle(shuffled)
    identities: dict[str, dict[str, str]] = {}
    public_results: list[dict[str, Any]] = []
    failures = 0

    for index, candidate in enumerate(shuffled):
        label = chr(ord("A") + index)
        identities[label] = candidate.to_dict()
        candidate_dir = run_dir / f"candidate-{label.lower()}"
        candidate_dir.mkdir(parents=True, exist_ok=True)
        report_path = candidate_dir / "report.md"
        events_path = candidate_dir / "events.jsonl"

        quota_before = (
            read_codex_rate_limits(cwd=repo_root)
            if args.include_coarse_quota
            else None
        )
        started_at = _now_iso()
        started_perf = time.perf_counter()

        try:
            generation_started_perf = time.perf_counter()
            generation = generate_markdown_with_codex(
                input_path=frozen_input,
                output_path=report_path,
                cwd=repo_root,
                model=candidate.model,
                reasoning_effort=candidate.effort,
                event_log_path=events_path,
                benchmark_isolation=True,
            )
            generation_duration_seconds = round(
                time.perf_counter() - generation_started_perf,
                3,
            )
            if generation.usage is None:
                raise RuntimeError("codex_exec_missing_token_usage")
            quota_after = (
                read_codex_rate_limits(cwd=repo_root)
                if args.include_coarse_quota
                else None
            )
            report = report_path.read_text(encoding="utf-8")
            validation = validate_markdown(report)
            write_analysis_html(
                report,
                candidate_dir / "report.html",
                symbol=symbol,
            )
            result = {
                "label": label,
                "status": "ok",
                "started_at": started_at,
                "finished_at": _now_iso(),
                "duration_seconds": generation_duration_seconds,
                "total_elapsed_seconds": round(
                    time.perf_counter() - started_perf,
                    3,
                ),
                "frozen_input_sha256": input_hash,
                "usage": generation.usage,
                "coarse_quota_diagnostic": _coarse_quota_diagnostic(
                    quota_before,
                    quota_after,
                ),
                "quality_signals": _quality_signals(report, validation.to_dict()),
                "report_markdown": str(report_path.relative_to(run_dir)),
                "report_html": str(
                    (candidate_dir / "report.html").relative_to(run_dir)
                ),
                "events": str(events_path.relative_to(run_dir)),
            }
        except Exception as exc:
            failures += 1
            result = {
                "label": label,
                "status": "failed",
                "started_at": started_at,
                "finished_at": _now_iso(),
                "duration_seconds": round(time.perf_counter() - started_perf, 3),
                "frozen_input_sha256": input_hash,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "coarse_quota_diagnostic": _coarse_quota_diagnostic(
                    quota_before,
                    None,
                ),
            }

        public_results.append(result)
        _write_json(candidate_dir / "result.json", result)

    _write_json(
        run_dir / "comparison.json",
        {
            "symbol": symbol,
            "created_at": _now_iso(),
            "frozen_input_sha256": input_hash,
            "candidates": public_results,
            "pairwise": _pairwise_summary(public_results),
        },
    )
    _write_json(
        run_dir / "identity.json",
        {
            "warning": "Open only after completing the blind quality review.",
            "candidates": identities,
        },
    )
    (run_dir / "blind_review.md").write_text(
        _blind_review_markdown(symbol, public_results),
        encoding="utf-8",
    )

    print(f"Benchmark {'FAILED' if failures else 'OK'} for {symbol}: {run_dir}")
    print("Review blind_review.md before opening identity.json.")
    return 1 if failures else 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare Codex models and efforts using one frozen ticker input."
    )
    parser.add_argument("ticker", help="Ticker symbol, for example RKLB")
    parser.add_argument(
        "--candidate",
        action="append",
        help=(
            "Candidate as MODEL:EFFORT. Repeat for each candidate. Defaults to "
            "gpt-5.6-terra:xhigh and gpt-5.6-sol:medium."
        ),
    )
    parser.add_argument(
        "--reuse-input",
        action="store_true",
        help="Reuse output/TICKER/codex_input.md instead of preparing fresh input.",
    )
    parser.add_argument(
        "--input-path",
        help=(
            "Use this exact prepared input instead of output/TICKER/codex_input.md. "
            "May be absolute or relative to the repository."
        ),
    )
    parser.add_argument(
        "--scenario-price",
        type=float,
        help=(
            "Counterfactual current price for an entry-stability regression. "
            "All other inputs remain frozen."
        ),
    )
    parser.add_argument(
        "--output-root",
        default="benchmarks",
        help="Local result directory relative to the repository root.",
    )
    parser.add_argument(
        "--include-coarse-quota",
        action="store_true",
        help=(
            "Store integer account quota snapshots as a coarse diagnostic. "
            "They are not used to compare candidates."
        ),
    )
    args = parser.parse_args(argv)
    if args.input_path and args.reuse_input:
        parser.error("--input-path and --reuse-input are mutually exclusive")
    if args.scenario_price is not None and args.scenario_price <= 0:
        parser.error("--scenario-price must be positive")
    return args


def _build_price_invariance_input(source: str, *, price: float) -> str:
    price_text = f"{price:.2f}"
    override = f"""# ENTRY STABILITY REGRESSION OVERRIDE

This is a controlled counterfactual test, not a new market analysis.

- Treat the current/reference price as ${price_text} instead of the price in the frozen JSON.
- The price reached this level through ordinary intraday movement only.
- There are no new catalysts, news, analyst actions, support breaks, closes below support, or changes to options, gamma, technical levels, volatility, fundamentals, or narrative.
- Do not browse the web or introduce information newer than the frozen input.
- Keep every absolute support, resistance, wall, gap, stop, and target from the frozen input unchanged unless the original analysis rules independently require otherwise.
- Recalculate only percentages versus the counterfactual price and the Estado actual classification.
- The purpose is to test the rule that an existing valid entry must not be moved lower merely because price reaches it.

The override above has priority only for current price and scenario state. All other frozen input follows unchanged.

"""
    return override + source


def _coarse_quota_diagnostic(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if before is None and after is None:
        return None
    return {
        "warning": (
            "Integer account-wide percentages are rounded and can include "
            "other activity. Do not use them to rank candidates."
        ),
        "before": before,
        "after": after,
    }


def _parse_candidates(values: list[str] | None) -> tuple[Candidate, ...]:
    parsed = tuple(Candidate.parse(value) for value in (values or DEFAULT_CANDIDATES))
    if not parsed:
        raise ValueError("benchmark_requires_at_least_one_candidate")
    if len(set(parsed)) != len(parsed):
        raise ValueError("benchmark_candidates_must_be_unique")
    if len(parsed) > 26:
        raise ValueError("benchmark_supports_at_most_26_candidates")
    return parsed


def _create_run_dir(repo_root: Path, output_root: str, symbol: str) -> Path:
    relative_root = Path(output_root)
    if relative_root.is_absolute() or ".." in relative_root.parts:
        raise ValueError("output_root_must_be_a_safe_relative_path")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    run_id = f"{timestamp}-{uuid.uuid4().hex[:8]}"
    run_dir = repo_root / relative_root / symbol / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _quality_signals(report: str, validation: dict[str, Any]) -> dict[str, Any]:
    lines = report.splitlines()
    return {
        "validation": validation,
        "characters": len(report),
        "words": len(report.split()),
        "lines": len(lines),
        "headings": sum(1 for line in lines if line.lstrip().startswith("#")),
    }


def _pairwise_summary(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(results) != 2:
        return None

    left, right = results
    return {
        "labels": [left.get("label"), right.get("label")],
        "total_tokens_delta_a_minus_b": _metric_delta(
            left, right, ("usage", "total_tokens")
        ),
        "output_tokens_delta_a_minus_b": _metric_delta(
            left, right, ("usage", "output_tokens")
        ),
        "duration_seconds_delta_a_minus_b": _metric_delta(
            left, right, ("duration_seconds",)
        ),
    }


def _metric_delta(
    left: dict[str, Any], right: dict[str, Any], path: tuple[str, ...]
) -> float | int | None:
    left_value: Any = left
    right_value: Any = right
    for key in path:
        if not isinstance(left_value, dict) or not isinstance(right_value, dict):
            return None
        left_value = left_value.get(key)
        right_value = right_value.get(key)
    if not isinstance(left_value, (int, float)) or not isinstance(
        right_value, (int, float)
    ):
        return None
    return left_value - right_value


def _blind_review_markdown(
    symbol: str, results: list[dict[str, Any]]
) -> str:
    sections = [
        f"# Revisión ciega del benchmark de {symbol}",
        "",
        "No abras `identity.json` hasta terminar esta revisión.",
        "",
        "Valora cada informe de 1 a 5 en:",
        "",
        "- exactitud y ausencia de datos inventados;",
        "- coherencia entre tesis, riesgos, valoración y conclusión;",
        "- profundidad útil del razonamiento;",
        "- uso correcto de los datos disponibles;",
        "- claridad, concisión y utilidad operativa.",
        "",
    ]
    for result in results:
        label = result.get("label")
        if result.get("status") == "ok":
            sections.extend(
                (
                    f"## Informe {label}",
                    "",
                    f"- [Abrir HTML](candidate-{str(label).lower()}/report.html)",
                    f"- [Abrir Markdown](candidate-{str(label).lower()}/report.md)",
                    "- Puntuación personal: /5",
                    "- Observaciones:",
                    "",
                )
            )
        else:
            sections.extend((f"## Informe {label}", "", "Ejecución fallida.", ""))
    sections.extend(
        (
            "## Elección ciega",
            "",
            "- Informe preferido:",
            "- Motivo principal:",
            "",
            "Después abre `comparison.json` para el consumo y `identity.json` "
            "para revelar modelo y esfuerzo.",
            "",
        )
    )
    return "\n".join(sections)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    sys.exit(main())
