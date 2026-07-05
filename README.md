# eslite-stock

誠品線上庫存查詢 CLI 工具，支援單次查詢、多商品同查、持續監控與 JSON 輸出。

## 需求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

## 使用方式

不需要安裝，直接用 `uv run` 執行，相依套件會自動處理：

```bash
uv run eslite_stock.py <GUID 或商品頁 URL>
```

### 取得商品 GUID

從誠品商品頁網址複製 20 位數字即為 GUID，例如：

```
https://www.eslite.com/product/10012013492683166052007
                                ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
```

### 範例

```bash
# 查詢單一商品（GUID）
uv run eslite_stock.py 10012013492683166052007

# 查詢單一商品（完整 URL）
uv run eslite_stock.py https://www.eslite.com/product/10012013492683166052007

# 同時查詢多個商品
uv run eslite_stock.py 10012013492683166052007 10012013492683166052008

# 每 60 秒持續監控（Ctrl+C 結束）
uv run eslite_stock.py 10012013492683166052007 --watch 60

# 輸出原始 JSON（供管線或程式使用）
uv run eslite_stock.py 10012013492683166052007 --json
uv run eslite_stock.py 10012013492683166052007 --json | python -m json.tool
```

### 輸出範例

```
Claude Code Vibe Coding開發手冊 (第2版)
  庫　　存：1
  購買狀態：可加入購物車
  定　　價：850
  售　　價：671.0
  查詢時間：2026-06-29 14:51:13
```

## 選項

| 選項 | 說明 |
|------|------|
| `--watch 秒` | 每隔指定秒數重新查詢，持續刷新畫面 |
| `--json` | 輸出完整原始 JSON，不進行格式化 |

## 技術細節

背後如何繞過 Cloudflare 防護、組出可用的 API 請求等實作細節，請參閱 [TECHNICAL_REPORT.md](./TECHNICAL_REPORT.md)。

