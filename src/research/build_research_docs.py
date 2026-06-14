#!/usr/bin/env python3
"""
Generate HTML preview/download pages for The Prescott Girls research docs.

Usage:
  cd path/to/research/markdown/source
  python3 build_research_docs.py

For every Markdown file in the current directory, this creates a matching
HTML file with the same basename. The PDF is assumed to have the same
basename and live in the same folder as the generated HTML page.

Example:
  The Prescott Girls - document1.md
  The Prescott Girls - document1.pdf
  -> The Prescott Girls - document1.html
"""

from __future__ import annotations

from pathlib import Path
import html
import re

SITE_NAME = "The Prescott Girls"
PRESS_RESOURCES_PATH = "../research.html"
OUTPUT_DIR = "../../research"

from urllib.parse import quote

SITE_BASE_URL = "https://www.theprescottgirls.com"


def remove_google_doc_images(markdown: str) -> str:
    """Remove Google Docs Markdown image embeds and base64 image references."""
    # Remove image embeds, including ![][image1], ![](path), and odd one-line variants.
    markdown = re.sub(
        r"^!\[[^\]]*\](?:\([^)]*\)|\[[^\]]*\]|.*)$",
        "",
        markdown,
        flags=re.MULTILINE,
    )

    # Remove huge reference-style base64 image definitions: [image1]: <data:image/png;base64,...>
    markdown = re.sub(
        r"^\[image\d+\]:\s*<data:image/[^>]+>\s*$",
        "",
        markdown,
        flags=re.MULTILINE,
    )

    # Remove any leftover ordinary image reference definitions.
    markdown = re.sub(
        r"^\[image\d+\]:\s*.*$",
        "",
        markdown,
        flags=re.MULTILINE,
    )

    markdown = re.sub(r"\\([\\`*_{}\[\]()#+\-.!])", r"\1", markdown)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip()


def strip_markdown_markup(text: str) -> str:
    text = re.sub(r"^[#\s]+", "", text).strip()
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    return text.strip()


def inline_markdown_to_html(text: str) -> str:
    """Convert a small subset of inline Markdown to HTML safely."""
    # Escape first so arbitrary HTML in the Markdown cannot pass through.
    text = html.escape(text, quote=False)

    # Convert Markdown links after escaping. Ordinary Markdown punctuation remains.
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>',
        text,
    )

    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)
    return text


def markdown_to_basic_html(markdown: str) -> str:
    """Small converter for the predictable Google Docs Markdown subset."""
    output: list[str] = []
    paragraph: list[str] = []
    in_ul = False
    in_ol = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            lines = [inline_markdown_to_html(p.strip()) for p in paragraph if p.strip()]
            if lines:
                output.append("<p>" + "<br>\n".join(lines) + "</p>")
            paragraph = []

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            output.append("</ul>")
            in_ul = False
        if in_ol:
            output.append("</ol>")
            in_ol = False

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()

        if not line.strip():
            flush_paragraph()
            close_lists()
            continue

        if re.fullmatch(r"---+", line.strip()):
            flush_paragraph()
            close_lists()
            output.append("<hr>")
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            flush_paragraph()
            close_lists()
            # Demote transcript headings by one level so the page has one visible H1.
            level = min(len(heading.group(1)) + 1, 6)
            heading_text = strip_markdown_markup(heading.group(2))
            output.append(f"<h{level}>{inline_markdown_to_html(heading_text)}</h{level}>")
            continue

        bullet = re.match(r"^[-*•]\s+(.*)$", line)
        if bullet:
            flush_paragraph()
            if in_ol:
                output.append("</ol>")
                in_ol = False
            if not in_ul:
                output.append("<ul>")
                in_ul = True
            output.append(f"<li>{inline_markdown_to_html(bullet.group(1).strip())}</li>")
            continue

        ordered = re.match(r"^\d+\.\s+(.*)$", line)
        if ordered:
            flush_paragraph()
            if in_ul:
                output.append("</ul>")
                in_ul = False
            if not in_ol:
                output.append("<ol>")
                in_ol = True
            output.append(f"<li>{inline_markdown_to_html(ordered.group(1).strip())}</li>")
            continue

        paragraph.append(line)

    flush_paragraph()
    close_lists()
    return "\n".join(output)


def title_has_resource_type(title: str) -> bool:
    title_lower = title.lower()
    return any(term in title_lower for term in [
        "press release",
        "press kit",
        "media kit",
        "media resources",
        "press resources",
        "study guide",
        "discussion questions",
        "teacher guide",
        "student guide",
        "overview",
        "guide",
    ])


def prettify_filename_title(stem: str) -> str:
    """Fallback title from filename, with common separators cleaned up."""
    title = re.sub(r"[_-]+", " ", stem).strip()
    title = re.sub(r"\s+", " ", title)
    return title or "Press Resource"


def title_from_markdown(markdown: str, basename: str) -> tuple[str, str]:
    lines = markdown.splitlines()
    headings: list[tuple[int, str]] = []

    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if match:
            level = len(match.group(1))
            text = strip_markdown_markup(match.group(2))

            # Ignore numbered section headings like "1. Leaving New Sharon".
            if re.match(r"^\d+[\.)]\s+", text):
                continue

            headings.append((level, text))

    h1 = next((text for level, text in headings if level == 1), "")
    h2 = next((text for level, text in headings if level == 2), "")

    generic_titles = {
        "the prescott girls",
        "press resource",
        "press resources",
        "study guide",
        "teacher guide",
        "teacher resources",
    }

    if h1 and h1.lower().strip() not in generic_titles:
        display_title = h1
    elif h2 and h2.lower().strip() not in generic_titles:
        display_title = h2
    elif h1:
        display_title = h1
    else:
        display_title = prettify_filename_title(basename)

    # Prefer filename fallback if the extracted title is too generic.
    if display_title.lower().strip() in {"press resource", "press resources"}:
        display_title = prettify_filename_title(basename)

    if title_has_resource_type(display_title):
        page_title = f"{display_title} | {SITE_NAME}"
    else:
        page_title = f"{display_title} Press Release | {SITE_NAME}"

    return display_title, page_title


