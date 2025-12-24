#!/usr/bin/env python
import json
import re
import sys
import time
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen


BASE = "https://backpackbattles.wiki.gg"
JINA_BASE = "https://r.jina.ai/http://backpackbattles.wiki.gg"
API = "/zh/api.php?action=query&list=allpages&apnamespace=0&aplimit=500&format=json"


def fetch(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def main():
    pages = set()
    page_count = 0
    cont = None

    while True:
        url = f"{JINA_BASE}{API}"
        if cont:
            url = f"{url}&apcontinue={quote(cont)}"
        raw = fetch(url)
        if "Markdown Content:" in raw:
            raw = raw.split("Markdown Content:", 1)[1].strip()

        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Unexpected API response format")

        data = json.loads(raw[start : end + 1])
        items = data.get("query", {}).get("allpages", [])
        for item in items:
            title = item.get("title")
            if not title:
                continue
            slug = quote(title.replace(" ", "_"))
            pages.add(urljoin(BASE, f"/zh/wiki/{slug}"))

        pages.add("https://backpackbattles.wiki.gg/zh/")

        cont = data.get("continue", {}).get("apcontinue")
        page_count += 1
        if not cont:
            break
        time.sleep(0.2)

    pages = sorted(pages)
    meta = {
        "source": urljoin(JINA_BASE, API),
        "pagination_pages": page_count,
        "page_count": len(pages),
    }

    with open("data/pages.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(pages))
        f.write("\n")

    with open("data/pages.json", "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "pages": pages}, f, ensure_ascii=False, indent=2)

    print(f"Pages: {len(pages)}")
    print(f"Pagination pages: {page_count}")


if __name__ == "__main__":
    try:
        import os

        os.makedirs("data", exist_ok=True)
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
