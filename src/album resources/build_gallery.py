#!/usr/bin/env python3
"""
build_gallery.py

Builds the generated author media gallery for The Prescott Girls website.

Expected project layout:

    project-root/
        author.html
        css/site.css
        assets/favicon-16.png
        assets/favicon-32.png
        assets/apple-touch-icon.png
        album/
            album.html          <-- generated
            *.jpg / *.jpeg / *.png / *.webp / *.mp4 / *.mov / *.m4v / *.webm
            thumbs/             <-- generated thumbnails for images
        src/
            album_resources/
                build_gallery.py
                author-gallery-control.txt

Run from anywhere:

    python src/album_resources/build_gallery.py

Optional:

    python src/album_resources/build_gallery.py --strict

The script reports:
    - files listed in the control file but missing from album/
    - supported media files in album/ not listed in the control file
    - duplicate ids and duplicate filenames in the control file
    - missing titles/captions
    - unsupported files in album/

Notes:
    - Images use generated thumbnails in album/thumbs/.
    - Videos are displayed with a small HTML video preview and open in GLightbox.
    - HEIC/HEVC are intentionally reported as unsupported for public web use.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

try:
    from PIL import Image, ImageOps
except Exception:  # pragma: no cover
    Image = None
    ImageOps = None


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}
SUPPORTED_EXTS = IMAGE_EXTS | VIDEO_EXTS
UNSUPPORTED_WEB_EXTS = {".heic", ".heif", ".avi", ".wmv", ".hevc"}

CONTROL_FILENAME = "author-gallery-control.txt"
OUTPUT_FILENAME = "album.html"
THUMB_DIRNAME = "thumbs"
THUMB_MAX_SIZE = (700, 525)


@dataclass
class Photo:
    fields: Dict[str, str]
    section_id: str = ""
    section_title: str = ""
    index: int = 0

    @property
    def file(self) -> str:
        return self.fields.get("file", "").strip()

    @property
    def id(self) -> str:
        return self.fields.get("id", "").strip()

    @property
    def title(self) -> str:
        return self.fields.get("title", "").strip()

    @property
    def caption(self) -> str:
        return self.fields.get("caption", "").strip()

    @property
    def alt(self) -> str:
        return self.fields.get("alt", "").strip() or self.title or self.caption or self.file

    @property
    def date(self) -> str:
        return self.fields.get("date", "").strip()

    @property
    def location(self) -> str:
        return self.fields.get("location", "").strip()

    @property
    def draft(self) -> str:
        return self.fields.get("draft", "").strip().lower()

    @property
    def sort(self) -> int:
        raw = self.fields.get("sort", "").strip()
        try:
            return int(raw)
        except Exception:
            return self.index

    @property
    def ext(self) -> str:
        return Path(self.file).suffix.lower()

    @property
    def media_type(self) -> str:
        explicit = self.fields.get("media_type", "").strip().lower()
        if explicit in {"image", "video"}:
            return explicit
        if self.ext in IMAGE_EXTS:
            return "image"
        if self.ext in VIDEO_EXTS:
            return "video"
        return "unknown"


@dataclass
class Section:
    fields: Dict[str, str]
    photos: List[Photo] = field(default_factory=list)
    index: int = 0

    @property
    def id(self) -> str:
        return self.fields.get("id", "").strip() or slugify(self.title or f"section-{self.index}")

    @property
    def title(self) -> str:
        return self.fields.get("title", "").strip()

    @property
    def caption(self) -> str:
        return self.fields.get("caption", "").strip()

    @property
    def sort(self) -> int:
        raw = self.fields.get("sort", "").strip()
        try:
            return int(raw)
        except Exception:
            return self.index


@dataclass
class Gallery:
    page: Dict[str, str]
    sections: List[Section]


def find_project_root(script_path: Path) -> Path:
    """Find project root from src/album_resources/build_gallery.py or cwd fallback."""
    resolved = script_path.resolve()
    parts = resolved.parts
    if len(parts) >= 3 and resolved.parent.name in {"album_resources", "album resources"} and resolved.parent.parent.name == "src":
        return resolved.parent.parent.parent

    cwd = Path.cwd().resolve()
    if (cwd / "src").exists() and (cwd / "album").exists():
        return cwd
    return resolved.parent.parent.parent


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "item"


def parse_key_value(line: str) -> Optional[Tuple[str, str]]:
    if "=" not in line:
        return None
    key, value = line.split("=", 1)
    return key.strip(), value.strip()


def parse_control_file(path: Path) -> Gallery:
    if not path.exists():
        raise FileNotFoundError(f"Control file not found: {path}")

    page: Dict[str, str] = {}
    sections: List[Section] = []
    current_section: Optional[Section] = None
    current_photo: Optional[Photo] = None
    photo_index = 0

    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line == "[SECTION]":
            current_section = Section(fields={}, photos=[], index=len(sections))
            sections.append(current_section)
            current_photo = None
            continue

        if line in {"[PHOTO]", "[MEDIA]"}:
            if current_section is None:
                raise ValueError(f"{line} before [SECTION] at line {line_no}")
            current_photo = Photo(fields={}, section_id=current_section.id, section_title=current_section.title, index=photo_index)
            photo_index += 1
            current_section.photos.append(current_photo)
            continue

        kv = parse_key_value(line)
        if kv is None:
            print(f"WARNING: Ignoring malformed line {line_no}: {raw_line}")
            continue

        key, value = kv
        if current_photo is not None:
            current_photo.fields[key] = value
        elif current_section is not None:
            current_section.fields[key] = value
            # refresh already assigned photo section data only for subsequent photos; not critical
        else:
            page[key] = value

    # Fill section references now that section fields are complete.
    for section in sections:
        for photo in section.photos:
            photo.section_id = section.id
            photo.section_title = section.title

    return Gallery(page=page, sections=sections)


def collect_album_media(album_dir: Path) -> Tuple[set[str], set[str], set[str]]:
    supported: set[str] = set()
    unsupported: set[str] = set()
    ignored: set[str] = set()

    if not album_dir.exists():
        return supported, unsupported, ignored

    for path in album_dir.iterdir():
        if path.is_dir():
            continue
        if path.name.startswith(".") or path.name == OUTPUT_FILENAME:
            ignored.add(path.name)
            continue
        ext = path.suffix.lower()
        if ext in SUPPORTED_EXTS:
            supported.add(path.name)
        elif ext in UNSUPPORTED_WEB_EXTS:
            unsupported.add(path.name)
        else:
            ignored.add(path.name)
    return supported, unsupported, ignored


def validate(gallery: Gallery, album_dir: Path) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    if not album_dir.exists():
        errors.append(f"Album folder does not exist: {album_dir}")
        return errors, warnings

    album_files, unsupported, _ignored = collect_album_media(album_dir)
    control_files: set[str] = set()
    ids: set[str] = set()

    for filename in sorted(unsupported):
        warnings.append(f"Unsupported web media format in album folder: {filename}")

    for section in gallery.sections:
        if not section.title:
            warnings.append(f"Section missing title: section #{section.index + 1}")
        if not section.caption:
            warnings.append(f"Section missing caption: {section.title or section.id}")

        for photo in section.photos:
            if not photo.file:
                errors.append(f"Photo entry missing file in section: {section.title or section.id}")
                continue

            if photo.id:
                if photo.id in ids:
                    errors.append(f"Duplicate media id: {photo.id}")
                ids.add(photo.id)

            if photo.file in control_files:
                errors.append(f"Duplicate filename in control file: {photo.file}")
            control_files.add(photo.file)

            if photo.ext not in SUPPORTED_EXTS:
                warnings.append(f"Referenced file has unsupported web format: {photo.file}")

            if photo.file not in album_files:
                errors.append(f"Referenced media missing from album folder: {photo.file}")

            if not photo.title:
                warnings.append(f"Missing title: {photo.file}")
            if not photo.caption:
                warnings.append(f"Missing caption: {photo.file}")
            if photo.draft in {"yes", "true", "1"}:
                warnings.append(f"Draft caption/title marked for review: {photo.file}")

    for filename in sorted(album_files - control_files):
        warnings.append(f"Media file exists but is not referenced in control file: {filename}")

    return errors, warnings


def url_path(filename: str) -> str:
    # quote each path component but preserve slashes if they ever appear
    return "/".join(quote(part) for part in filename.split("/"))


def make_thumbnail(src: Path, thumb_dir: Path) -> str:
    """Create thumbnail for image. Returns thumbnail filename, or original filename if Pillow unavailable/fails."""
    thumb_dir.mkdir(parents=True, exist_ok=True)
    ext = src.suffix.lower()
    stem = src.stem
    # Use jpg thumbnails for consistency. Avoid collisions by including a sanitized original stem.
    thumb_name = f"{slugify(stem)}.jpg"
    thumb_path = thumb_dir / thumb_name

    if Image is None or ImageOps is None:
        return src.name

    try:
        needs_update = not thumb_path.exists() or src.stat().st_mtime > thumb_path.stat().st_mtime
        if needs_update:
            with Image.open(src) as img:
                img = ImageOps.exif_transpose(img)
                img.thumbnail(THUMB_MAX_SIZE)
                if img.mode not in {"RGB", "L"}:
                    img = img.convert("RGB")
                img.save(thumb_path, "JPEG", quality=82, optimize=True)
        return f"{THUMB_DIRNAME}/{thumb_name}"
    except Exception as exc:
        print(f"WARNING: Could not create thumbnail for {src.name}: {exc}")
        return src.name


def media_description(photo: Photo) -> str:
    bits = []
    if photo.date:
        bits.append(f"<strong>Date:</strong> {html.escape(photo.date)}")
    if photo.location and photo.location.lower() not in {"unknown", "auto"}:
        bits.append(f"<strong>Location:</strong> {html.escape(photo.location)}")
    if photo.caption:
        bits.append(html.escape(photo.caption))
    return "<br>".join(bits)


def render_media_card(photo: Photo, album_dir: Path) -> str:
    href = url_path(photo.file)
    title = html.escape(photo.title or photo.file)
    caption = html.escape(photo.caption)
    alt = html.escape(photo.alt)
    description = media_description(photo)
    meta_items = []
    if photo.date:
        meta_items.append(html.escape(photo.date))
    if photo.location and photo.location.lower() not in {"unknown", "auto"}:
        meta_items.append(html.escape(photo.location))
    meta = " · ".join(meta_items)

    data_type = "video" if photo.media_type == "video" else "image"
    type_attr = ' data-type="video"' if data_type == "video" else ""
    desc_attr = html.escape(description, quote=True)
    title_attr = html.escape(photo.title or photo.file, quote=True)

    if photo.media_type == "video":
        preview = f"""
          <div class=\"video-preview\" aria-hidden=\"true\">
            <video src=\"{href}\" muted preload=\"metadata\"></video>
            <span class=\"play-badge\">▶</span>
          </div>
        """
    else:
        thumb = make_thumbnail(album_dir / photo.file, album_dir / THUMB_DIRNAME)
        preview = f'<img src="{url_path(thumb)}" alt="{alt}">'

    meta_html = f'<p class="album-meta">{meta}</p>' if meta else ""
    caption_html = f'<p>{caption}</p>' if caption else ""

    return f"""
      <a class=\"album-card glightbox\" href=\"{href}\" data-gallery=\"author-gallery\" data-title=\"{title_attr}\" data-description=\"{desc_attr}\"{type_attr}>
        {preview}
        <div class=\"album-card-text\">
          <h3>{title}</h3>
          {meta_html}
          {caption_html}
        </div>
      </a>
    """


def render_section(section: Section, album_dir: Path) -> str:
    photos = sorted(section.photos, key=lambda p: p.sort)
    cards = "\n".join(render_media_card(photo, album_dir) for photo in photos)
    section_caption_html = f'<p>{html.escape(section.caption)}</p>' if section.caption else ""

    return f"""
    <section class=\"section album-section\" id=\"{html.escape(section.id)}\">
      <h2>{html.escape(section.title)}</h2>
      {section_caption_html}
      <div class=\"album-grid\">
        {cards}
      </div>
    </section>
    """


def render_html(gallery: Gallery, album_dir: Path) -> str:
    page_title = gallery.page.get("page_title", "Author Gallery").strip() or "Author Gallery"
    page_intro = gallery.page.get("page_intro", "").strip()
    sections = sorted(gallery.sections, key=lambda s: s.sort)
    sections_html = "\n".join(render_section(section, album_dir) for section in sections)
    page_intro_html = f'<p>{html.escape(page_intro)}</p>' if page_intro else ""

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{html.escape(page_title)} | The Prescott Girls</title>
  <meta name=\"description\" content=\"A curated author gallery for The Prescott Girls, including research trips, museum visits, technology history, music, and travel.\">

  <!-- Open Graph -->
  <meta property=\"og:title\" content=\"{html.escape(page_title)} | The Prescott Girls\">
  <meta property=\"og:description\" content=\"A curated author gallery for The Prescott Girls.\">
  <meta property=\"og:image\" content=\"https://www.theprescottgirls.com/assets/promo-image.jpg\">
  <meta property=\"og:image:secure_url\" content=\"https://www.theprescottgirls.com/assets/promo-image.jpg\">
  <meta property=\"og:image:type\" content=\"image/jpeg\">
  <meta property=\"og:image:width\" content=\"1200\">
  <meta property=\"og:image:height\" content=\"630\">
  <meta property=\"og:image:alt\" content=\"The Prescott Girls book cover and interior illustration\">
  <meta property=\"og:url\" content=\"https://www.theprescottgirls.com/album/album.html\">
  <meta property=\"og:type\" content=\"website\">

  <!-- Twitter -->
  <meta name=\"twitter:card\" content=\"summary_large_image\">
  <meta name=\"twitter:image\" content=\"https://www.theprescottgirls.com/assets/book-cover.jpg\">

  <!-- Icons -->
  <link rel=\"icon\" type=\"image/png\" sizes=\"16x16\" href=\"../assets/favicon-16.png\">
  <link rel=\"icon\" type=\"image/png\" sizes=\"32x32\" href=\"../assets/favicon-32.png\">
  <link rel=\"apple-touch-icon\" href=\"../assets/apple-touch-icon.png\">

  <!-- Styles -->
  <link rel=\"stylesheet\" href=\"../css/site.css\" />
  <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/glightbox/dist/css/glightbox.min.css\" />

  <!-- Canonical -->
  <link rel=\"canonical\" href=\"https://www.theprescottgirls.com/album/album.html\">

  <!-- Counter.dev -->
  <script src=\"https://cdn.counter.dev/script.js\"
    data-id=\"800e0f07-e8c7-43c4-bdaf-617aab5c0504\"
    data-utcoffset=\"-7\"
    data-track-path=\"true\"
    defer></script>

  <style>
    .return-link {{
      display: inline-block;
      margin: 0 0 1rem 0;
      font-weight: 600;
    }}
    .album-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1.25rem;
      margin-top: 1.25rem;
    }}
    .album-card {{
      display: block;
      text-decoration: none;
      color: inherit;
      border: 1px solid rgba(0,0,0,.12);
      border-radius: 10px;
      overflow: hidden;
      background: rgba(255,255,255,.55);
      box-shadow: 0 1px 4px rgba(0,0,0,.08);
      transition: transform .15s ease, box-shadow .15s ease;
    }}
    .album-card:hover {{
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0,0,0,.14);
    }}
    .album-card img,
    .album-card video {{
      width: 100%;
      aspect-ratio: 4 / 3;
      object-fit: cover;
      display: block;
      background: #eee;
    }}
    .album-card-text {{
      padding: .85rem .9rem 1rem;
    }}
    .album-card-text h3 {{
      margin: 0 0 .35rem 0;
      font-size: 1.05rem;
    }}
    .album-card-text p {{
      margin: .35rem 0 0 0;
    }}
    .album-meta {{
      font-size: .9rem;
      opacity: .8;
    }}
    .video-preview {{
      position: relative;
      background: #222;
    }}
    .play-badge {{
      position: absolute;
      left: 50%;
      top: 50%;
      transform: translate(-50%, -50%);
      width: 3rem;
      height: 3rem;
      border-radius: 50%;
      display: grid;
      place-items: center;
      background: rgba(0,0,0,.62);
      color: white;
      font-size: 1.25rem;
      line-height: 1;
    }}
    .gdesc-inner {{
      font-size: 1rem;
      line-height: 1.45;
    }}
  </style>
</head>
<body>
<a class=\"skip\" href=\"#main\">Skip to content</a>
<header>
  <div class=\"container brandbar\">
    <a class=\"brand\" href=\"../index.html\">
      <span class=\"mark\" aria-hidden=\"true\"></span>
      <span class=\"title\">The Prescott Girls</span>
    </a>
    <nav aria-label=\"Primary navigation\">
      <a href=\"../index.html\">Home</a>
      <a href=\"../book.html\">Book</a>
      <a href=\"../illustrations.html\">Illustrations</a>
      <a href=\"../interpretations.html\">Interpretations</a>
      <a href=\"../author.html\">Author</a>
      <a href=\"../teachers.html\">Teachers</a>
      <a href=\"../events.html\">Events</a>
      <a href=\"../faq.html\">FAQ</a>
      <a href=\"../contact.html\">Contact</a>
    </nav>
  </div>
</header>

<main id=\"main\" class=\"container\">
  <div class=\"section\">
    <h1>{html.escape(page_title)}</h1>
    {page_intro_html}
  </div>

  {sections_html}

</main>

<footer>
  <div class=\"container footergrid\">
    <div>© 2026 Aric Wilmunder. All rights reserved.</div>
    <div class=\"smalllinks\">
      <a href=\"../contact.html\">Contact</a>
      <a href=\"../events.html\">Events</a>
      <a href=\"../illustrations.html\">Illustrations</a>
    </div>
  </div>
</footer>

<script src=\"https://cdn.jsdelivr.net/npm/glightbox/dist/js/glightbox.min.js\"></script>
<script>
  const lightbox = GLightbox({{
    selector: '.glightbox',
    touchNavigation: true,
    loop: true,
    closeButton: true
  }});
</script>

</body>
</html>
"""


