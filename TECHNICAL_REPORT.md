# 誠品線上庫存查詢工具 — 技術報告

## 1. 問題背景

誠品線上（eslite.com）的商品頁面雖然會顯示庫存狀態，但僅能逐一開啟網頁人工確認，無法：

- 一次查詢多筆商品
- 對限量或熱銷商品做「上架/補貨」的持續監控
- 以結構化格式（JSON）取得資料供其他程式串接

因此本專案目標是撰寫一支輕量 CLI 工具，直接呼叫誠品線上背後的商品 API，取代人工刷新網頁的行為。開發過程中遇到的核心技術問題並非「業務邏輯」，而是**如何繞過前端防護、正確組出可用的 API 請求**。以下逐項說明。

---

## 2. 核心技術問題與解法

### 2.1 Cloudflare TLS 指紋偵測導致 403

誠品線上的 API 後端（`athena.eslite.com`）架設在 Cloudflare 之後。Cloudflare 除了檢查 HTTP Header，還會在 TLS handshake 階段比對 **JA3/JA3S 指紋**（ClientHello 中的 cipher suite 順序、TLS 擴充欄位順序、支援的橢圓曲線等）。

Python 的 `requests` 或 `httpx` 底層使用 OpenSSL 產生的 TLS 指紋，與真實 Chrome 瀏覽器不同，即使把 `User-Agent` 偽裝成 Chrome，Cloudflare 仍能從 TLS 層辨識出「非瀏覽器流量」並直接回傳 `403 Forbidden`：

```python
# ❌ 會被 Cloudflare 擋下（TLS 指紋不符，即使偽造了 User-Agent）
import requests

resp = requests.get(
    "https://athena.eslite.com/api/v1/products/10012013492683166052007",
    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"},
)
print(resp.status_code)  # 403
```

