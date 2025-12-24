#!/usr/bin/env python
import argparse
import hashlib
import os
import random
import re
import sys
import time
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen


BASE = "https://backpackbattles.wiki.gg"
JINA_BASE = "https://r.jina.ai/http://backpackbattles.wiki.gg"

AD_PATTERNS = (
    "app.wiki.gg/showcase",
    "utm_campaign=",
)

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")


def fetch(url, retries=5, base_delay=1.0, headers=None):
    last_exc = None
    for attempt in range(retries + 1):
        try:
            req_headers = {"User-Agent": "Mozilla/5.0"}
            if headers:
                req_headers.update(headers)
            req = Request(url, headers=req_headers)
            with urlopen(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            last_exc = exc
            if attempt >= retries:
                break
            sleep_s = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(sleep_s)
    raise last_exc


def extract_markdown(jina_text):
    marker = "Markdown Content:"
    if marker in jina_text:
        return jina_text.split(marker, 1)[1].strip()
    return jina_text.strip()


def to_local_slug(url):
    parsed = urlparse(url)
    if parsed.path in ("/zh", "/zh/"):
        return "index"
    if parsed.path.startswith("/zh/wiki/"):
        slug = parsed.path[len("/zh/wiki/") :]
        if not slug:
            return "index"
        return slug.replace("/", "__")
    return None


def local_href(url):
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if base != BASE:
        return None
    slug = to_local_slug(url)
    if not slug:
        return None
    anchor = f"#{parsed.fragment}" if parsed.fragment else ""
    if slug == "index":
        return f"index.html{anchor}"
    return f"pages/{slug}.html{anchor}"


def should_drop_line(line):
    for pat in AD_PATTERNS:
        if pat in line:
            return True
    return False


def clean_ads(markdown):
    lines = []
    for line in markdown.splitlines():
        if should_drop_line(line):
            continue
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


def is_image_url(url):
    lower = url.lower()
    return lower.startswith("http") and lower.split("?", 1)[0].endswith(IMAGE_EXTS)


def image_filename(url):
    parsed = urlparse(url)
    path = parsed.path
    ext = os.path.splitext(path)[1]
    if not ext:
        ext = ".bin"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return f"{digest}{ext}"


def download_image(url, dest_dir, retries=5, base_delay=1.0):
    os.makedirs(dest_dir, exist_ok=True)
    filename = image_filename(url)
    dest_path = os.path.join(dest_dir, filename)
    if os.path.exists(dest_path):
        return dest_path
    last_exc = None
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=60) as resp:
                data = resp.read()
            break
        except Exception as exc:
            last_exc = exc
            if attempt >= retries:
                raise last_exc
            sleep_s = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(sleep_s)
    with open(dest_path, "wb") as f:
        f.write(data)
    return dest_path


def localize_images(markdown, assets_dir):
    def repl(match):
        url = match.group(2)
        if not is_image_url(url):
            return match.group(0)
        local_path = download_image(url, assets_dir)
        rel = os.path.relpath(local_path, "content").replace("\\", "/")
        return f"![{match.group(1)}]({rel})"

    pattern = re.compile(r"!\[([^\]]*)\]\((https?://[^)]+)\)")
    return pattern.sub(lambda m: repl(m), markdown)


def rewrite_links(markdown):
    def repl(match):
        text = match.group(1)
        url = match.group(2)
        if url.startswith("http://") or url.startswith("https://"):
            local = local_href(url)
            if local:
                return f"[{text}]({local})"
        return match.group(0)

    pattern = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
    return pattern.sub(lambda m: repl(m), markdown)


def rewrite_html_links(html):
    def normalize_href(href):
        if href.startswith("//"):
            return f"https:{href}"
        if href.startswith("/zh/wiki/"):
            return f"{BASE}{href}"
        if href.startswith("/"):
            return f"{BASE}{href}"
        return href

    def repl(match):
        href = match.group(1)
        if href.startswith("#"):
            return match.group(0)
        normalized = normalize_href(href)
        local = local_href(normalized)
        if local:
            return f'href="{local}"'
        return match.group(0)

    pattern = re.compile(r'href="([^"]+)"')
    return pattern.sub(lambda m: repl(m), html)


def add_action_render(url):
    if "action=render" in url:
        return url
    if "?" in url:
        return f"{url}&action=render"
    return f"{url}?action=render"


