#!/usr/bin/env python3
"""
Generate HTML preview/download pages for The Prescott Girls research documents.

Directory layout expected when this script runs:

  research-source/
    build_research_docs.py
    research-metadata.txt
    incoming/
      New Paper.md
      New Paper.pdf
    Existing Paper.md
    ...

  public/research/                 (configured by OUTPUT_DIR)
    Existing Paper.pdf
    Existing Paper.html
    ...

Workflow:
  1. Load and validate research-metadata.txt.
  2. Validate every installed Markdown document and every incoming Markdown/PDF pair.
  3. Refuse to publish if metadata, a matching file, or a required field is missing.
  4. Move validated incoming Markdown files into the source directory and PDFs into
     the public research directory.
  5. Rebuild HTML pages for every installed Markdown document.

Metadata format:

  [DOCUMENT]
  file=The Schoolgirl Samplers in the Ziploc Bag.md
  page_intro=A visible introduction explaining why the document matters.
  description=One distinctive, page-specific search description.
  keywords=schoolgirl samplers;Pownalborough Court House;Betsy Ross

Keywords are separated with semicolons. Every document requires all four fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
import html
import json
import re
import shutil


# -----------------------------------------------------------------------------
# Site configuration
# -----------------------------------------------------------------------------

SITE_NAME = "The Prescott Girls"
SITE_BASE_URL = "https://www.theprescottgirls.com"
AUTHOR_NAME = "Aric Wilmunder"
PUBLISHER_NAME = "A Well-Regulated Press"

PRESS_RESOURCES_PATH = "../research.html"
OUTPUT_DIR = Path("../../research")
INCOMING_DIR = Path("incoming")
METADATA_FILE = Path("research-metadata.txt")

PDF_WARNING_SIZE_MB = 5
DESCRIPTION_RECOMMENDED_MIN = 120
DESCRIPTION_RECOMMENDED_MAX = 220
IGNORED_INCOMING_FILES = {".DS_Store", ".gitkeep"}


# -----------------------------------------------------------------------------
# Data structures
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class DocumentMetadata:
    """Validated metadata for one Markdown research document."""

    file: str
    page_intro: str
    description: str
    keywords: tuple[str, ...]


# -----------------------------------------------------------------------------
# General helpers
# -----------------------------------------------------------------------------


def fail(errors: list[str], heading: str = "ERROR") -> None:
    """Print errors and stop without publishing anything."""
    print(heading)
    print("-" * len(heading))
    for error in errors:
        print(error)
    print()
    print("Nothing was published.")
    raise SystemExit(1)


def write_text_if_changed(path: str | Path, content: str) -> bool:
    """Write UTF-8 text only when content changed."""
    path = Path(path)

    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def format_file_size(size_bytes: int) -> str:
    """Return a readable file size."""
    size_mb = size_bytes / (1024 * 1024)
    if size_mb >= 1:
        return f"{size_mb:.1f} MB"
    return f"{size_bytes / 1024:.0f} KB"


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    """Ask a yes/no question, returning the default on Return."""
    suffix = "[Y/n]" if default else "[y/N]"

    while True:
        answer = input(f"{prompt} {suffix} ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please answer y or n.")


def normalized_filename(name: str) -> str:
    """Normalize a metadata filename for duplicate detection only."""
    return name.casefold()


# -----------------------------------------------------------------------------
# Metadata parsing and validation
# -----------------------------------------------------------------------------


def parse_metadata_file(path: Path = METADATA_FILE) -> tuple[dict[str, DocumentMetadata], list[str]]:
    """Parse research-metadata.txt and return entries plus nonfatal warnings.

    The parser intentionally supports a small, predictable control-file syntax:
      * comments beginning with #
      * repeated [DOCUMENT] sections
      * key=value fields
      * required page_intro and description fields
      * semicolon-separated keywords
    """
    if not path.exists():
        fail([
            f"Required metadata file not found: {path}",
            "Create research-metadata.txt before building research documents.",
        ])

    sections: list[tuple[int, dict[str, str]]] = []
    current: dict[str, str] | None = None
    current_line = 0
    errors: list[str] = []
    warnings: list[str] = []

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if line == "[DOCUMENT]":
            if current is not None:
                sections.append((current_line, current))
            current = {}
            current_line = line_number
            continue

        if line.startswith("[") and line.endswith("]"):
            errors.append(f"{path}:{line_number}: Unknown section {line!r}; expected [DOCUMENT].")
            continue

        if current is None:
            errors.append(f"{path}:{line_number}: Field appears before the first [DOCUMENT] section.")
            continue

        if "=" not in raw_line:
            errors.append(f"{path}:{line_number}: Expected key=value.")
            continue

        key, value = raw_line.split("=", 1)
        key = key.strip().lower()
        value = value.strip()

        if key not in {"file", "page_intro", "description", "keywords"}:
            errors.append(f"{path}:{line_number}: Unknown field {key!r}.")
            continue

        if key in current:
            errors.append(f"{path}:{line_number}: Duplicate field {key!r} in this [DOCUMENT] section.")
            continue

        current[key] = value

    if current is not None:
        sections.append((current_line, current))

    if not sections and not errors:
        errors.append(f"{path}: No [DOCUMENT] sections were found.")

    result: dict[str, DocumentMetadata] = {}
    seen_normalized: dict[str, str] = {}
    descriptions: dict[str, str] = {}

    for section_line, values in sections:
        missing = [
            field
            for field in ("file", "page_intro", "description", "keywords")
            if not values.get(field, "").strip()
        ]
        if missing:
            errors.append(
                f"{path}:{section_line}: Missing required field(s): {', '.join(missing)}."
            )
            continue

        filename = values["file"].strip()
        page_intro = re.sub(r"\s+", " ", values["page_intro"].strip())
        description = re.sub(r"\s+", " ", values["description"].strip())
        raw_keywords = [item.strip() for item in values["keywords"].split(";")]
        keywords = [item for item in raw_keywords if item]

        if Path(filename).name != filename:
            errors.append(
                f"{path}:{section_line}: file must be a filename only, not a path: {filename!r}."
            )

        if Path(filename).suffix.lower() != ".md":
            errors.append(f"{path}:{section_line}: file must end in .md: {filename!r}.")

        normalized = normalized_filename(filename)
        if normalized in seen_normalized:
            errors.append(
                f"{path}:{section_line}: Duplicate document entry for {filename!r}; "
                f"already used by {seen_normalized[normalized]!r}."
            )
        else:
            seen_normalized[normalized] = filename

        if not description.endswith(('.', '!', '?')):
            warnings.append(f"Description for {filename} does not end with punctuation.")

        length = len(description)
        if length < DESCRIPTION_RECOMMENDED_MIN or length > DESCRIPTION_RECOMMENDED_MAX:
            warnings.append(
                f"Description for {filename} is {length} characters; recommended range is "
                f"{DESCRIPTION_RECOMMENDED_MIN}-{DESCRIPTION_RECOMMENDED_MAX}."
            )

        description_key = description.casefold()
        if description_key in descriptions:
            errors.append(
                f"{path}:{section_line}: Description duplicates the description for "
                f"{descriptions[description_key]!r}."
            )
        else:
            descriptions[description_key] = filename

        if len(keywords) != len({keyword.casefold() for keyword in keywords}):
            errors.append(f"{path}:{section_line}: Duplicate keywords found for {filename}.")

        if not keywords:
            errors.append(f"{path}:{section_line}: At least one keyword is required for {filename}.")

        result[filename] = DocumentMetadata(
            file=filename,
            page_intro=page_intro,
            description=description,
            keywords=tuple(keywords),
        )

    if errors:
        fail(errors, heading="METADATA ERROR")

    return result, warnings


def print_metadata_warnings(warnings: list[str]) -> None:
    if not warnings:
        return

    print("Metadata warnings")
    print("-----------------")
    for warning in warnings:
        print(f"WARNING: {warning}")
    print()


def validate_metadata_coverage(
    metadata: dict[str, DocumentMetadata],
    installed_md_files: list[Path],
    incoming_md_files: list[Path],
) -> None:
    """Require one metadata entry for every installed or incoming Markdown file.

    Also reject metadata entries that do not correspond to either an installed
    document or a document currently waiting in incoming.
    """
    document_names = {path.name for path in installed_md_files}
    document_names.update(path.name for path in incoming_md_files)
    metadata_names = set(metadata)

    errors: list[str] = []

    for name in sorted(document_names - metadata_names, key=str.casefold):
        errors.extend([
            f"Missing metadata for: {name}",
            "Add:",
            "",
            "[DOCUMENT]",
            f"file={name}",
            "page_intro=",
            "description=",
            "keywords=",
            "",
        ])

    for name in sorted(metadata_names - document_names, key=str.casefold):
        errors.append(f"Metadata entry has no matching installed or incoming Markdown file: {name}")

    if errors:
        fail(errors, heading="METADATA COVERAGE ERROR")


# -----------------------------------------------------------------------------
# Incoming document validation and installation
# -----------------------------------------------------------------------------


def incoming_files() -> list[Path]:
    """Return non-ignored files currently waiting in incoming."""
    INCOMING_DIR.mkdir(exist_ok=True)
    return sorted(
        (
            path
            for path in INCOMING_DIR.iterdir()
            if path.is_file() and path.name not in IGNORED_INCOMING_FILES
        ),
        key=lambda path: path.name.casefold(),
    )


def validate_existing_documents(installed_md_files: list[Path]) -> None:
    """Require a corresponding public PDF for every installed Markdown file."""
    errors: list[str] = []

    for md_path in installed_md_files:
        pdf_path = OUTPUT_DIR / f"{md_path.stem}.pdf"
        if not pdf_path.exists():
            errors.append(f"Missing published PDF for installed Markdown file: {pdf_path}")

    if errors:
        fail(errors, heading="EXISTING DOCUMENT ERROR")


def validate_incoming(
    metadata: dict[str, DocumentMetadata],
    files: list[Path],
) -> list[tuple[Path, Path]]:
    """Validate complete incoming Markdown/PDF pairs before moving anything."""
    if not files:
        return []

    print("Checking incoming...")
    print()

    md_files = sorted(
        (path for path in files if path.suffix.lower() == ".md"),
        key=lambda path: path.name.casefold(),
    )
    pdf_files = sorted(
        (path for path in files if path.suffix.lower() == ".pdf"),
        key=lambda path: path.name.casefold(),
    )
    other_files = sorted(
        (path for path in files if path.suffix.lower() not in {".md", ".pdf"}),
        key=lambda path: path.name.casefold(),
    )

    errors: list[str] = []
    pairs: list[tuple[Path, Path]] = []

    if other_files:
        errors.append("Stray files found in incoming:")
        errors.extend(f"  {path.name}" for path in other_files)

    md_by_stem = {path.stem: path for path in md_files}
    pdf_by_stem = {path.stem: path for path in pdf_files}

    duplicate_md_stems = len(md_by_stem) != len(md_files)
    duplicate_pdf_stems = len(pdf_by_stem) != len(pdf_files)
    if duplicate_md_stems:
        errors.append("Incoming contains Markdown filenames that differ only by extension case or duplication.")
    if duplicate_pdf_stems:
        errors.append("Incoming contains PDF filenames that differ only by extension case or duplication.")

    for stem in sorted(set(md_by_stem) | set(pdf_by_stem), key=str.casefold):
        md_path = md_by_stem.get(stem)
        pdf_path = pdf_by_stem.get(stem)

        if md_path is None:
            errors.append(f"Missing matching Markdown file for PDF: {pdf_path.name}")
            continue
        if pdf_path is None:
            errors.append(f"Missing matching PDF file for Markdown: {md_path.name}")
            continue

        if md_path.name not in metadata:
            errors.append(f"Missing metadata entry for incoming document: {md_path.name}")
            continue

        destination_md = Path.cwd() / md_path.name
        destination_pdf = OUTPUT_DIR / pdf_path.name
        if destination_md.exists():
            errors.append(f"Incoming Markdown would overwrite an installed source file: {destination_md.name}")
        if destination_pdf.exists():
            errors.append(f"Incoming PDF would overwrite a published file: {destination_pdf.name}")

        size = pdf_path.stat().st_size
        print(f"Incoming document: {stem}")
        print(f"  MD:   {md_path.name}")
        print(f"  PDF:  {pdf_path.name}")
        print(f"  Size: {format_file_size(size)}")
        print(f"  Metadata: present")
        print()

        if size > PDF_WARNING_SIZE_MB * 1024 * 1024:
            print(f"WARNING: {pdf_path.name} is larger than {PDF_WARNING_SIZE_MB} MB.")
            print("Large PDFs may slow downloads and website performance.")
            print("If appropriate, open the PDF in Preview and use:")
            print("  File → Export... → Quartz Filter: Reduce File Size")
            print()

            if not ask_yes_no("Continue publishing this PDF?", default=True):
                print()
                print("Publishing cancelled. Files remain in incoming.")
                raise SystemExit(1)
            print()

        pairs.append((md_path, pdf_path))

    if errors:
        fail(errors, heading="INCOMING ERROR")

    print(f"Validated {len(pairs)} incoming document(s).")
    print()
    return pairs


def install_incoming(pairs: list[tuple[Path, Path]]) -> None:
    """Move validated incoming documents into their source/public locations."""
    if not pairs:
        return

    print("Installing incoming documents...")
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for md_path, pdf_path in pairs:
        destination_md = Path.cwd() / md_path.name
        destination_pdf = OUTPUT_DIR / pdf_path.name

        shutil.move(str(md_path), destination_md)
        shutil.move(str(pdf_path), destination_pdf)

        print(f"Installed {md_path.stem}")
        print(f"  Markdown: {destination_md}")
        print(f"  PDF:      {destination_pdf}")
        print()


# -----------------------------------------------------------------------------
# Markdown conversion
# -----------------------------------------------------------------------------


def remove_google_doc_images(markdown: str) -> str:
    """Remove Google Docs Markdown image embeds and image reference definitions."""

    # Remove inline image syntax anywhere in a line:
    # ![](file.png), ![alt](file.png)
    markdown = re.sub(
        r"!\[[^\]]*]\([^)]*\)",
        "",
        markdown,
    )

    # Remove reference-style images anywhere in a line:
    # ![][image12], ![alt][image12]
    markdown = re.sub(
        r"!\[[^\]]*]\[[^\]]*]",
        "",
        markdown,
    )

    # Remove image reference definitions.
    markdown = re.sub(
        r"^\[[^\]]+]:\s*.*$",
        "",
        markdown,
        flags=re.MULTILINE,
    )

    # Remove lines left with only Markdown emphasis or heading markers.
    markdown = re.sub(
        r"^\s*(?:#{1,6}\s*)?(?:\*{1,2}|_{1,2})?\s*(?:\*{1,2}|_{1,2})?\s*$",
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
    """Convert a small, safe subset of inline Markdown to HTML."""
    text = html.escape(text, quote=False)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda match: (
            f'<a href="{html.escape(match.group(2), quote=True)}">'
            f"{match.group(1)}</a>"
        ),
        text,
    )
    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)
    return text


def markdown_to_basic_html(markdown: str) -> str:
    """Convert the predictable Google Docs Markdown subset to semantic HTML."""
    output: list[str] = []
    paragraph: list[str] = []
    in_ul = False
    in_ol = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            lines = [inline_markdown_to_html(item.strip()) for item in paragraph if item.strip()]
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

        if re.fullmatch(r"#{1,6}", line.strip()):
            flush_paragraph()
            close_lists()
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            flush_paragraph()
            close_lists()
            # Demote transcript headings one level so the page retains one H1.
            level = min(len(heading.group(1)) + 1, 6)
            heading_text = strip_markdown_markup(heading.group(2))
            if heading_text:
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


# -----------------------------------------------------------------------------
# Page title and HTML generation
# -----------------------------------------------------------------------------


def title_has_resource_type(title: str) -> bool:
    title_lower = title.lower()
    return any(
        term in title_lower
        for term in [
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
        ]
    )


def prettify_filename_title(stem: str) -> str:
    """Create a readable fallback title from a filename stem."""
    title = re.sub(r"[_-]+", " ", stem).strip()
    title = re.sub(r"\s+", " ", title)
    return title or "Research Document"


def title_from_markdown(markdown: str, basename: str) -> tuple[str, str]:
    """Return the visible document title and HTML page title."""
    headings: list[tuple[int, str]] = []

    for line in markdown.splitlines():
        match = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if not match:
            continue

        level = len(match.group(1))
        heading_text = strip_markdown_markup(match.group(2))
        if re.match(r"^\d+[\.)]\s+", heading_text):
            continue
        if heading_text:
            headings.append((level, heading_text))

    h1 = next((heading_text for level, heading_text in headings if level == 1), "")
    h2 = next((heading_text for level, heading_text in headings if level == 2), "")

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

    if display_title.lower().strip() in {"press resource", "press resources"}:
        display_title = prettify_filename_title(basename)

    page_title = f"{display_title} | {SITE_NAME}"
    return display_title, page_title


def build_structured_data(
    display_title: str,
    canonical_url: str,
    pdf_url: str,
    metadata: DocumentMetadata,
) -> str:
    """Return escaped JSON-LD for the research document."""
    data = {
        "@context": "https://schema.org",
        "@type": "ScholarlyArticle",
        "headline": display_title,
        "description": metadata.description,
        "url": canonical_url,
        "mainEntityOfPage": canonical_url,
        "author": {
            "@type": "Person",
            "name": AUTHOR_NAME,
        },
        "publisher": {
            "@type": "Organization",
            "name": PUBLISHER_NAME,
        },
        "isAccessibleForFree": True,
        "keywords": list(metadata.keywords),
        "encoding": {
            "@type": "MediaObject",
            "contentUrl": pdf_url,
            "encodingFormat": "application/pdf",
        },
    }
    # JSON characters are safe inside application/ld+json, but replace </ to
    # prevent a title or description from prematurely closing the script tag.
    return json.dumps(data, ensure_ascii=False, indent=2).replace("</", "<\\/")


def build_page(md_path: Path, metadata: DocumentMetadata) -> tuple[Path, bool]:
    basename = md_path.stem
    pdf_name = f"{basename}.pdf"
    html_name = f"{basename}.html"
    canonical_url = f"{SITE_BASE_URL}/research/{quote(html_name)}"
    pdf_url = f"{SITE_BASE_URL}/research/{quote(pdf_name)}"

    markdown = remove_google_doc_images(md_path.read_text(encoding="utf-8"))
    display_title, page_title = title_from_markdown(markdown, basename)
    transcript_html = markdown_to_basic_html(markdown)
    structured_data = build_structured_data(
        display_title=display_title,
        canonical_url=canonical_url,
        pdf_url=pdf_url,
        metadata=metadata,
    )
    page_intro_html = inline_markdown_to_html(metadata.page_intro)
    # Permit only the limited emphasis tags documented for metadata entries.
    page_intro_html = (
        page_intro_html
        .replace("&lt;em&gt;", "<em>")
        .replace("&lt;/em&gt;", "</em>")
        .replace("&lt;strong&gt;", "<strong>")
        .replace("&lt;/strong&gt;", "</strong>")
    )

    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(page_title)}</title>
  <meta name="description" content="{html.escape(metadata.description, quote=True)}">
  <link rel="canonical" href="{html.escape(canonical_url, quote=True)}">

  <script type="application/ld+json">
{structured_data}
  </script>

  <link rel="icon" type="image/png" sizes="16x16" href="../assets/favicon-16.png">
  <link rel="icon" type="image/png" sizes="32x32" href="../assets/favicon-32.png">
  <link rel="apple-touch-icon" href="../assets/apple-touch-icon.png">

  <script>
  if (localStorage.getItem("CounterDevIgnore") !== "true") {{
    const script = document.createElement("script");
    script.src = "https://cdn.counter.dev/script.js";
    script.dataset.id = "800e0f07-e8c7-43c4-bdaf-617aab5c0504";
    script.dataset.utcoffset = "-7";
    script.dataset.trackPath = "true";
    script.defer = true;
    document.head.appendChild(script);
  }} else {{
    console.log("Counter.dev disabled for this browser.");
  }}
  </script>

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
      <p class="back-link"><a href="{html.escape(PRESS_RESOURCES_PATH, quote=True)}#research-papers">← Back to Research Documents</a></p>
      <h1>{html.escape(display_title)}</h1>
      <p class="subtitle">{page_intro_html}</p>
      <div class="actions">
        <a class="button" href="{html.escape(pdf_name, quote=True)}" download>Download PDF</a>
      </div>
    </header>

    <section class="pdf-viewer" aria-label="PDF preview">
      <object data="{html.escape(pdf_name, quote=True)}" type="application/pdf">
        <div class="pdf-fallback">
          <p>Your browser does not support embedded PDFs.</p>
          <p><a href="{html.escape(pdf_name, quote=True)}">Download the PDF instead.</a></p>
        </div>
      </object>
    </section>

    <details class="transcript">
      <summary>Full searchable transcript</summary>
      <div class="transcript-content">
        <p class="transcript-note">This searchable transcript is provided for accessibility and to support indexing of the complete research document.</p>
{transcript_html}
      </div>
    </details>

    <p class="back-link">
      <a href="{html.escape(PRESS_RESOURCES_PATH, quote=True)}#research-papers">← Back to Research Documents</a>
    </p>

    <footer>From <em>The Prescott Girls</em> Research Documents.</footer>
  </main>
</body>
</html>
'''

    out_path = OUTPUT_DIR / html_name
    changed = write_text_if_changed(out_path, page)
    return out_path, changed


def build_documents(metadata: dict[str, DocumentMetadata]) -> None:
    """Generate HTML pages for every installed Markdown research document."""
    md_files = sorted(Path.cwd().glob("*.md"), key=lambda path: path.name.casefold())
    if not md_files:
        print("No installed .md files found in the current directory.")
        return

    updated = 0
    unchanged = 0

    for md_path in md_files:
        document_metadata = metadata.get(md_path.name)
        if document_metadata is None:
            # Coverage validation should make this impossible; retain a clear guard.
            fail([f"No metadata loaded for {md_path.name}."])

        out_path, changed = build_page(md_path, document_metadata)
        if changed:
            updated += 1
            print(f"Updated   {out_path.name}")
        else:
            unchanged += 1
            print(f"Unchanged {out_path.name}")

    print()
    print(f"Research documents updated:   {updated}")
    print(f"Research documents unchanged: {unchanged}")


# -----------------------------------------------------------------------------
# Main workflow
# -----------------------------------------------------------------------------


def main() -> None:
    metadata, metadata_warnings = parse_metadata_file()
    print_metadata_warnings(metadata_warnings)

    installed_md_files = sorted(Path.cwd().glob("*.md"), key=lambda path: path.name.casefold())
    files_waiting = incoming_files()
    incoming_md_files = sorted(
        (path for path in files_waiting if path.suffix.lower() == ".md"),
        key=lambda path: path.name.casefold(),
    )

    # Validate the complete intended library before moving or generating anything.
    validate_metadata_coverage(metadata, installed_md_files, incoming_md_files)
    validate_existing_documents(installed_md_files)
    pairs = validate_incoming(metadata, files_waiting)

    # Only now is it safe to modify the source/public directories.
    install_incoming(pairs)
    build_documents(metadata)


if __name__ == "__main__":
    main()
