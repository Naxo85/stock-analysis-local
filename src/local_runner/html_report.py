"""Render validated stock analysis Markdown as a standalone HTML report."""

from __future__ import annotations

import re
from html import escape
from pathlib import Path

import markdown


_SECTION_HEADING_RE = re.compile(r"^\*\*([0-9]+\)\s+.+?)\*\*\s*$")


def render_analysis_html(markdown_text: str, *, symbol: str) -> str:
    """Return a readable, self-contained HTML document."""

    normalized = _promote_report_headings(markdown_text, symbol)
    safe_markdown = escape(normalized, quote=False)
    body = markdown.markdown(
        safe_markdown,
        extensions=("extra", "sane_lists"),
        output_format="html5",
    )
    title = f"{symbol.strip().upper()} stock analysis"

    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --page: #f3f5f7;
      --surface: #ffffff;
      --text: #1f2933;
      --muted: #5f6b76;
      --line: #d9e0e6;
      --accent: #126e5b;
      --accent-soft: #e7f3ef;
      --link: #175cd3;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--page);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
      font-size: 16px;
      line-height: 1.65;
      letter-spacing: 0;
    }}
    main {{
      width: min(920px, calc(100% - 32px));
      margin: 32px auto;
      padding: 38px 44px 48px;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 8px 28px rgba(31, 41, 51, 0.07);
    }}
    h1 {{
      margin: 0 0 18px;
      color: #102a25;
      font-size: 30px;
      line-height: 1.2;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 34px 0 14px;
      padding-bottom: 8px;
      border-bottom: 2px solid var(--accent-soft);
      color: #173d35;
      font-size: 20px;
      line-height: 1.35;
      letter-spacing: 0;
    }}
    p {{ margin: 0 0 14px; }}
    ul, ol {{ margin: 0 0 18px; padding-left: 26px; }}
    li {{ margin: 0 0 12px; }}
    strong {{ color: #102a25; }}
    a {{ color: var(--link); text-decoration-thickness: 1px; text-underline-offset: 2px; }}
    a:hover {{ text-decoration-thickness: 2px; }}
    code {{
      padding: 2px 5px;
      border-radius: 4px;
      background: #edf1f4;
      font-family: ui-monospace, "Cascadia Code", monospace;
      font-size: 0.92em;
    }}
    blockquote {{
      margin: 18px 0;
      padding: 12px 16px;
      border-left: 4px solid var(--accent);
      background: var(--accent-soft);
      color: #29443d;
    }}
    @media (max-width: 640px) {{
      body {{ font-size: 15px; }}
      main {{ width: 100%; margin: 0; padding: 24px 20px 36px; border: 0; border-radius: 0; }}
      h1 {{ font-size: 26px; }}
      h2 {{ font-size: 18px; }}
    }}
    @media print {{
      body {{ background: #fff; }}
      main {{ width: 100%; margin: 0; padding: 0; border: 0; box-shadow: none; }}
      a {{ color: inherit; }}
    }}
  </style>
</head>
<body>
  <main>
{body}
  </main>
</body>
</html>
"""


def write_analysis_html(markdown_text: str, output_path: Path, *, symbol: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_analysis_html(markdown_text, symbol=symbol),
        encoding="utf-8",
    )


def _promote_report_headings(markdown_text: str, symbol: str) -> str:
    lines = markdown_text.splitlines()
    first_content_seen = False
    normalized: list[str] = []
    expected_symbol = symbol.strip().upper()

    for line in lines:
        stripped = line.strip()

        if not first_content_seen and stripped:
            first_content_seen = True
            if stripped.upper() == expected_symbol:
                normalized.append(f"# {stripped}")
                continue

        section_match = _SECTION_HEADING_RE.match(stripped)
        if section_match:
            normalized.append(f"## {section_match.group(1)}")
            continue

        normalized.append(line)

    return "\n".join(normalized)