def control_file_names(gallery: Gallery) -> set[str]:
    """Return all filenames referenced by [PHOTO] / [MEDIA] blocks."""
    names: set[str] = set()
    for section in gallery.sections:
        for photo in section.photos:
            if photo.file:
                names.add(photo.file)
    return names


def first_section_id(gallery: Gallery) -> str:
    """Suggest the first section as a default insertion point."""
    if gallery.sections:
        return gallery.sections[0].id
    return "prescott-research"


def exif_date_from_image(path: Path) -> str:
    """Return YYYY-MM-DD from image EXIF DateTimeOriginal/DateTime when available."""
    if Image is None:
        return ""
    try:
        from PIL.ExifTags import TAGS
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return ""
            named = {TAGS.get(k, k): v for k, v in exif.items()}
            raw = (
                named.get("DateTimeOriginal")
                or named.get("DateTimeDigitized")
                or named.get("DateTime")
                or ""
            )
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="ignore")
            raw = str(raw).strip()
            # EXIF dates are usually "YYYY:MM:DD HH:MM:SS"
            if len(raw) >= 10 and raw[4] == ":" and raw[7] == ":":
                return raw[:10].replace(":", "-")
    except Exception:
        pass
    return ""


def exif_time_from_image(path: Path) -> str:
    """Return HH:MM:SS from image EXIF DateTimeOriginal/DateTime when available."""
    if Image is None:
        return ""
    try:
        from PIL.ExifTags import TAGS
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return ""
            named = {TAGS.get(k, k): v for k, v in exif.items()}
            raw = (
                named.get("DateTimeOriginal")
                or named.get("DateTimeDigitized")
                or named.get("DateTime")
                or ""
            )
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="ignore")
            raw = str(raw).strip()
            if len(raw) >= 19:
                return raw[11:19]
    except Exception:
        pass
    return ""


