#!/usr/bin/env python
import html
import json
import re
import shutil
from pathlib import Path
from urllib.parse import unquote

import markdown


CONTENT_DIR = Path("content")
PAGES_DIR = CONTENT_DIR / "pages"
ASSETS_DIR = CONTENT_DIR / "assets"
OUTPUT_DIR = Path("site")
SITE_PAGES_DIR = OUTPUT_DIR / "pages"
SITE_ASSETS_DIR = OUTPUT_DIR / "assets"
SITE_CSS_DIR = SITE_ASSETS_DIR / "css"
SITE_JS_DIR = SITE_ASSETS_DIR / "js"
SPECIAL_LINK_PATTERN = re.compile(
    r'href="(?:\./|\.\./)?pages/(?:Special|Talk|Template|Template_talk|Category):[^"]+"'
)
JS_LINK_PATTERN = re.compile(r'href="javascript:[^"]*"')

SITE_TITLE = "Backpack Battles 中文 Wiki"
CSS_TEXT = """\
:root {
  color-scheme: light;
  --bg: #f8f6f1;
  --panel: #ffffff;
  --ink: #221a14;
  --muted: #7a6a5f;
  --accent: #9b3b2f;
  --line: #e1d6c9;
  --shadow: 0 12px 30px rgba(34, 26, 20, 0.08);
  --radius: 14px;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: "Source Han Sans SC", "Noto Sans CJK SC", "Noto Sans", "PingFang SC", "Microsoft YaHei", sans-serif;
  background: radial-gradient(circle at top, #fbf7f0 0%, #f4efe6 45%, #ece4d6 100%);
  color: var(--ink);
  line-height: 1.6;
}

a {
  color: var(--accent);
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

.site-header {
  padding: 28px clamp(16px, 4vw, 48px);
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(6px);
  position: sticky;
  top: 0;
  z-index: 10;
}

.site-title {
  font-family: "Source Han Serif SC", "Noto Serif CJK SC", "Noto Serif", "STSong", serif;
  font-size: clamp(22px, 3vw, 32px);
  margin: 0;
  letter-spacing: 0.5px;
}

.layout {
  display: grid;
  grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
  gap: clamp(16px, 4vw, 36px);
  padding: clamp(16px, 4vw, 48px);
}

.sidebar {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 20px;
  align-self: start;
  position: sticky;
  top: 110px;
}

.sidebar h2 {
  font-size: 16px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--muted);
  margin: 0 0 12px;
}

.sidebar ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 8px;
}

.content {
  background: var(--panel);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: clamp(20px, 4vw, 40px);
  border: 1px solid var(--line);
}

.content h1,
.content h2,
.content h3,
.content h4 {
  font-family: "Source Han Serif SC", "Noto Serif CJK SC", "Noto Serif", "STSong", serif;
  color: #2c2219;
}

.content img {
  max-width: 100%;
  height: auto;
}

.content table {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
}

.content th,
.content td {
  border: 1px solid var(--line);
  padding: 8px 10px;
  text-align: left;
}

.site-footer {
  padding: 16px clamp(16px, 4vw, 48px) 32px;
  color: var(--muted);
  font-size: 13px;
}

@media (max-width: 960px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .sidebar {
    position: static;
  }
}
"""

BASE_TEMPLATE = """\
<!doctype html>
<html lang="zh-Hans">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <link rel="stylesheet" href="{base_path}/assets/css/site.css" />
  </head>
  <body>
    <header class="site-header">
      <h1 class="site-title">{site_title}</h1>
    </header>
    <div class="layout">
      <nav class="sidebar">
        <h2>导航</h2>
        <ul>
          <li><a href="{base_path}/index.html">首页</a></li>
          <li><a href="{base_path}/all-pages.html">全站索引</a></li>
          <li><a href="{base_path}/search.html">搜索</a></li>
        </ul>
        <p style="margin-top:16px; color: var(--muted); font-size: 13px;">共 {page_count} 页</p>
      </nav>
      <main class="content">
        {content}
      </main>
    </div>
    <footer class="site-footer">离线版本，仅供本地阅读。</footer>
  </body>
</html>
"""


