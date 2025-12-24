# 使用说明（本地离线版）

## 1. 打开站点
- 直接双击 `site/index.html`。
- 搜索入口：`site/search.html`。

## 1.1 在 localhost:8000 启动本地服务（便于 BrowserMCP）
```powershell
.\.venv\Scripts\python.exe -m http.server 8000
```
默认以当前目录为根目录，请在 `site/` 目录中运行该命令。

## 2. 重新生成静态站点
在工作区根目录执行：
```powershell
.\.venv\Scripts\python.exe .\build_site.py
```

## 3. 重新生成搜索索引
```powershell
.\.venv\Scripts\python.exe .\build_search_index.py
```

## 4. 重新抓取内容（可选）
```powershell
.\.venv\Scripts\python.exe .\fetch_pages.py --resume
.\.venv\Scripts\python.exe .\postprocess_markdown.py --download-images --resume
```