def meta_description_for(display_title: str) -> str:
    title_lower = display_title.lower()
    if "press kit" in title_lower or "media kit" in title_lower:
        return f"Preview and download the {display_title} for {SITE_NAME}."
    if "press release" in title_lower:
        return f"Preview and download the {display_title} from {SITE_NAME} press resources."
    return f"Preview and download the {display_title} press resource from {SITE_NAME}."


def build_page(md_path: Path) -> Path:
    basename = md_path.stem
    pdf_name = basename + ".pdf"
    html_name = basename + ".html"
    canonical_url = f"{SITE_BASE_URL}/research/{quote(html_name)}"

    markdown = remove_google_doc_images(md_path.read_text(encoding="utf-8"))
    display_title, page_title = title_from_markdown(markdown, basename)
    transcript_html = markdown_to_basic_html(markdown)
    meta_description = meta_description_for(display_title)

    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(page_title)}</title>
  <meta name="description" content="{html.escape(meta_description)}">
  <link rel="canonical" href="{html.escape(canonical_url)}">
  
  <link rel="icon" type="image/png" sizes="16x16" href="../assets/favicon-16.png">
  <link rel="icon" type="image/png" sizes="32x32" href="../assets/favicon-32.png">
  <link rel="apple-touch-icon" href="../assets/apple-touch-icon.png">
  
  <style>
    body {{ margin: 0; font-family: Georgia, "Times New Roman", serif; background: #f7f3ea; color: #2d261f; line-height: 1.6; }}
    .page {{ max-width: 1100px; margin: 0 auto; padding: 32px 20px 56px; }}
    .back-link a {{ color: #244a4a; text-decoration: underline; }}
    h1 {{ font-size: clamp(2rem, 4vw, 3rem); line-height: 1.15; margin: 16px 0 8px; }}
    .subtitle {{ font-size: 1.15rem; margin: 0 0 24px; }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 14px; margin: 20px 0 28px; }}
    .button {{ display: inline-block; padding: 10px 16px; border-radius: 6px; background: #244a4a; color: #fff; text-decoration: none; font-family: Arial, sans-serif; font-size: 0.95rem; }}
    .pdf-viewer {{ background: #fff; border: 1px solid #d2c8b8; box-shadow: 0 2px 10px rgba(0,0,0,0.08); margin-bottom: 32px; }}
    .pdf-viewer object {{ width: 100%; height: 86vh; min-height: 640px; border: 0; display: block; }}
    .pdf-fallback {{ padding: 24px; }}
    details.transcript {{ background: #fffdf8; border: 1px solid #d2c8b8; border-radius: 8px; padding: 18px 22px; }}
    details.transcript summary {{ cursor: pointer; font-family: Arial, sans-serif; font-weight: bold; color: #244a4a; margin-bottom: 12px; }}
    .transcript-content {{ max-width: 760px; }}
    .transcript-note {{ color: #5f554a; font-style: italic; }}
    .transcript-content h2, .transcript-content h3, .transcript-content h4 {{ font-family: Arial, sans-serif; line-height: 1.25; margin-top: 1.5em; }}
    .transcript-content ul, .transcript-content ol {{ padding-left: 1.5em; }}
    footer {{ margin-top: 36px; font-size: 0.95rem; color: #5f554a; }}
    @media (max-width: 700px) {{ .pdf-viewer object {{ height: 75vh; min-height: 500px; }} }}
  </style>
</head>
<body>
  <main class="page">
    <header>
    
      <p class="back-link"><a href="{html.escape(PRESS_RESOURCES_PATH)}#research-papers">← Back to Research Documents</a></p>
        
      
      
      <h1>{html.escape(display_title)}</h1>
      <p class="subtitle">Preview the Research Document below, or download the PDF.</p>
      <div class="actions">
        <a class="button" href="{html.escape(pdf_name)}" download>Download PDF</a>
      </div>
    </header>

    <section class="pdf-viewer" aria-label="PDF preview">
      <object data="{html.escape(pdf_name)}" type="application/pdf">
        <div class="pdf-fallback">
          <p>Your browser does not support embedded PDFs.</p>
          <p><a href="{html.escape(pdf_name)}">Download the PDF instead.</a></p>
        </div>
      </object>
    </section>

    <details class="transcript">
      <summary>Accessible text version</summary>
      <div class="transcript-content">
        <p class="transcript-note">This text version is provided for accessibility and search.</p>
{transcript_html}
      </div>
    </details>

    <footer>From <em>The Prescott Girls</em> Research Documents.</footer>
  </main>
</body>
</html>
'''

    out_path = Path(OUTPUT_DIR) / html_name
    out_path.write_text(page, encoding="utf-8")
    return out_path


def main() -> None:
    md_files = sorted(Path.cwd().glob("*.md"))
    if not md_files:
        print("No .md files found in current directory.")
        return

    for md_path in md_files:
        out_path = build_page(md_path)
        print(f"Generated {out_path.name}")


if __name__ == "__main__":
    main()
