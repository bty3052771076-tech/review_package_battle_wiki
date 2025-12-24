#!/usr/bin/env python
import argparse
import hashlib
import os
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE = "https://backpackbattles.wiki.gg"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico")


def fetch_bytes(url, retries=1, base_delay=0.3, headers=None, timeout=15):
    last_exc = None
    for attempt in range(retries + 1):
        try:
            req_headers = {"User-Agent": "Mozilla/5.0"}
            if headers:
                req_headers.update(headers)
            req = Request(url, headers=req_headers)
            with urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except HTTPError as exc:
            if exc.code == 403:
                return None
            last_exc = exc
        except Exception as exc:
            last_exc = exc
            if attempt >= retries:
                break
            sleep_s = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(sleep_s)
    if last_exc:
        raise last_exc
    return None


def is_image_url(url):
    lower = url.lower()
    return lower.startswith("http") and lower.split("?", 1)[0].endswith(IMAGE_EXTS)


def normalize_image_url(url):
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("/"):
        return f"{BASE}{url}"
    return url


def image_filename(url):
    parsed = urlparse(url)
    path = parsed.path
    ext = os.path.splitext(path)[1]
    if not ext:
        ext = ".bin"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return f"{digest}{ext}"


def download_image(url, dest_dir, headers=None):
    os.makedirs(dest_dir, exist_ok=True)
    filename = image_filename(url)
    dest_path = os.path.join(dest_dir, filename)
    if os.path.exists(dest_path):
        return dest_path
    data = fetch_bytes(url, headers=headers)
    if not data:
        raise ValueError("Image download blocked")
    with open(dest_path, "wb") as f:
        f.write(data)
    if Path(dest_path).read_bytes()[:6] == b"Title:":
        os.remove(dest_path)
        raise ValueError("Downloaded non-image content")
    return dest_path


def local_href(url):
    parsed = urlparse(url)
    if parsed.query:
        return None
    if "/zh/wiki/Special:" in parsed.path:
        return None
    if parsed.netloc != urlparse(BASE).netloc:
        return None
    if parsed.path in ("/zh", "/zh/"):
        return "index.html"
    if parsed.path.startswith("/zh/wiki/"):
        slug = parsed.path[len("/zh/wiki/") :].replace("/", "__")
        anchor = f"#{parsed.fragment}" if parsed.fragment else ""
        return f"pages/{slug}.html{anchor}"
    return None


def fix_broken_local_links(text):
    text = re.sub(r"\((pages/[^)\s]+)\s+\"[^\"]*\"\.html\)", r"(\1.html)", text)
    text = re.sub(r"\((index)\s+\"[^\"]*\"\.html\)", r"(\1.html)", text)
    return text


def restore_special_links(text):
    def repl(match):
        label = match.group(1)
        slug = match.group(2)
        return f"[{label}](https://backpackbattles.wiki.gg/zh/wiki/Special:{slug})"

    image_pattern = re.compile(
        r"\[(!\[[^\]]*\]\([^)]+\))\]\(pages/Special:([^)\s]+)\.html(?:\s+\"[^\"]+\")?\)"
    )
    text = image_pattern.sub(lambda m: repl(m), text)

    pattern = re.compile(r"\[([^\]]+)\]\(pages/Special:([^)\s]+)\.html\)")
    return pattern.sub(lambda m: repl(m), text)


def remove_empty_links(text):
    return re.sub(r"\[\]\([^)]+\)", "", text)


def separate_adjacent_links(text):
    return re.sub(r"\)\[", ") [", text)


def localize_images(text, file_path, assets_dir, download_images, headers):
    def localize_url(url):
        normalized = normalize_image_url(url)
        if normalized.startswith("blob:") or normalized.startswith("data:"):
            return ""
        if not is_image_url(normalized):
            return url
        if not download_images:
            return url
        try:
            local_path = download_image(normalized, assets_dir, headers=headers)
            return os.path.relpath(local_path, os.path.dirname(file_path)).replace("\\", "/")
        except Exception:
            return url

    def repl(match):
        alt = match.group(1)
        url = match.group(2)
        localized = localize_url(url)
        if not localized:
            return ""
        return f"![{alt}]({localized})"

    pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    return pattern.sub(lambda m: repl(m), text)


