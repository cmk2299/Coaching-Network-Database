#!/usr/bin/env python3
"""Render a project directive markdown file to a SPORTFIVE-styled HTML page.

Use case: stakeholder-facing roadmap/sprint documents need to be deployable
alongside the dashboards without rebuilding the whole index. Output sits at
output/{slug}.html (default: roadmap.html).

Usage:
  python3 execution/render_directive_to_html.py \
      --source directives/DIRECTIVE_2026-05-22_pending_sprints.md \
      --output output/roadmap.html \
      --title "Sprint-Roadmap 2026-05-22"
"""
import argparse
import re
import sys
from datetime import datetime
from html import escape
from pathlib import Path


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Coach Network Explorer</title>
<meta name="robots" content="noindex">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{{
  --bg:#0a0a0e;--surface-1:#111318;--surface-2:#1a1d24;
  --border:rgba(255,255,255,.08);--border-h:rgba(255,255,255,.16);
  --accent:#F40009;--text:#d4d4d8;--text-2:#8b8d97;--text-3:#7c7e88;
  --good:#34C23A;--warn:#f39c12;
  --font-sans:'IBM Plex Sans',system-ui,sans-serif;
  --font-display:'Space Grotesk','IBM Plex Sans',sans-serif;
  --font-mono:'JetBrains Mono',ui-monospace,Menlo,monospace;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
html{{font-size:15px}}
body{{
  background:var(--bg);color:var(--text);font-family:var(--font-sans);
  -webkit-font-smoothing:antialiased;line-height:1.55;
}}
.hdr{{
  padding:28px 0;border-bottom:1px solid var(--border);margin:0 40px;
}}
.hdr-inner{{
  display:flex;align-items:baseline;justify-content:space-between;gap:24px;
}}
.hdr h1{{
  font-family:var(--font-display);font-size:17px;font-weight:600;color:#fff;
  letter-spacing:-.3px;
}}
.hdr h1 b{{color:var(--accent);font-weight:700}}
.hdr-right{{font-size:12px;color:var(--text-3);text-align:right;line-height:1.5}}
.hdr-right a{{color:var(--text-2);text-decoration:none;border-bottom:1px solid var(--border);padding-bottom:1px}}
.hdr-right a:hover{{color:var(--accent);border-color:var(--accent)}}

main{{
  max-width:920px;margin:0 auto;padding:48px 40px 96px;
}}
h1.title{{
  font-family:var(--font-display);font-size:32px;font-weight:700;
  letter-spacing:-.5px;color:#fff;margin-bottom:6px;
}}
.lead{{
  font-size:13px;color:var(--text-3);margin-bottom:40px;
}}
h2{{
  font-family:var(--font-display);font-size:22px;font-weight:600;color:#fff;
  margin:48px 0 16px;letter-spacing:-.3px;
  padding-bottom:8px;border-bottom:1px solid var(--border);
}}
h3{{
  font-family:var(--font-display);font-size:17px;font-weight:600;color:#fff;
  margin:28px 0 12px;letter-spacing:-.2px;
}}
h4{{
  font-family:var(--font-sans);font-size:14px;font-weight:600;
  color:var(--text);margin:20px 0 8px;
  text-transform:uppercase;letter-spacing:.04em;
}}
p{{margin:0 0 14px;font-size:14.5px;color:var(--text);}}
ul,ol{{margin:0 0 16px 22px;padding:0}}
li{{margin-bottom:6px;font-size:14px;color:var(--text)}}
strong{{color:#fff;font-weight:600}}
em{{font-style:italic;color:var(--text-2)}}
code{{
  font-family:var(--font-mono);font-size:12.5px;
  background:var(--surface-2);padding:1.5px 6px;border-radius:3px;
  color:#fff;border:1px solid var(--border);
}}
pre{{
  font-family:var(--font-mono);font-size:12px;line-height:1.55;
  background:var(--surface-1);padding:16px 18px;border-radius:6px;
  border:1px solid var(--border);overflow-x:auto;margin:0 0 16px;
}}
pre code{{background:transparent;border:none;padding:0;color:#e8e9ed}}

table{{
  width:100%;border-collapse:collapse;margin:0 0 20px;font-size:13px;
}}
table th,table td{{
  padding:9px 14px;text-align:left;
  border-bottom:1px solid var(--border);
}}
table th{{
  font-family:var(--font-display);font-weight:600;color:#fff;
  font-size:11px;text-transform:uppercase;letter-spacing:.05em;
  background:var(--surface-1);
}}
table tr:hover td{{background:var(--surface-1)}}
table code{{font-size:11.5px}}

hr{{
  border:none;border-top:1px solid var(--border);
  margin:36px 0;
}}
a{{color:#fff;text-decoration:underline;text-decoration-color:var(--border);}}
a:hover{{color:var(--accent);text-decoration-color:var(--accent)}}

blockquote{{
  border-left:3px solid var(--accent);
  padding:6px 16px;margin:12px 0 16px;
  color:var(--text-2);font-size:14px;
  background:rgba(244,0,9,.04);
}}

.toc{{
  background:var(--surface-1);border:1px solid var(--border);
  padding:18px 22px;border-radius:6px;margin-bottom:32px;
}}
.toc h4{{margin-top:0;color:var(--text-2)}}
.toc ul{{margin:0;list-style:none;padding:0}}
.toc li{{margin-bottom:4px;font-size:13px}}
.toc a{{color:var(--text);text-decoration:none;}}
.toc a:hover{{color:var(--accent)}}

.priority-P0{{color:var(--accent);font-weight:600}}
.priority-P1{{color:var(--warn);font-weight:600}}
.priority-P2{{color:var(--text-2)}}
</style>
</head>
<body>
<header class="hdr">
  <div class="hdr-inner">
    <h1><b>p5</b> Coach Network Explorer</h1>
    <div class="hdr-right">
      <a href="/">← Trainer-Netzwerke</a>
      &nbsp;·&nbsp;
      <a href="/clubs.html">Vereine →</a>
    </div>
  </div>
</header>
<main>
  <h1 class="title">{title}</h1>
  <div class="lead">Quelle: <code>{source_path}</code> · Rendered {now}</div>
  {body}
</main>
</body>
</html>
"""


def render_inline(text: str) -> str:
    """Inline markdown → HTML: code, bold, italics, links."""
    out = escape(text)
    # `code`
    out = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", out)
    # **bold**
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    # *italic* (single * not part of **)
    out = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", out)
    # [text](url) links
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', out)
    # priority badges P0/P1/P2 — colored
    out = re.sub(r"\b(P0)\b", r'<span class="priority-P0">\1</span>', out)
    out = re.sub(r"\b(P1)\b", r'<span class="priority-P1">\1</span>', out)
    out = re.sub(r"\b(P2)\b", r'<span class="priority-P2">\1</span>', out)
    return out


def md_to_html(md: str) -> str:
    """Minimal but sufficient markdown renderer for project directives.

    Supports: h1-h4, paragraphs, ul/ol, code blocks (```), inline `code`,
    bold/italic, [links](url), tables (| ... |), blockquotes (>), hr (---).
    """
    lines = md.split("\n")
    out = []
    i = 0

    def close_paragraph(buffer):
        if buffer:
            joined = " ".join(buffer).strip()
            if joined:
                out.append(f"<p>{render_inline(joined)}</p>")
            buffer.clear()

    paragraph: list[str] = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Fenced code block
        if stripped.startswith("```"):
            close_paragraph(paragraph)
            lang = stripped[3:].strip()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            code_html = escape("\n".join(code_lines))
            out.append(f'<pre><code class="lang-{escape(lang)}">{code_html}</code></pre>')
            continue

        # HR
        if re.match(r"^-{3,}$", stripped):
            close_paragraph(paragraph)
            out.append("<hr>")
            i += 1
            continue

        # Headings
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            close_paragraph(paragraph)
            level = len(m.group(1))
            text = m.group(2).strip()
            # H1 from MD = "title" — we already render document-level title separately,
            # so promote H1→H2 visually
            level_html = max(2, level) if level == 1 else level
            anchor = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
            out.append(f'<h{level_html} id="{anchor}">{render_inline(text)}</h{level_html}>')
            i += 1
            continue

        # Blockquote
        if stripped.startswith("> "):
            close_paragraph(paragraph)
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith("> "):
                quote_lines.append(lines[i].strip()[2:])
                i += 1
            out.append(f"<blockquote>{render_inline(' '.join(quote_lines))}</blockquote>")
            continue

        # Tables
        if "|" in stripped and i + 1 < len(lines) and re.match(r"^\s*\|?[\s\-:|]+\|?\s*$", lines[i + 1]):
            close_paragraph(paragraph)
            header_cells = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2  # skip separator
            rows = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells)
                i += 1
            thead = "<tr>" + "".join(f"<th>{render_inline(c)}</th>" for c in header_cells) + "</tr>"
            tbody = "".join(
                "<tr>" + "".join(f"<td>{render_inline(c)}</td>" for c in row) + "</tr>"
                for row in rows
            )
            out.append(f"<table><thead>{thead}</thead><tbody>{tbody}</tbody></table>")
            continue

        # Unordered list
        if re.match(r"^[-*+]\s+", stripped):
            close_paragraph(paragraph)
            items = []
            while i < len(lines) and re.match(r"^[-*+]\s+", lines[i].strip()):
                item_text = re.sub(r"^[-*+]\s+", "", lines[i].strip())
                items.append(f"<li>{render_inline(item_text)}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue

        # Ordered list
        if re.match(r"^\d+\.\s+", stripped):
            close_paragraph(paragraph)
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                item_text = re.sub(r"^\d+\.\s+", "", lines[i].strip())
                items.append(f"<li>{render_inline(item_text)}</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue

        # Empty line → close paragraph
        if not stripped:
            close_paragraph(paragraph)
            i += 1
            continue

        # Default: accumulate into paragraph
        paragraph.append(stripped)
        i += 1

    close_paragraph(paragraph)
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, help="Path to markdown directive")
    ap.add_argument("--output", required=True, help="Path to output HTML")
    ap.add_argument("--title", default=None, help="Page title (default: parsed from H1)")
    args = ap.parse_args()

    src = Path(args.source)
    if not src.exists():
        print(f"✗ Source not found: {src}", file=sys.stderr)
        sys.exit(1)

    md = src.read_text(encoding="utf-8")

    # Extract title from first H1 if not given
    if args.title:
        title = args.title
    else:
        m = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
        title = m.group(1).strip() if m else src.stem.replace("_", " ").title()

    body_html = md_to_html(md)

    html = HTML_TEMPLATE.format(
        title=escape(title),
        source_path=escape(str(src)),
        now=datetime.now().strftime("%d.%m.%Y %H:%M"),
        body=body_html,
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"✓ Rendered: {out_path} ({out_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
