#!/usr/bin/env python3
"""
Generate HTML preview/download pages for The Prescott Girls teacher guides.

Usage:
  cd path/to/teachers
  python3 build_teacher_guides.py

For every Markdown file in the current directory, this creates a matching
HTML file with the same basename. The PDF is assumed to have the same
basename and live in the same folder.

Example:
  Study Guide - Beckie Prescott's Sampler.md
  Study Guide - Beckie Prescott's Sampler.pdf
  -> Study Guide - Beckie Prescott's Sampler.html
"""

from __future__ import annotations

from pathlib import Path
import html
import re

SITE_NAME = "The Prescott Girls"
TEACHER_RESOURCES_PATH = "../teachers.html"

from urllib.parse import quote, unquote

SITE_BASE_URL = "https://www.theprescottgirls.com"

OUTPUT_DIR = "../../teachers"
TEACHERS_INDEX_PATH = Path(OUTPUT_DIR).parent / "teachers.html"


def write_text_if_changed(path: str | Path, content: str) -> bool:
    """Write text only when the generated content has changed.

    Returns True if the file was written, False if the existing file was unchanged.
    """
    path = Path(path)

    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return False

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


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
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.strip()


def inline_markdown_to_html(text: str) -> str:
    text = html.escape(text, quote=False)

    # Convert simple Markdown links after escaping the line. The link text is already
    # escaped; escape href attributes with quote=True before inserting them.
    def replace_link(match: re.Match[str]) -> str:
        label = match.group(1)
        href = html.escape(match.group(2), quote=True)
        return f'<a href="{href}">{label}</a>'

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace_link, text)
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

        bullet = re.match(r"^•\s+(.*)$", line)
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


def normalize_title(title: str) -> str:
    """Normalize titles so generic H1 variants compare reliably."""
    title = strip_markdown_markup(title)
    title = title.replace("—", "-").replace("–", "-").replace("\\-", "-")
    title = re.sub(r"\s+", " ", title)
    title = re.sub(r"\s*-\s*", " - ", title)
    return title.lower().strip()


def title_has_resource_type(title: str) -> bool:
    title_lower = normalize_title(title)
    return any(term in title_lower for term in [
        "study guide",
        "discussion questions",
        "teacher guide",
        "student guide",
        "overview",
        "guide",
    ])


def display_h1_from_title(display_title: str) -> str:
    """Use a descriptive visible H1, adding 'Study Guide' only when needed."""
    if title_has_resource_type(display_title):
        return display_title
    return f"{display_title} Study Guide"


def title_from_markdown(markdown: str) -> tuple[str, str]:
    lines = markdown.splitlines()
    headings: list[tuple[int, str]] = []

    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if match:
            level = len(match.group(1))
            text = strip_markdown_markup(match.group(2))

            # Ignore numbered section headings like:
            # "1. Leaving New Sharon"
            if re.match(r"^\d+[\.)]\s+", text):
                continue

            headings.append((level, text))

    h1 = next((text for level, text in headings if level == 1), "")
    h2 = next((text for level, text in headings if level == 2), "")

    generic_titles = {
        "the prescott girls",
        "the prescott girls - study guide",
        "study guide",
        "teacher guide",
        "teacher resources",
    }

    # Most individual guide Markdown files use a generic H1 and a specific H2.
    # Promote the H2 for page titles, meta descriptions, and the visible page H1.
    if h1 and normalize_title(h1) in generic_titles and h2:
        display_title = h2
    elif h1:
        display_title = h1
    elif h2:
        display_title = h2
    else:
        display_title = "Teacher Resource"

    if title_has_resource_type(display_title):
        page_title = f"{display_title} | {SITE_NAME}"
    else:
        page_title = f"{display_title} Study Guide | {SITE_NAME}"

    if len(page_title) > 70 and page_title.endswith(f" | {SITE_NAME}"):
        page_title = page_title.removesuffix(f" | {SITE_NAME}")

    return display_title, page_title