def _gps_coord(values, ref: str) -> Optional[float]:
    """Convert EXIF GPS rationals into decimal degrees."""
    try:
        def as_float(v):
            try:
                return float(v)
            except Exception:
                return float(v[0]) / float(v[1])
        deg = as_float(values[0])
        minutes = as_float(values[1])
        seconds = as_float(values[2])
        result = deg + minutes / 60.0 + seconds / 3600.0
        if ref in {"S", "W"}:
            result = -result
        return result
    except Exception:
        return None


def exif_gps_from_image(path: Path) -> str:
    """Return lat,lng from image EXIF GPS data when available."""
    if Image is None:
        return ""
    try:
        from PIL.ExifTags import GPSTAGS
        with Image.open(path) as img:
            exif = img.getexif()
            gps_ifd = exif.get_ifd(0x8825) if hasattr(exif, "get_ifd") else {}
            if not gps_ifd:
                return ""
            gps = {GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
            lat = _gps_coord(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef", "N"))
            lon = _gps_coord(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef", "E"))
            if lat is None or lon is None:
                return ""
            return f"{lat:.6f},{lon:.6f}"
    except Exception:
        pass
    return ""


def title_from_filename(filename: str) -> str:
    """Create a human-readable draft title from a filename."""
    stem = Path(filename).stem
    stem = re.sub(r"^\d+\s+edited\s+", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"[_-]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    # Avoid useless camera names as titles.
    if re.match(r"^(IMG|DSC|DSCN)\s*\d+$", stem, flags=re.IGNORECASE):
        return "New Gallery Photo"
    return stem.title() if stem else "New Gallery Photo"


def media_block_for_unreferenced_file(filename: str, album_dir: Path) -> str:
    """Create a paste-ready [PHOTO] block for an unreferenced media file."""
    path = album_dir / filename
    ext = path.suffix.lower()
    media_type = "video" if ext in VIDEO_EXTS else "image"

    date = exif_date_from_image(path) if media_type == "image" else ""
    time = exif_time_from_image(path) if media_type == "image" else ""
    gps = exif_gps_from_image(path) if media_type == "image" else ""

    title = title_from_filename(filename)
    caption = "Caption needed."

    lines = [
        "[PHOTO]",
        f"file={filename}",
    ]
    if media_type == "video":
        lines.append("media_type=video")
    lines.extend([
        f"date={date}",
        f"time={time}",
        f"gps={gps}",
        "location=Unknown",
        "location_confidence=unknown",
        f"title={title}",
        f"caption={caption}",
        "draft=yes",
    ])
    return "\n".join(lines)


def unreferenced_media_files(gallery: Gallery, album_dir: Path) -> List[str]:
    album_files, _unsupported, _ignored = collect_album_media(album_dir)
    control_files = control_file_names(gallery)
    return sorted(album_files - control_files)


def print_unreferenced_media_blocks(gallery: Gallery, album_dir: Path) -> None:
    """Print paste-ready [PHOTO] blocks for supported media not in the control file."""
    missing_from_control = unreferenced_media_files(gallery, album_dir)
    if not missing_from_control:
        return

    print("\nPaste-ready control file blocks for unreferenced media")
    print("-----------------------------------------------------")
    print(f"# Suggested insertion section: {first_section_id(gallery)}")
    print("# Review title, caption, location, and section placement before publishing.\n")

    for filename in missing_from_control:
        print(media_block_for_unreferenced_file(filename, album_dir))
        print()



def print_report(errors: List[str], warnings: List[str], gallery: Gallery, album_dir: Path, output_file: Path) -> None:
    control_count = sum(len(section.photos) for section in gallery.sections)
    album_files, unsupported, _ignored = collect_album_media(album_dir)

    print("\nGallery Validation Report")
    print("-------------------------")
    print(f"Sections in control file: {len(gallery.sections)}")
    print(f"Media entries in control file: {control_count}")
    print(f"Supported media files in album folder: {len(album_files)}")
    print(f"Unsupported web media files in album folder: {len(unsupported)}")
    print(f"Output file: {output_file}")

    if errors:
        print("\nERRORS:")
        for item in errors:
            print(f"  - {item}")

    if warnings:
        print("\nWARNINGS:")
        for item in warnings:
            print(f"  - {item}")

    if not errors and not warnings:
        print("\nNo issues found.")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build The Prescott Girls author media gallery.")
    parser.add_argument("--strict", action="store_true", help="Do not generate output if warnings are present.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to auto-detection.")
    parser.add_argument("--control", type=Path, default=None, help="Control file path. Defaults to src/album_resources/author-gallery-control.txt.")
    args = parser.parse_args()

    script_path = Path(__file__)
    root = args.root.resolve() if args.root else find_project_root(script_path)
    album_dir = root / "album"
    output_file = album_dir / OUTPUT_FILENAME

    control_file = args.control.resolve() if args.control else root / "src" / "album_resources" / CONTROL_FILENAME
    if not control_file.exists():
        # Backward-compatible fallback for the earlier folder name with a space.
        fallback = root / "src" / "album resources" / CONTROL_FILENAME
        if fallback.exists():
            control_file = fallback

    try:
        gallery = parse_control_file(control_file)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    album_dir.mkdir(parents=True, exist_ok=True)
    errors, warnings = validate(gallery, album_dir)
    print_report(errors, warnings, gallery, album_dir, output_file)
    print_unreferenced_media_blocks(gallery, album_dir)

    if errors:
        print("Not generating album.html because errors were found.", file=sys.stderr)
        return 1
    if args.strict and warnings:
        print("Not generating album.html because --strict was used and warnings were found.", file=sys.stderr)
        return 1

    html_text = render_html(gallery, album_dir)
    output_file.write_text(html_text, encoding="utf-8")
    print(f"Generated: {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