def localize_html_images(text, file_path, assets_dir, download_images, headers):
    def replace_src(match):
        url = match.group(1)
        localized = localize_images(f"![x]({url})", file_path, assets_dir, download_images, headers)
        if localized.startswith("![x]("):
            new_url = localized[len("![x](") : -1]
            if new_url:
                return f'src="{new_url}"'
        return match.group(0)

    def replace_srcset(match):
        srcset = match.group(1)
        parts = [p.strip() for p in srcset.split(",") if p.strip()]
        rewritten = []
        for part in parts:
            if " " in part:
                url, descriptor = part.split(" ", 1)
            else:
                url, descriptor = part, ""
            localized = localize_images(f"![x]({url})", file_path, assets_dir, download_images, headers)
            if localized.startswith("![x]("):
                new_url = localized[len("![x](") : -1]
            else:
                new_url = url
            rewritten.append(f"{new_url} {descriptor}".strip())
        return f'srcset="{", ".join(rewritten)}"'

    text = re.sub(r'src="([^"]+)"', lambda m: replace_src(m), text)
    text = re.sub(r'srcset="([^"]+)"', lambda m: replace_srcset(m), text)
    return text


def rewrite_links(text):
    def repl_image_link(match):
        image = match.group(1)
        url = match.group(2)
        title = match.group(3)
        local = local_href(url)
        if local:
            if title:
                return f"[{image}]({local} \"{title}\")"
            return f"[{image}]({local})"
        return match.group(0)

    def repl(match):
        label = match.group(1)
        url = match.group(2)
        title = match.group(3)
        if url.startswith("http://") or url.startswith("https://"):
            local = local_href(url)
            if local:
                if title:
                    return f"[{label}]({local} \"{title}\")"
                return f"[{label}]({local})"
        return match.group(0)

    image_link_pattern = re.compile(r"\[(!\[[^\]]*\]\([^)]+\))\]\((\S+)(?:\s+\"([^\"]+)\")?\)")
    text = image_link_pattern.sub(lambda m: repl_image_link(m), text)

    pattern = re.compile(r"(?<!!)\[([^\]]+)\]\((\S+)(?:\s+\"([^\"]+)\")?\)")
    return pattern.sub(lambda m: repl(m), text)


def restore_invalid_local_images(text, file_path):
    def repl(match):
        alt = match.group(1)
        url = match.group(2)
        if url.startswith("http://") or url.startswith("https://"):
            return match.group(0)
        abs_path = os.path.normpath(os.path.join(os.path.dirname(file_path), url))
        if not os.path.exists(abs_path):
            return match.group(0)
        try:
            head = Path(abs_path).read_text(encoding="utf-8", errors="replace").splitlines()[:5]
        except Exception:
            return match.group(0)
        source_line = next((line for line in head if line.startswith("URL Source: ")), None)
        if not source_line:
            return match.group(0)
        source_url = source_line.replace("URL Source: ", "").strip()
        try:
            os.remove(abs_path)
        except Exception:
            pass
        return f"![{alt}]({source_url})"

    pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    return pattern.sub(lambda m: repl(m), text)


def process_file(path, assets_dir, download_images, headers):
    text = Path(path).read_text(encoding="utf-8")
    text = fix_broken_local_links(text)
    text = restore_special_links(text)
    text = remove_empty_links(text)
    text = separate_adjacent_links(text)
    text = restore_invalid_local_images(text, path)
    text = localize_images(text, path, assets_dir, download_images, headers)
    text = localize_html_images(text, path, assets_dir, download_images, headers)
    text = rewrite_links(text)
    Path(path).write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Post-process markdown files")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay between files")
    parser.add_argument("--resume", action="store_true", help="Resume from data/postprocess_progress.txt")
    parser.add_argument("--download-images", action="store_true", help="Attempt to download images")
    parser.add_argument("--cookie-file", default="", help="Cookie string file for image requests")
    parser.add_argument("--user-agent", default="", help="User-Agent override for image requests")
    args = parser.parse_args()

    headers = {}
    if args.cookie_file:
        try:
            with open(args.cookie_file, "r", encoding="utf-8") as f:
                cookie_value = f.read().strip()
            if cookie_value:
                headers["Cookie"] = cookie_value
        except Exception:
            pass
    if args.user_agent:
        headers["User-Agent"] = args.user_agent
    if args.cookie_file:
        headers["Accept"] = "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
        headers["Accept-Language"] = "zh-CN,zh;q=0.9,en;q=0.8"
        headers["Referer"] = f"{BASE}/zh/"

    assets_dir = os.path.join("content", "assets", "images")
    files = list(Path("content").rglob("*.md"))
    progress_path = os.path.join("data", "postprocess_progress.txt")
    start_index = 0
    if args.resume and os.path.exists(progress_path):
        try:
            with open(progress_path, "r", encoding="utf-8") as f:
                start_index = int(f.read().strip() or "0")
        except Exception:
            start_index = 0

    for idx, path in enumerate(files[start_index:], start=start_index + 1):
        process_file(str(path), assets_dir, args.download_images, headers)
        with open(progress_path, "w", encoding="utf-8") as f:
            f.write(str(idx))
        if args.delay:
            time.sleep(args.delay)
        if idx % 50 == 0:
            print(f"Processed {idx}/{len(files)}")
    print(f"Processed files: {len(files)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
