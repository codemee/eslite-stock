# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案結構

- `eslite_stock.py` — 誠品庫存查詢 CLI 工具（PEP 723 獨立腳本）
- `pyproject.toml` — 專案元數據與相依套件宣告
- `uv.lock` — 鎖定的相依套件版本

## 執行方式

`uv run` 直接執行，首次執行自動安裝相依套件，無需 `uv sync`。

```bash
uv run eslite_stock.py <GUID或URL> [--watch 秒] [--json]
```

## 相依套件

- `curl-cffi>=0.7`（模擬 Chrome TLS 指紋）
- `rich>=13`

## 關鍵設計

- **curl-cffi + `impersonate="chrome120"`**：API 後端有 Cloudflare 防護，`httpx`/`requests` 會被 403，須模擬真實瀏覽器 TLS 指紋
- **`datetime` 查詢參數**：API 要求每次請求帶入格式 `YYYYMMDDHHmmss` 的當前時間戳
- **GUID 提取**：`_GUID_RE = re.compile(r"\d{20,}")` 可從商品頁 URL 或純 GUID 字串中自動提取

## uv 套件管理常用指令

```bash
uv add <package>          # 新增套件至 pyproject.toml
uv add --dev <package>    # 新增開發用套件
uv remove <package>       # 移除套件
uv lock                   # 更新 uv.lock
```