def ensure_dirs():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SITE_PAGES_DIR.mkdir(parents=True, exist_ok=True)
    SITE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    SITE_CSS_DIR.mkdir(parents=True, exist_ok=True)
    SITE_JS_DIR.mkdir(parents=True, exist_ok=True)


def write_css():
    (SITE_CSS_DIR / "site.css").write_text(CSS_TEXT, encoding="utf-8")


def write_search_js():
    script = """\
(() => {
  const input = document.querySelector('[data-search-input]');
  const results = document.querySelector('[data-search-results]');
  if (!input || !results) return;

  let index = [];
  fetch('search/index.json')
    .then((res) => res.json())
    .then((data) => {
      index = data.items || [];
    })
    .catch(() => {
      results.innerHTML = '<p>索引加载失败。</p>';
    });

  const render = (items) => {
    if (!items.length) {
      results.innerHTML = '<p>没有匹配结果。</p>';
      return;
    }
    const html = items
      .slice(0, 50)
      .map((item) => {
        const tags = item.tags ? item.tags.join('、') : '';
        return `
          <article style="padding:12px 0; border-bottom:1px solid var(--line);">
            <h3 style="margin:0 0 4px;"><a href="${item.url}">${item.title}</a></h3>
            <p style="margin:0 0 6px; color: var(--muted);">${item.summary || ''}</p>
            <div style="font-size:12px; color: var(--muted);">类型：${item.type || 'page'}${tags ? `｜标签：${tags}` : ''}</div>
          </article>
        `;
      })
      .join('');
    results.innerHTML = html;
  };

  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();
    if (!q) {
      results.innerHTML = '<p>输入关键词开始搜索。</p>';
      return;
    }
    const matched = index.filter((item) => {
      const hay = `${item.title} ${item.summary || ''} ${(item.tags || []).join(' ')} ${item.type || ''}`.toLowerCase();
      return hay.includes(q);
    });
    render(matched);
  });
})();
"""
    (SITE_JS_DIR / "search.js").write_text(script, encoding="utf-8")


def copy_images():
    src = ASSETS_DIR / "images"
    dst = SITE_ASSETS_DIR / "images"
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def render_markdown(text, md):
    md.reset()
    return md.convert(text)


def strip_tags(text):
    return re.sub(r"<[^>]+>", "", text or "")


def extract_title(markdown_text, html_text, fallback):
    for line in markdown_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    match = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, re.IGNORECASE | re.DOTALL)
    if match:
        return strip_tags(match.group(1)).strip()
    return fallback


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


def rewrite_page_links(html_text, slug_map):
    pattern = re.compile(r'([./]*pages/)([^"/?#]+)\.html')

    def repl(match):
        prefix = match.group(1)
        slug = match.group(2)
        target = slug_map.get(slug, slug)
        return f"{prefix}{target}.html"

    return pattern.sub(repl, html_text)


def rewrite_relative_links(html_text, base_path):
    if base_path == ".":
        return html_text
    html_text = re.sub(r'href="\\./pages/', 'href="../pages/', html_text)
    html_text = re.sub(r'href="pages/', 'href="../pages/', html_text)
    html_text = re.sub(r'href="index.html"', 'href="../index.html"', html_text)
    html_text = re.sub(r'href="all-pages.html"', 'href="../all-pages.html"', html_text)
    html_text = re.sub(r'href="assets/', 'href="../assets/', html_text)
    html_text = re.sub(r'href="\\./assets/', 'href="../assets/', html_text)
    html_text = re.sub(r'src="assets/', 'src="../assets/', html_text)
    html_text = re.sub(r'src="\\./assets/', 'src="../assets/', html_text)
    html_text = SPECIAL_LINK_PATTERN.sub('href="#"', html_text)
    html_text = JS_LINK_PATTERN.sub('href="#"', html_text)
    return html_text