def process_page(page_url, out_dir, assets_dir, cookies=None, user_agent="", use_jina=True):
    headers = {}
    if cookies:
        headers["Cookie"] = cookies
        headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        headers["Accept-Language"] = "zh-CN,zh;q=0.9,en;q=0.8"
        headers["Cache-Control"] = "no-cache"
        headers["Pragma"] = "no-cache"
        headers["Referer"] = page_url
    if user_agent:
        headers["User-Agent"] = user_agent

    if use_jina:
        jina_url = f"{JINA_BASE}{urlparse(page_url).path}"
        if urlparse(page_url).query:
            jina_url = f"{jina_url}?{urlparse(page_url).query}"
        raw = fetch(jina_url, headers=headers)
        markdown = extract_markdown(raw)
        markdown = clean_ads(markdown)
        markdown = localize_images(markdown, assets_dir)
        markdown = rewrite_links(markdown)
    else:
        render_url = add_action_render(page_url)
        html = fetch(render_url, headers=headers)
        html = rewrite_html_links(html)
        markdown = f"<!-- source: action=render -->\n\n{html.strip()}\n"

    slug = to_local_slug(page_url)
    if slug == "index":
        out_path = os.path.join(out_dir, "index.md")
    else:
        out_path = os.path.join(out_dir, "pages", f"{slug}.md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(markdown)


def main():
    parser = argparse.ArgumentParser(description="Fetch wiki pages via jina.ai")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of pages")
    parser.add_argument("--resume", action="store_true", help="Resume from data/progress.txt")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between requests")
    parser.add_argument("--cookie-file", default="", help="Cookie string file for origin requests")
    parser.add_argument("--user-agent", default="", help="User-Agent override for origin requests")
    parser.add_argument("--blocked-only", action="store_true", help="Only refetch blocked pages")
    args = parser.parse_args()

    cookies = ""
    if args.cookie_file:
        try:
            with open(args.cookie_file, "r", encoding="utf-8") as f:
                cookies = f.read().strip()
        except Exception:
            cookies = ""
    user_agent = args.user_agent.strip()

    with open("data/pages.txt", "r", encoding="utf-8") as f:
        pages = [line.strip() for line in f if line.strip()]

    out_dir = "content"
    assets_dir = os.path.join(out_dir, "assets", "images")
    os.makedirs(out_dir, exist_ok=True)

    start_index = 0
    progress_path = os.path.join("data", "progress.txt")
    if args.resume and os.path.exists(progress_path):
        try:
            with open(progress_path, "r", encoding="utf-8") as f:
                start_index = int(f.read().strip() or "0")
        except Exception:
            start_index = 0

    if args.blocked_only:
        blocked_path = os.path.join("data", "blocked_pages.txt")
        if not os.path.exists(blocked_path):
            print("Blocked list not found: data/blocked_pages.txt", file=sys.stderr)
            sys.exit(1)
        blocked_urls = []
        with open(blocked_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("\t", 1)
                if len(parts) == 2 and parts[1]:
                    blocked_urls.append(parts[1])
        pages = blocked_urls
        start_index = 0

    count = 0
    blocked_phrase = "review the security of your browser and network"
    for idx, page_url in enumerate(pages[start_index:], start=start_index):
        slug = to_local_slug(page_url)
        if slug == "index":
            out_path = os.path.join(out_dir, "index.md")
        else:
            out_path = os.path.join(out_dir, "pages", f"{slug}.md")
        if not args.blocked_only and os.path.exists(out_path):
            count += 1
            continue
        if args.blocked_only and os.path.exists(out_path):
            try:
                with open(out_path, "r", encoding="utf-8", errors="ignore") as f:
                    if blocked_phrase not in f.read(2000):
                        count += 1
                        continue
            except Exception:
                pass

        use_jina = not args.blocked_only
        process_page(
            page_url,
            out_dir,
            assets_dir,
            cookies=cookies,
            user_agent=user_agent,
            use_jina=use_jina,
        )
        count += 1
        if not args.blocked_only:
            with open(progress_path, "w", encoding="utf-8") as f:
                f.write(str(idx + 1))
        if args.limit and count >= args.limit:
            break
        if count % 25 == 0:
            print(f"Processed: {count} (last index {idx + 1})")
        time.sleep(args.delay)

    print(f"Processed pages: {count}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
