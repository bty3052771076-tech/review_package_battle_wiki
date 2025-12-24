#!/usr/bin/env python
import html
import json
import re
from pathlib import Path
from urllib.parse import unquote


CONTENT_PAGES_DIR = Path("content") / "pages"
OUTPUT_DIR = Path("search")
SITE_OUTPUT_DIR = Path("site") / "search"


def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(text)


def strip_markdown(text):
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


def normalize_text(text):
    text = strip_markdown(text)
    text = strip_html(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_title(markdown_text, slug):
    for line in markdown_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    match = re.search(r'<span class="name">([^<]+)</span>', markdown_text)
    if match:
        return match.group(1).strip()
    match = re.search(r"<h1[^>]*>(.*?)</h1>", markdown_text, re.IGNORECASE | re.DOTALL)
    if match:
        return normalize_text(match.group(1)) or unquote(slug)
    return unquote(slug)


def is_safe_filename(name):
    if not name:
        return False
    if name.endswith((" ", ".")):
        return False
    for ch in name:
        if ord(ch) < 32:
            return False
        if ch in '<>:"/\\|?*':
            return False
    return True


def build_slug_map(slugs):
    mapping = {}
    used = set()
    for slug in slugs:
        decoded = unquote(slug)
        candidate = decoded if is_safe_filename(decoded) else slug
        if candidate in used:
            candidate = slug
        if candidate in used:
            candidate = f"{slug}__dup"
        mapping[slug] = candidate
        used.add(candidate)
    return mapping


def detect_type(slug, title):
    if slug.startswith("File:"):
        return "file"
    if re.match(r"^\d+(?:\.\d+)+(?:[a-z])?$", slug):
        return "version"
    if "版本" in title or "Version" in title:
        return "version"
    if "配方" in title or "Recipe" in title or "合成" in title:
        return "recipe"
    if "角色" in title:
        return "character"
    if "机制" in title or "Mechanic" in title:
        return "mechanic"
    if "物品" in title:
        return "item"
    return "page"


def extract_tags(title, page_type):
    tokens = set()
    tokens.add(title)
    for part in re.split(r"[\s_\-]+", title):
        part = part.strip()
        if len(part) > 1:
            tokens.add(part)
    if page_type != "page":
        tokens.add(page_type)
    return sorted(tokens)


def build_index():
    items = []
    paths = sorted(CONTENT_PAGES_DIR.glob("*.md"))
    slug_map = build_slug_map([path.stem for path in paths])
    for path in paths:
        slug = path.stem
        markdown_text = path.read_text(encoding="utf-8", errors="replace")
        title = extract_title(markdown_text, slug)
        plain = normalize_text(markdown_text)
        summary = plain[:160]
        page_type = detect_type(slug, title)
        tags = extract_tags(title, page_type)
        output_name = slug_map[slug]
        items.append(
            {
                "title": title,
                "url": f"pages/{output_name}.html",
                "summary": summary,
                "tags": tags,
                "type": page_type,
            }
        )
    return items


def write_index(items):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SITE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"count": len(items), "items": items}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    (OUTPUT_DIR / "index.json").write_text(text, encoding="utf-8")
    (SITE_OUTPUT_DIR / "index.json").write_text(text, encoding="utf-8")


def main():
    items = build_index()
    write_index(items)
    print(f"Wrote {len(items)} items")


if __name__ == "__main__":
    main()