def clean_meta_text(text: str) -> str:
    text = strip_markdown_markup(text)
    text = re.sub(r"^!\[[^\]]*\].*$", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -–—")


def first_useful_paragraph(markdown: str) -> str:
    """Find the first substantial paragraph for a more descriptive meta snippet."""
    blocks = re.split(r"\n\s*\n", markdown)
    for block in blocks:
        lines = []
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            if stripped.startswith("!"):
                continue
            if re.fullmatch(r"---+", stripped):
                continue
            if stripped.startswith("•"):
                continue
            lines.append(stripped)

        candidate = clean_meta_text(" ".join(lines))
        # Skip short labels such as "Artifact Overview".
        if len(candidate) >= 80:
            return candidate

    return ""


def truncate_meta(text: str, max_length: int = 155) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_length:
        return text

    truncated = text[: max_length + 1]
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return truncated.rstrip(".,;:") + "…"


def meta_description_from_markdown(display_title: str, markdown: str) -> str:
    intro = first_useful_paragraph(markdown)

    if intro:
        return truncate_meta(intro)

    if title_has_resource_type(display_title):
        return truncate_meta(
            f"Preview and download {display_title} from {SITE_NAME} teacher resources."
        )

    return truncate_meta(
        f"Preview and download the {display_title} study guide from {SITE_NAME} teacher resources."
    )


def load_teacher_anchors() -> dict[str, str]:
    """Read teachers.html and map guide HTML filenames to their download-item IDs.

    teachers.html remains the source of truth. Each generated guide page uses
    the ID from the matching guide link, so its back link can return visitors
    to the exact item in the Teacher Resources list.
    """
    if not TEACHERS_INDEX_PATH.exists():
        print(f"Warning: {TEACHERS_INDEX_PATH} not found; back links will use {TEACHER_RESOURCES_PATH}.")
        return {}

    teachers_html = TEACHERS_INDEX_PATH.read_text(encoding="utf-8")
    anchors: dict[str, str] = {}

    # Match each <div class="download-item..." id="..."> block and the first
    # guide HTML link inside it. Attribute order is allowed to vary.
    pattern = re.compile(
        r'<div\b'
        r'(?=[^>]*\bclass="[^"]*\bdownload-item\b[^"]*")'
        r'(?=[^>]*\bid="([^"]+)")'
        r'[^>]*>'
        r'[\s\S]*?'
        r'href="teachers/([^"#]+\.html)"',
        re.IGNORECASE,
    )

    for match in pattern.finditer(teachers_html):
        anchor = html.unescape(match.group(1)).strip()
        html_file = unquote(html.unescape(match.group(2))).strip()
        if anchor and html_file:
            anchors[html_file] = anchor

    return anchors


def build_page(md_path: Path, teacher_anchors: dict[str, str]) -> Path:
    basename = md_path.stem
    pdf_name = basename + ".pdf"
    html_name = basename + ".html"
    anchor = teacher_anchors.get(html_name)
    if anchor:
        teacher_resources_path = f"{TEACHER_RESOURCES_PATH}#{anchor}"
    else:
        teacher_resources_path = TEACHER_RESOURCES_PATH
        print(f"WARNING: No anchor found for {html_name}")
    
    canonical_url = (
    f"{SITE_BASE_URL}/teachers/{quote(html_name)}"
    )

    markdown = remove_google_doc_images(md_path.read_text(encoding="utf-8"))
    display_title, page_title = title_from_markdown(markdown)
    visible_h1 = display_h1_from_title(display_title)
    transcript_html = markdown_to_basic_html(markdown)
    meta_description = meta_description_from_markdown(display_title, markdown)

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
  
  <!-- Counter.dev -->
  <script src="https://cdn.counter.dev/script.js"
    data-id="800e0f07-e8c7-43c4-bdaf-617aab5c0504"
    data-utcoffset="-7"
    data-track-path="true"
    defer></script>
  
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
    
        <p class="back-link"><a href="{html.escape(teacher_resources_path)}">← Back to Teacher Resources</a></p>
      
<h1>{html.escape(visible_h1)}</h1>
      <p class="subtitle">Preview the printable study guide below, or download the PDF for classroom use.</p>
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
        <p class="transcript-note">This text version is provided for accessibility, classroom copying, and search.</p>
{transcript_html}
      </div>
    </details>
    
    <p class="back-link"><a href="{html.escape(teacher_resources_path)}">← Back to Teacher Resources</a></p>

    <footer>From <em>The Prescott Girls</em> Teacher Resources.</footer>
  </main>
</body>
</html>
'''

    out_path = Path(OUTPUT_DIR) / html_name
    changed = write_text_if_changed(out_path, page)
    return out_path, changed


def main() -> None:
    teacher_anchors = load_teacher_anchors()
    md_files = sorted(Path.cwd().glob("*.md"))
    if not md_files:
        print("No .md files found in current directory.")
        return

    updated = 0
    unchanged = 0

    for md_path in md_files:
        out_path, changed = build_page(md_path, teacher_anchors)
        if changed:
            updated += 1
            print(f"Updated   {out_path.name}")
        else:
            unchanged += 1
            print(f"Unchanged {out_path.name}")

    print()
    print(f"Teacher guides updated:   {updated}")
    print(f"Teacher guides unchanged: {unchanged}")


if __name__ == "__main__":
    main()