**解法**：改用 [`curl-cffi`](https://github.com/yifeikong/curl-cffi)，它底層綁定 curl-impersonate，能重現特定瀏覽器版本（如 Chrome 120）的實際 TLS/HTTP2 指紋，而非只偽造 Header：

```python
# ✅ curl-cffi 以 impersonate 參數重現真實 Chrome 的 TLS 指紋
from curl_cffi import requests as cffi_requests

resp = cffi_requests.get(
    "https://athena.eslite.com/api/v1/products/10012013492683166052007",
    headers={"Accept": "application/json", "Referer": "https://www.eslite.com/"},
    impersonate="chrome120",
    timeout=10,
)
resp.raise_for_status()
```

`impersonate="chrome120"` 這行是整個工具能否運作的關鍵，缺少它請求一律被 Cloudflare 攔截。

### 2.2 API 要求動態時間戳參數

觀察誠品線上網頁實際發出的請求後發現，商品 API 每次呼叫都必須帶上 `datetime` query 參數，格式為 `YYYYMMDDHHmmss`（如 `20260705143210`），推測用於後端做請求時效驗證或快取失效判斷：

```python
from datetime import datetime

def fetch_product(guid: str) -> dict:
    url = f"https://athena.eslite.com/api/v1/products/{guid}"
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    resp = cffi_requests.get(
        url,
        params={"datetime": ts},
        headers=_HEADERS,
        impersonate="chrome120",
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()
```

若省略此參數或帶入固定值，部分情況下 API 會回傳錯誤或非預期的快取結果，因此每次請求都即時產生當下時間戳。

### 2.3 商品 GUID 的容錯擷取

使用者輸入的來源可能是純數字 GUID，也可能是完整商品頁 URL（如 `https://www.eslite.com/product/10012013492683166052007`）。為避免要求使用者自行複製 GUID，改用正規表達式從任意字串中擷取 20 位以上的連續數字：

```python
import re

_GUID_RE = re.compile(r"\d{20,}")

def extract_guid(text: str) -> str:
    m = _GUID_RE.search(text)
    if m:
        return m.group()
    raise ValueError(f"無法從 {text!r} 解析出商品 GUID（需為 20 位以上數字）")
```

這讓 CLI 同時支援兩種輸入形式：

```bash
uv run eslite_stock.py 10012013492683166052007
uv run eslite_stock.py https://www.eslite.com/product/10012013492683166052007
```

### 2.4 持續監控（--watch）與狀態顯示

限量書籍的補貨時機難以預測，因此加入 `--watch N` 參數，每 N 秒重新查詢並清空終端機重繪，直到使用者按 `Ctrl+C` 中斷：

```python
if args.watch:
    try:
        while True:
            console.clear()
            query_all(guids, args.raw_json)
            console.print(f"\n[dim]每 {args.watch} 秒更新一次，按 Ctrl+C 結束[/dim]")
            time.sleep(args.watch)
    except KeyboardInterrupt:
        console.print("\n[dim]已停止監控[/dim]")
```

庫存與購買狀態以顏色區分，方便在終端機掃視多筆商品時快速辨識可搶購的項目：

```python
_BUTTON_LABEL = {
    "add_to_shopping_cart": "[bold green]可加入購物車[/bold green]",
    "out_of_stock":         "[bold red]缺貨[/bold red]",
    "not_for_sale":         "[yellow]停售[/yellow]",
    "pre_order":            "[cyan]預購中[/cyan]",
}
```

### 2.5 多目標查詢與錯誤隔離

支援一次傳入多個 GUID/URL，且單一商品查詢失敗（如 GUID 打錯、該商品已下架）不應中斷整批查詢：

```python
def query_all(guids: list[str], raw_json: bool) -> None:
    for i, guid in enumerate(guids):
        try:
            data = fetch_product(guid)
        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status:
                console.print(f"[red]HTTP {status}（GUID: {guid}）[/red]")
            else:
                console.print(f"[red]錯誤：{e}（GUID: {guid}）[/red]")
            continue
        ...
```

每筆商品各自 try/except，確保部分失敗不影響其餘商品的查詢結果。

### 2.6 Windows 終端機中文編碼相容性

在部分 Windows 終端環境（如舊版 `cmd.exe`）下，`sys.stdout` 預設編碼並非 UTF-8，直接輸出中文書名或 rich 的方塊字元會出現亂碼或 `UnicodeEncodeError`。啟動時主動偵測並重新設定編碼：

```python
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
```

### 2.7 PEP 723 獨立腳本（零安裝執行）

本工具以 [PEP 723](https://peps.python.org/pep-0723/) 內嵌相依套件宣告，使用者無需事先 `pip install` 或維護虛擬環境，`uv run` 會自動解析並快取相依套件：

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "curl-cffi>=0.7",
#   "rich>=13",
# ]
# ///
```

```bash
uv run eslite_stock.py <GUID或URL> [--watch 秒] [--json]
```

---

## 3. 架構小結

```
使用者輸入 (GUID / URL)
        │
        ▼
  extract_guid()  ──▶ 正規表達式擷取 20 位以上數字
        │
        ▼
  fetch_product()  ──▶ curl-cffi + impersonate="chrome120" 繞過 Cloudflare TLS 指紋偵測
        │              帶入即時 datetime 參數
        ▼
  athena.eslite.com/api/v1/products/{guid}
        │
        ▼
  show_product() / json.dumps()  ──▶ rich 彩色輸出 或 原始 JSON
        │
        ▼
  （若 --watch）迴圈重新查詢，Ctrl+C 結束
```

整個專案最主要、也最不易從程式碼本身看出「為什麼這樣寫」的技術決策，是 **2.1 節的 TLS 指紋問題**：一般開發者在遇到 API 回傳 403 時，直覺會先懷疑 Header 或 Cookie，但根因其實在 TLS 層，必須改用能重現瀏覽器指紋的函式庫（curl-cffi）才能解決，單純偽造 `User-Agent` 完全無效。
