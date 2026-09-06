#!/usr/bin/env python3
"""Generate venue-specific Freqtrade blacklists from canonical underlyings."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


VENUES = {
    "binance_spot": {
        "filename": "blacklist-binance-spot.json",
        "suffix": "/USDT",
    },
    "binance_futures": {
        "filename": "blacklist-binance-futures.json",
        "suffix": "/USDT:USDT",
    },
    "okx_spot": {
        "filename": "blacklist-okx-spot.json",
        "suffix": "/USDT",
    },
    "okx_futures": {
        "filename": "blacklist-okx-futures.json",
        "suffix": "/USDT:USDT",
    },
}

API_URLS = {
    "binance_spot": "https://api.binance.com/api/v3/exchangeInfo",
    "binance_futures": "https://fapi.binance.com/fapi/v1/exchangeInfo",
    "okx_spot": "https://www.okx.com/api/v5/public/instruments?instType=SPOT",
    "okx_futures": "https://www.okx.com/api/v5/public/instruments?instType=SWAP",
}


def fetch_json(url: str, timeout: int = 30) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "freqtrade-pairs-generator/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def fetch_live_inventory(timeout: int = 30) -> dict[str, set[str]]:
    binance_spot = fetch_json(API_URLS["binance_spot"], timeout)
    binance_futures = fetch_json(API_URLS["binance_futures"], timeout)
    okx_spot = fetch_json(API_URLS["okx_spot"], timeout)
    okx_futures = fetch_json(API_URLS["okx_futures"], timeout)

    return {
        "binance_spot": {
            item["baseAsset"]
            for item in binance_spot.get("symbols", [])
            if item.get("status") == "TRADING"
            and item.get("quoteAsset") == "USDT"
            and item.get("isSpotTradingAllowed") is True
        },
        "binance_futures": {
            item["baseAsset"]
            for item in binance_futures.get("symbols", [])
            if item.get("status") == "TRADING"
            and item.get("quoteAsset") == "USDT"
            and item.get("marginAsset") == "USDT"
            and item.get("contractType") == "TRADIFI_PERPETUAL"
        },
        "okx_spot": {
            item["baseCcy"]
            for item in okx_spot.get("data", [])
            if item.get("state") == "live"
            and item.get("quoteCcy") == "USDT"
            and item.get("instCategory") == "3"
        },
        "okx_futures": {
            item["instId"][: -len("-USDT-SWAP")]
            for item in okx_futures.get("data", [])
            if item.get("state") == "live"
            and item.get("instCategory") == "3"
            and item.get("instId", "").endswith("-USDT-SWAP")
        },
    }


def load_inventory(path: Path) -> dict[str, set[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = set(VENUES) - set(data)
    if missing:
        raise ValueError(f"inventory missing venues: {', '.join(sorted(missing))}")
    return {venue: set(data[venue]) for venue in VENUES}


def validate_source(source: dict[str, Any]) -> None:
    if source.get("schema_version") != 1:
        raise ValueError("unsupported schema_version")
    if not isinstance(source.get("refresh_period"), int) or source["refresh_period"] <= 0:
        raise ValueError("refresh_period must be a positive integer")

    reason_codes = set(source.get("policy", {}).get("exclude", {}))
    seen_ids: set[str] = set()
    for item in source.get("underlyings", []):
        item_id = item.get("id")
        if not item_id or item_id in seen_ids:
            raise ValueError(f"invalid or duplicate underlying id: {item_id!r}")
        seen_ids.add(item_id)

        if item.get("reason_code") not in reason_codes:
            raise ValueError(f"unknown reason_code for {item_id}")

        aliases = item.get("market_aliases", {})
        if set(aliases) != set(VENUES):
            raise ValueError(f"market_aliases for {item_id} must contain all venues")
        for venue, symbols in aliases.items():
            if not isinstance(symbols, list) or len(symbols) != len(set(symbols)):
                raise ValueError(f"invalid aliases for {item_id}/{venue}")
            for symbol in symbols:
                if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z0-9._-]+", symbol):
                    raise ValueError(f"invalid symbol {symbol!r} for {item_id}/{venue}")


def build_outputs(
    source: dict[str, Any], inventory: dict[str, set[str]]
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    validate_source(source)
    outputs: dict[str, dict[str, Any]] = {}
    selected: dict[str, list[str]] = {}

    for venue, settings in VENUES.items():
        if venue not in inventory:
            raise ValueError(f"inventory missing venue: {venue}")

        symbols: list[str] = []
        seen: set[str] = set()
        for item in source["underlyings"]:
            for symbol in item["market_aliases"][venue]:
                if symbol in inventory[venue] and symbol not in seen:
                    seen.add(symbol)
                    symbols.append(symbol)

        selected[venue] = symbols
        pairs: list[str] = []
        if symbols:
            alternatives = "|".join(re.escape(symbol) for symbol in symbols)
            pairs.append(f"^({alternatives}){settings['suffix']}$")
        outputs[settings["filename"]] = {
            "pairs": pairs,
            "refresh_period": source["refresh_period"],
        }

    outputs["blacklist.json"] = outputs["blacklist-binance-futures.json"]
    return outputs, selected


def serialized(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def write_or_check_outputs(
    outputs: dict[str, dict[str, Any]], output_dir: Path, check: bool
) -> list[str]:
    stale: list[str] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in outputs.items():
        path = output_dir / filename
        content = serialized(payload)
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(filename)
        else:
            path.write_text(content, encoding="utf-8")
    return stale


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=root / "tradfi-exclusions.json")
    parser.add_argument("--output-dir", type=Path, default=root)
    parser.add_argument(
        "--inventory",
        type=Path,
        help="Use a local inventory JSON instead of querying public exchange APIs.",
    )
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; fail when generated files differ from current files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = json.loads(args.source.read_text(encoding="utf-8"))
    inventory = load_inventory(args.inventory) if args.inventory else fetch_live_inventory(args.timeout)
    outputs, selected = build_outputs(source, inventory)
    stale = write_or_check_outputs(outputs, args.output_dir, args.check)

    for venue in VENUES:
        print(
            f"{venue}: market={len(inventory[venue])} "
            f"excluded={len(selected[venue])} "
            f"symbols={','.join(selected[venue]) or '-'}"
        )

    if stale:
        print(f"stale generated files: {', '.join(stale)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
