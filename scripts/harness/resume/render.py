"""Render tailored-resume Markdown to a professionally-formatted PDF.

Uses WeasyPrint (HTML+CSS → PDF). Falls back to writing the .md next to
the .pdf if WeasyPrint is unavailable, so the pipeline never blocks.
"""
from __future__ import annotations
import re
from pathlib import Path


_CSS = """
@page { size: Letter; margin: 0.5in; }
body { font-family: 'Helvetica', 'Arial', sans-serif; font-size: 10pt; color: #111; line-height: 1.35; }
h1 { font-size: 20pt; margin: 0 0 2px 0; letter-spacing: 1px; text-align: center; }
h2 { font-size: 11pt; text-transform: uppercase; letter-spacing: 1.5px;
     border-bottom: 1px solid #333; padding-bottom: 2px; margin: 16px 0 6px 0; }
h3 { font-size: 10.5pt; margin: 10px 0 2px 0; }
p, li { font-size: 10pt; margin: 2px 0; }
ul { margin: 4px 0 6px 18px; padding: 0; }
.header-contact { text-align: center; color: #333; font-size: 9pt; margin-bottom: 6px; }
"""


def _md_to_html(md: str) -> str:
    # Very small, dependency-free Markdown → HTML for the subset we use.
    html_lines: list[str] = []
    in_list = False
    for raw in md.splitlines():
        line = raw.rstrip()
        if line.startswith("# "):
            html_lines.append(f"<h1>{_esc(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_list:
                html_lines.append("</ul>"); in_list = False
            html_lines.append(f"<h2>{_esc(line[3:])}</h2>")
        elif line.startswith("### "):
            if in_list:
                html_lines.append("</ul>"); in_list = False
            html_lines.append(f"<h3>{_esc(line[4:])}</h3>")
        elif line.startswith("- "):
            if not in_list:
                html_lines.append("<ul>"); in_list = True
            html_lines.append(f"<li>{_inline(line[2:])}</li>")
        elif not line.strip():
            if in_list:
                html_lines.append("</ul>"); in_list = False
            html_lines.append("")
        else:
            if in_list:
                html_lines.append("</ul>"); in_list = False
            cls = " class=\"header-contact\"" if any(
                s in line for s in ("@", "linkedin.com", "github.com", "+")
            ) else ""
            html_lines.append(f"<p{cls}>{_inline(line)}</p>")
    if in_list:
        html_lines.append("</ul>")
    body = "\n".join(html_lines)
    return f"<!doctype html><meta charset='utf-8'><style>{_CSS}</style><body>{body}</body>"


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _inline(s: str) -> str:
    s = _esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    return s


def render(markdown: str, out_pdf: Path) -> Path:
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    html = _md_to_html(markdown)
    try:
        from weasyprint import HTML  # imported lazily so missing dep never blocks tailor()
        HTML(string=html).write_pdf(str(out_pdf))
    except Exception as e:
        # Fallback: write both .md and .html next to the target
        md_path = out_pdf.with_suffix(".md")
        html_path = out_pdf.with_suffix(".html")
        md_path.write_text(markdown, encoding="utf-8")
        html_path.write_text(html, encoding="utf-8")
        # Return the html so the caller has something to upload.
        return html_path
    return out_pdf
