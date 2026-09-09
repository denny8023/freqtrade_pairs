#!/usr/bin/env python3
"""Generate a Freqtrade Binance bStocks spot whitelist."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"


def fetch_json(url: str, timeout: int = 30) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "freqtrade-pairs-generator/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def active_usdt_spot_assets(exchange_info: dict[str, Any]) -> set[str]:
    return {
        item["baseAsset"]
        for item in exchange_info.get("symbols", [])
        if item.get("status") == "TRADING"
        and item.get("quoteAsset") == "USDT"
        and item.get("isSpotTradingAllowed") is True
    }


def validate_source(source: dict[str, Any]) -> None:
    if source.get("schema_version") != 1:
        raise ValueError("unsupported schema_version")
    if not isinstance(source.get("refresh_period"), int) or source["refresh_period"] <= 0:
        raise ValueError("refresh_period must be a positive integer")
    if source.get("quote_asset") != "USDT":
        raise ValueError("quote_asset must be USDT")

    assets = source.get("base_assets")
    if not isinstance(assets, list) or not assets:
        raise ValueError("base_assets must be a non-empty list")
    if assets != sorted(assets):
        raise ValueError("base_assets must be sorted")
    if len(assets) != len(set(assets)):
        raise ValueError("base_assets contains duplicates")
    for asset in assets:
        if not isinstance(asset, str) or not re.fullmatch(r"[A-Z0-9]+", asset):
            raise ValueError(f"invalid base asset: {asset!r}")


def build_output(source: dict[str, Any], active_assets: set[str]) -> tuple[dict[str, Any], list[str]]:
    validate_source(source)
    selected = [asset for asset in source["base_assets"] if asset in active_assets]
    output = {
        "pairs": [f"{asset}/{source['quote_asset']}" for asset in selected],
        "refresh_period": source["refresh_period"],
    }
    return output, selected


def serialized(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=root / "bstocks-source.json")
    parser.add_argument("--output", type=Path, default=root / "binance-bstocks.json")
    parser.add_argument(
        "--exchange-info",
        type=Path,
        help="Use a saved Binance exchangeInfo response instead of the live API.",
    )
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; fail if binance-bstocks.json differs from the generated output.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = json.loads(args.source.read_text(encoding="utf-8"))
    if args.exchange_info:
        exchange_info = json.loads(args.exchange_info.read_text(encoding="utf-8"))
    else:
        exchange_info = fetch_json(EXCHANGE_INFO_URL, args.timeout)

    output, selected = build_output(source, active_usdt_spot_assets(exchange_info))
    content = serialized(output)
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != content:
            print("binance-bstocks.json is stale", file=sys.stderr)
            return 1
    else:
        args.output.write_text(content, encoding="utf-8")

    print(
        f"confirmed={len(source['base_assets'])} active={len(selected)} "
        f"symbols={','.join(selected)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
