# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "curl-cffi>=0.7",
#   "rich>=13",
# ]
# ///
"""誠品線上庫存查詢工具"""

import argparse
import json
import re
import sys
import time
from datetime import datetime

# Windows 終端 UTF-8 相容
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from curl_cffi import requests as cffi_requests
from rich.console import Console

console = Console()

_GUID_RE = re.compile(r"\d{20,}")

_HEADERS = {
    "Accept": "application/json",
    "Referer": "https://www.eslite.com/",
}

_BUTTON_LABEL = {
    "add_to_shopping_cart": "[bold green]可加入購物車[/bold green]",
    "out_of_stock":         "[bold red]缺貨[/bold red]",
    "not_for_sale":         "[yellow]停售[/yellow]",
    "pre_order":            "[cyan]預購中[/cyan]",
}


def extract_guid(text: str) -> str:
    m = _GUID_RE.search(text)
    if m:
        return m.group()
    raise ValueError(f"無法從 {text!r} 解析出商品 GUID（需為 20 位以上數字）")


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


def show_product(data: dict) -> None:
    stock = data.get("stock", 0)
    stock_str = (
        f"[bold green]{stock}[/bold green]"
        if stock > 0
        else f"[bold red]{stock}[/bold red]"
    )
    status_key = data.get("product_button_status", "")
    status_str = _BUTTON_LABEL.get(status_key, f"[dim]{status_key}[/dim]")

    console.print(f"[bold]{data.get('name', '（無書名）')}[/bold]")
    console.print(f"  庫　　存：{stock_str}")
    console.print(f"  購買狀態：{status_str}")
    console.print(f"  定　　價：{data.get('final_price', '-')}")
    console.print(f"  售　　價：{data.get('retail_price', '-')}")
    console.print(
        f"  查詢時間：[dim]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]"
    )


def query_all(guids: list[str], raw_json: bool) -> None:
    for i, guid in enumerate(guids):
        try:
            data = fetch_product(guid)
        except Exception as e:
            msg = getattr(getattr(e, "response", None), "status_code", None)
            if msg:
                console.print(f"[red]HTTP {msg}（GUID: {guid}）[/red]")
            else:
                console.print(f"[red]錯誤：{e}（GUID: {guid}）[/red]")
            continue

        if raw_json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            show_product(data)
            if i < len(guids) - 1:
                console.print()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="eslite-stock",
        description="誠品線上庫存查詢工具",
        epilog=(
            "範例：\n"
            "  uv run eslite_stock.py 10012013492683166052007\n"
            "  uv run eslite_stock.py https://www.eslite.com/product/10012013492683166052007\n"
            "  uv run eslite_stock.py 10012013492683166052007 --watch 30\n"
            "  uv run eslite_stock.py 10012013492683166052007 --json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "targets",
        nargs="+",
        metavar="GUID或URL",
        help="商品 GUID 或誠品商品頁 URL（可同時輸入多個）",
    )
    parser.add_argument(
        "--json",
        dest="raw_json",
        action="store_true",
        help="輸出原始 JSON",
    )
    parser.add_argument(
        "--watch",
        type=int,
        metavar="秒",
        help="每隔 N 秒持續監控庫存（Ctrl+C 結束）",
    )
    args = parser.parse_args()

    try:
        guids = [extract_guid(t) for t in args.targets]
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    if args.watch:
        try:
            while True:
                console.clear()
                query_all(guids, args.raw_json)
                console.print(
                    f"\n[dim]每 {args.watch} 秒更新一次，按 Ctrl+C 結束[/dim]"
                )
                time.sleep(args.watch)
        except KeyboardInterrupt:
            console.print("\n[dim]已停止監控[/dim]")
    else:
        query_all(guids, args.raw_json)


if __name__ == "__main__":
    main()
