"""Safely push one local Apps Script file with clasp.

The local apps_script directory can contain draft or helper files that should
not be pushed blindly. This command pulls the remote project twice, replaces one
file in one copy, verifies that the only remote diff is that file, and then
optionally runs `clasp push --force` from the temporary copy.
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_LOCAL_FILE = "apps_script/update_targets_and_notes.gs"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = _find_repo_root(Path.cwd())
    local_file = (repo_root / args.local_file).resolve()

    _assert_inside(repo_root, local_file)

    if not local_file.exists():
        raise RuntimeError(f"local_file_not_found: {local_file}")

    remote_name = args.remote_name or _default_remote_name(local_file)
    if not remote_name or "/" in remote_name or "\\" in remote_name:
        raise RuntimeError(f"invalid_remote_name: {remote_name}")

    clasp_json = repo_root / "apps_script" / ".clasp.json"
    if not clasp_json.exists():
        raise RuntimeError(f"missing_clasp_json: {clasp_json}")

    clasp_command = _resolve_command(args.clasp_command)
    temp_root = (
        repo_root
        / ".tmp_apps_script_push"
        / datetime.now().strftime("%Y%m%d-%H%M%S")
    ).resolve()
    work_dir = temp_root / "work"
    original_dir = temp_root / "original"

    _assert_inside(repo_root, temp_root)

    try:
        for directory in (work_dir, original_dir):
            directory.mkdir(parents=True, exist_ok=False)
            shutil.copy2(clasp_json, directory / ".clasp.json")
            _run([clasp_command, "pull"], cwd=directory)

        destination = work_dir / remote_name
        shutil.copy2(local_file, destination)

        if destination.suffix == ".js":
            node_command = shutil.which("node")
            if node_command:
                _run([node_command, "--check", str(destination)], cwd=repo_root)
            else:
                print("WARN node_not_found: skipping syntax check")

        changed_files = _changed_files(original_dir, work_dir)
        if changed_files != [remote_name]:
            raise RuntimeError(
                "unexpected_remote_diff: "
                + ", ".join(changed_files or ["<none>"])
                + f" (expected only {remote_name})"
            )

        print(f"OK diff check: only {remote_name} changes")

        if args.execute_push:
            _run([clasp_command, "push", "--force"], cwd=work_dir)
            print(f"OK pushed: {remote_name}")
        else:
            print("DRY RUN: add --execute-push to upload this change")
            print(f"TEMP: {work_dir}")

        return 0
    finally:
        if args.keep_temp:
            print(f"Keeping temp dir: {temp_root}")
        else:
            shutil.rmtree(temp_root, ignore_errors=True)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely push one local Apps Script file through clasp."
    )
    parser.add_argument(
        "local_file",
        nargs="?",
        default=DEFAULT_LOCAL_FILE,
        help=f"Local file to push. Default: {DEFAULT_LOCAL_FILE}",
    )
    parser.add_argument(
        "--remote-name",
        help=(
            "Remote Apps Script filename. Defaults to the local basename with "
            ".gs converted to .js."
        ),
    )
    parser.add_argument(
        "--clasp-command",
        default="clasp",
        help="clasp executable or .cmd path. Default: clasp",
    )
    parser.add_argument(
        "--execute-push",
        action="store_true",
        help="Actually run clasp push --force after the safety checks.",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep the temporary pulled project copies for inspection.",
    )
    return parser.parse_args(argv)


def _default_remote_name(local_file: Path) -> str:
    if local_file.suffix == ".gs":
        return local_file.with_suffix(".js").name
    return local_file.name


def _resolve_command(command: str) -> str:
    if any(sep in command for sep in ("/", "\\")):
        path = Path(command).expanduser()
        if not path.exists():
            raise RuntimeError(f"command_not_found: {command}")
        return str(path)

    found = shutil.which(command)
    if not found:
        raise RuntimeError(f"command_not_found_on_path: {command}")
    return found


def _changed_files(original_dir: Path, work_dir: Path) -> list[str]:
    original_files = _relative_files(original_dir)
    work_files = _relative_files(work_dir)
    all_files = sorted(original_files | work_files)
    changed: list[str] = []

    for relative in all_files:
        if relative == ".clasp.json":
            continue

        left = original_dir / relative
        right = work_dir / relative

        if not left.exists() or not right.exists():
            changed.append(relative)
            continue

        if not filecmp.cmp(left, right, shallow=False):
            changed.append(relative)

    return changed


def _relative_files(directory: Path) -> set[str]:
    return {
        str(path.relative_to(directory)).replace("\\", "/")
        for path in directory.rglob("*")
        if path.is_file()
    }


def _run(command: list[str], *, cwd: Path) -> None:
    print(f"> {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()

    for candidate in (current, *current.parents):
        if (candidate / "AGENTS.md").exists() and (candidate / "src").exists():
            return candidate

    raise RuntimeError(f"repo_root_not_found: {start}")


def _assert_inside(root: Path, target: Path) -> None:
    root = root.resolve()
    target = target.resolve()

    try:
        target.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"path_outside_repo: {target}") from exc


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI should print concise failures.
        print(f"FAILED push_apps_script_file: {exc}", file=sys.stderr)
        raise SystemExit(1)
