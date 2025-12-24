# Review Package Battle Wiki (Backpack Battles)

Offline mirror and static site build for the Backpack Battles wiki content.

## Contents
- Fetches and postprocesses wiki pages.
- Builds a static site under `site/`.
- Generates a local search index under `search/`.

## Requirements
- Windows + PowerShell
- Python (use the `.venv` virtual environment created in this repo)

## Quick Start
Open the generated site:
- Double-click `site/index.html`.
- Search entry: `site/search.html`.

Serve locally (optional):
```powershell
.\.venv\Scripts\python.exe -m http.server 8000
```
Run that command inside `site/`.

## Rebuild
Rebuild the static site:
```powershell
.\.venv\Scripts\python.exe .\build_site.py
```

Rebuild the search index:
```powershell
.\.venv\Scripts\python.exe .\build_search_index.py
```

Refresh content (optional):
```powershell
.\.venv\Scripts\python.exe .\fetch_pages.py --resume
.\.venv\Scripts\python.exe .\postprocess_markdown.py --download-images --resume
```

## Repo Layout
- `content/`: postprocessed wiki content
- `data/`: page lists and metadata
- `search/`: search index assets
- `site/`: generated static site output
- `build_site.py`: site generation
- `build_search_index.py`: search index generation
