"""Prototype builder: merges mathedu htmldoc text with MinerU figure crops into Markdown."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

from lxml import html as lxml_html
from PIL import Image


def clean_text(text: str) -> str:
    """Normalize non-breaking spaces and excessive whitespace while preserving exact words."""
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def parse_page_spec(spec: str, *, preserve_order: bool = False) -> list[int]:
    """Parse a page spec like '13-16' or '13,15,17-19' into a sorted unique list of page numbers."""
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
            if end < start:
                raise ValueError(f"Invalid page range: {part}")
            pages.extend(range(start, end + 1))
        else:
            pages.append(int(part))
    if not pages:
        raise ValueError("Page spec cannot be empty")
    if any(p <= 0 for p in pages):
        raise ValueError("Page numbers must be positive")
    return pages if preserve_order else sorted(set(pages))


def crop_mineru_images(
    mineru_json_path: Path,
    jpg_dir: Path,
    page_numbers: list[int],
    images_out_dir: Path,
    *,
    source_page_numbers: list[int] | None = None,
) -> dict[int, list[dict]]:
    """Crop all `image` blocks from MinerU JSON and return per-page image metadata."""
    data = json.loads(mineru_json_path.read_text(encoding="utf-8"))
    source_pages = source_page_numbers if source_page_numbers is not None else data.get("page_numbers")
    if not source_pages:
        raise ValueError("MinerU page_numbers metadata or --source-pages is required")
    if len(set(source_pages)) != len(source_pages) or any(type(p) is not int or p <= 0 for p in source_pages):
        raise ValueError("Source page_numbers must be unique positive integers")
    indexed_pages = {}
    for page in data.get("pages", []):
        pidx = page["page_idx"]
        if type(pidx) is not int or not 0 <= pidx < len(source_pages) or pidx in indexed_pages:
            raise ValueError(f"Invalid or duplicate MinerU page_idx: {pidx}")
        indexed_pages[pidx] = page
    available = {source_pages[idx] for idx in indexed_pages}
    missing = set(page_numbers) - available
    if missing:
        raise ValueError(f"Missing MinerU pages: {sorted(missing)}")
    for pno in page_numbers:
        if not (jpg_dir / f"{pno:04d}.jpg").is_file():
            raise FileNotFoundError(f"Missing source scan: {pno:04d}.jpg")
    images_out_dir.mkdir(parents=True, exist_ok=True)
    per_page: dict[int, list[dict]] = {}

    for page in data.get("pages", []):
        pidx = page["page_idx"]
        pno = source_pages[pidx]
        if pno not in page_numbers:
            continue
        jpg_path = jpg_dir / f"{pno:04d}.jpg"

        blocks = page.get("blocks", [])
        text_blocks_before = 0
        fig_idx = 0
        with Image.open(jpg_path) as im:
            w, h = im.size
            for b in blocks:
                btype = b.get("type", "")
                if btype == "image":
                    fig_idx += 1
                    bbox = b["bbox"]
                    if (
                        len(bbox) != 4
                        or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in bbox)
                        or not (0 <= bbox[0] < bbox[2] <= 1 and 0 <= bbox[1] < bbox[3] <= 1)
                    ):
                        raise ValueError(f"Invalid normalized bbox on page {pno}: {bbox}")
                    crop = im.crop(
                        (
                            int(bbox[0] * w),
                            int(bbox[1] * h),
                            int(bbox[2] * w),
                            int(bbox[3] * h),
                        )
                    )
                    img_name = f"p{pno:04d}_fig{fig_idx}.png"
                    crop.save(images_out_dir / img_name)
                    per_page.setdefault(pno, []).append(
                        {
                            "filename": img_name,
                            "bbox": bbox,
                            "after_text_block_idx": text_blocks_before,
                        }
                    )
                elif btype not in ("page_number", "page_footnote"):
                    text_blocks_before += 1

    return per_page


def _table_to_md(table_el: lxml_html.HtmlElement, pno: int, inline_fn_counter: int) -> tuple[str, int]:
    if table_el.xpath(".//table"):
        raise ValueError(f"Nested tables are not supported on page {pno}")
    rows: list[list[str]] = []
    for tr in table_el.xpath(".//tr"):
        if any(
            not isinstance(child.tag, str) or child.tag not in ("th", "td")
            for child in tr
            if isinstance(child.tag, str)
        ):
            raise ValueError(f"Unsupported element inside table row on page {pno}")
        cells = tr.xpath("./th|./td")
        if not cells:
            continue
        row_cells: list[str] = []
        for cell in cells:
            for attr in ("rowspan", "colspan"):
                val = cell.get(attr)
                if val is not None and val.strip() != "1":
                    raise ValueError(f"Table cell with {attr}={val!r} is not supported on page {pno}")
            if cell.xpath(".//img|.//svg"):
                raise ValueError(f"Embedded media inside table cell is not supported on page {pno}")
            clone = lxml_html.fromstring(lxml_html.tostring(cell, encoding="unicode"))
            for span in clone.xpath(".//span[contains(@class, 'fnsymbol')]"):
                inline_fn_counter += 1
                span.text = f"[^{pno}-{inline_fn_counter}]"
            cell_txt = clean_text(" ".join(clone.itertext())).replace("|", r"\|")
            row_cells.append(cell_txt)
        rows.append(row_cells)
    if not rows:
        raise ValueError(f"Empty or malformed table on page {pno}")
    col_counts = {len(r) for r in rows}
    if len(col_counts) != 1:
        raise ValueError(f"Ragged table column counts {sorted(col_counts)} on page {pno}")
    col_count = len(rows[0])
    header = "| " + " | ".join(rows[0]) + " |"
    sep = "| " + " | ".join(["---"] * col_count) + " |"
    body = ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join([header, sep, *body]), inline_fn_counter


def html_page_to_md(
    page_el: lxml_html.HtmlElement,
    pno: int,
    page_images: list[dict],
) -> str:
    """Convert a single htmldoc page element into Markdown, inserting cropped images."""
    lines: list[str] = [f"<!-- Page {pno} -->"]
    footnotes: list[str] = []
    inline_fn_counter = 0
    footer_fn_counter = 0

    caption_map: list[str] = []
    body_nodes: list[tuple[str, str]] = []

    pagebox = page_el.find(".//div[@class='pagebox']")
    if pagebox is None:
        return ""

    for child in pagebox:
        if not isinstance(child.tag, str):
            continue
        cls = child.get("class", "")
        cls_tokens = set(cls.split())
        tag = child.tag

        if tag == "div" and "fn" in cls_tokens:
            fn_paras = child.findall(".//p")
            if not fn_paras and clean_text("".join(child.itertext())):
                raise ValueError(f"Footnote container without <p> on page {pno}")
            for p in fn_paras:
                raw = clean_text("".join(p.itertext()))
                raw = re.sub(r"^\*+\)\s*", "", raw)
                footer_fn_counter += 1
                footnotes.append(f"[^{pno}-{footer_fn_counter}]: {raw}")
            continue

        if tag == "div" and ("li1" in cls_tokens or "li2" in cls_tokens):
            level = "##" if "li1" in cls_tokens else "###"
            parts = [clean_text("".join(p.itertext())) for p in child.findall(".//p")]
            heading = " ".join(p for p in parts if p)
            if not heading and clean_text("".join(child.itertext())):
                heading = clean_text("".join(child.itertext()))
            if heading:
                body_nodes.append(("heading", f"{level} {heading}"))
            continue

        if tag == "table":
            table_md, inline_fn_counter = _table_to_md(child, pno, inline_fn_counter)
            body_nodes.append(("table", table_md))
            continue

        if tag == "p":
            clone = lxml_html.fromstring(lxml_html.tostring(child, encoding="unicode"))
            for span in clone.xpath(".//span[contains(@class, 'fnsymbol')]"):
                inline_fn_counter += 1
                span.text = f"[^{pno}-{inline_fn_counter}]"
            txt = clean_text("".join(clone.itertext()))
            if not txt:
                continue
            if re.fullmatch(r"Рис\.\s*\d+\.?", txt):
                caption_map.append(txt)
            else:
                body_nodes.append(("para", txt))
            continue

        if clean_text("".join(child.itertext())) or child.xpath(".//img|.//table|.//svg"):
            raise ValueError(f"Unsupported non-empty HTML element on page {pno}: <{tag} class='{cls}'>")

    img_by_pos: dict[int, list[dict]] = {}
    for img in page_images:
        img_by_pos.setdefault(img["after_text_block_idx"], []).append(img)

    cap_idx = 0
    for idx, (_kind, content) in enumerate(body_nodes):
        if idx in img_by_pos:
            for img in img_by_pos[idx]:
                cap = caption_map[cap_idx] if cap_idx < len(caption_map) else f"Иллюстрация (стр. {pno})"
                cap_idx += 1
                lines.append("")
                lines.append(f"![{cap}](images/{img['filename']})")
                if cap.startswith("Рис."):
                    lines.append(f"*{cap}*")
        lines.append("")
        lines.append(content)

    for pos, imgs in sorted(img_by_pos.items()):
        if pos >= len(body_nodes):
            for img in imgs:
                cap = caption_map[cap_idx] if cap_idx < len(caption_map) else f"Иллюстрация (стр. {pno})"
                cap_idx += 1
                lines.append("")
                lines.append(f"![{cap}](images/{img['filename']})")
                if cap.startswith("Рис."):
                    lines.append(f"*{cap}*")

    if footnotes:
        lines.append("")
        lines.extend(footnotes)

    return "\n".join(lines).strip()


def build_markdown(
    *,
    html_path: Path,
    mineru_json_path: Path,
    jpg_dir: Path,
    out_dir: Path,
    page_numbers: list[int],
    output_filename: str | None = None,
    source_page_numbers: list[int] | None = None,
) -> tuple[Path, list[str]]:
    """Build Markdown file with cropped MinerU figures for the given pages."""
    if not page_numbers:
        raise ValueError("No pages requested")
    doc = lxml_html.fromstring(html_path.read_text(encoding="utf-8"))
    selected = {}
    for pno in page_numbers:
        els = doc.xpath(f"//div[contains(concat(' ',normalize-space(@class),' '),' page-html ') and @data-rel='{pno}']")
        if len(els) != 1 or els[0].find(".//div[@class='pagebox']") is None:
            raise ValueError(f"Missing or ambiguous HTML page/pagebox: {pno}")
        selected[pno] = els[0]
    images_dir = out_dir / "images"

    per_page_images = crop_mineru_images(
        mineru_json_path=mineru_json_path,
        jpg_dir=jpg_dir,
        page_numbers=page_numbers,
        images_out_dir=images_dir,
        source_page_numbers=source_page_numbers,
    )

    sections: list[str] = []
    for pno in page_numbers:
        sections.append(html_page_to_md(selected[pno], pno, per_page_images.get(pno, [])))

    if output_filename is None:
        output_filename = f"sample_p{page_numbers[0]:03d}_{page_numbers[-1]:03d}.md"
    md_path = out_dir / output_filename
    md_path.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
    images = sorted(img["filename"] for figures in per_page_images.values() for img in figures)
    return md_path, images


def main(argv: list[str] | None = None) -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Merge mathedu HTML with MinerU figure crops into Markdown.")
    parser.add_argument("--pages", default="13-16", help="Page range/list, e.g. '13-16' or '13,14,16'")
    parser.add_argument(
        "--source-pages", help="Original MinerU source pages in index order (defaults to JSON metadata)"
    )
    parser.add_argument("--html", type=Path, default=root / "data" / "htmldoc.html")
    parser.add_argument("--mineru-json", type=Path, default=root / "data" / "mineru_test" / "res7_json.json")
    parser.add_argument("--jpg-dir", type=Path, default=root / "data" / "sample_jpgs")
    parser.add_argument("--out-dir", type=Path, default=root / "data" / "sample_md")
    parser.add_argument("--output-name", default=None)
    args = parser.parse_args(argv)

    md_path, images = build_markdown(
        html_path=args.html,
        mineru_json_path=args.mineru_json,
        jpg_dir=args.jpg_dir,
        out_dir=args.out_dir,
        page_numbers=parse_page_spec(args.pages),
        source_page_numbers=parse_page_spec(args.source_pages, preserve_order=True) if args.source_pages else None,
        output_filename=args.output_name,
    )
    print(f"Wrote {md_path} ({md_path.stat().st_size} bytes)")
    print("Images:", images)


if __name__ == "__main__":
    main()