def strip_missing_images(html_text):
    def repl(match):
        tag = match.group(0)
        src_match = re.search(r'src="([^"]+)"', tag)
        if not src_match:
            return tag
        src = src_match.group(1)
        if src.startswith(("http://", "https://", "data:")):
            return tag
        normalized = src.replace("../", "").replace("./", "")
        if not normalized.startswith("assets/images/"):
            return tag
        rel_path = normalized[len("assets/") :]
        target = ASSETS_DIR / rel_path
        if target.exists():
            return tag
        return ""

    return re.sub(r"<img\b[^>]*>", repl, html_text)


def wrap_page(title, content_html, base_path, page_count):
    return BASE_TEMPLATE.format(
        title=html.escape(title),
        site_title=html.escape(SITE_TITLE),
        content=content_html,
        base_path=base_path,
        page_count=page_count,
    )


def strip_unsupported_links(html_text):
    html_text = SPECIAL_LINK_PATTERN.sub('href="#"', html_text)
    html_text = JS_LINK_PATTERN.sub('href="#"', html_text)
    return html_text


def build_all_pages(pages_meta):
    items = []
    for slug, title in pages_meta:
        items.append(f'<li><a href="pages/{slug}.html">{html.escape(title)}</a></li>')
    return "<h2>全站索引</h2>\n<ul>\n" + "\n".join(items) + "\n</ul>"


def load_pages_list():
    pages_json = Path("data") / "pages.json"
    if not pages_json.exists():
        return []
    data = json.loads(pages_json.read_text(encoding="utf-8"))
    pages = data.get("pages", [])
    return pages


def main():
    ensure_dirs()
    write_css()
    write_search_js()
    copy_images()

    md = markdown.Markdown(extensions=["tables", "fenced_code"])

    pages = sorted(PAGES_DIR.glob("*.md"))
    slug_map = build_slug_map([path.stem for path in pages])
    page_count = len(pages) + 1
    page_meta = []

    for path in pages:
        slug = path.stem
        output_name = slug_map[slug]
        markdown_text = path.read_text(encoding="utf-8", errors="replace")
        html_text = render_markdown(markdown_text, md)
        fallback = unquote(slug)
        title = extract_title(markdown_text, html_text, fallback)
        page_meta.append((output_name, title))

        html_text = rewrite_relative_links(html_text, "..")
        html_text = rewrite_page_links(html_text, slug_map)
        html_text = strip_missing_images(html_text)
        page_html = wrap_page(title, html_text, "..", page_count)
        page_html = strip_unsupported_links(page_html)
        (SITE_PAGES_DIR / f"{output_name}.html").write_text(page_html, encoding="utf-8")

    index_path = CONTENT_DIR / "index.md"
    if index_path.exists():
        index_md = index_path.read_text(encoding="utf-8", errors="replace")
        index_html = render_markdown(index_md, md)
    else:
        index_html = "<h2>首页缺失</h2><p>未找到 content/index.md。</p>"
    index_html = rewrite_relative_links(index_html, ".")
    index_html = rewrite_page_links(index_html, slug_map)
    index_html = strip_missing_images(index_html)
    index_page = wrap_page(SITE_TITLE, index_html, ".", page_count)
    index_page = strip_unsupported_links(index_page)
    (OUTPUT_DIR / "index.html").write_text(index_page, encoding="utf-8")

    page_meta.sort(key=lambda item: item[1].casefold())
    all_pages_html = build_all_pages(page_meta)
    all_pages_page = wrap_page("全站索引", all_pages_html, ".", page_count)
    all_pages_page = strip_unsupported_links(all_pages_page)
    (OUTPUT_DIR / "all-pages.html").write_text(all_pages_page, encoding="utf-8")

    search_html = """
<h2>搜索</h2>
<p>输入关键词即可筛选标题、摘要、标签与类型。</p>
<input data-search-input type="search" placeholder="搜索关键词..." style="width:100%; padding:10px 12px; border-radius:10px; border:1px solid var(--line); margin-bottom:12px;" />
<div data-search-results><p>输入关键词开始搜索。</p></div>
<script src="assets/js/search.js"></script>
"""
    search_page = wrap_page("搜索", search_html.strip(), ".", page_count)
    search_page = strip_unsupported_links(search_page)
    (OUTPUT_DIR / "search.html").write_text(search_page, encoding="utf-8")


if __name__ == "__main__":
    main()
