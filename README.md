# TradFi Freqtrade blacklists

`tradfi-exclusions.json` records exclusions by real underlying asset. Exchange-specific
Freqtrade pair strings are generated from the aliases under each underlying, so one policy
decision can be applied consistently across Binance and OKX.

## Files

- `tradfi-exclusions.json`: canonical exclusion policy, underlyings and confirmed venue aliases.
- `blacklist-binance-spot.json`: Binance bStocks spot blacklist.
- `blacklist-binance-futures.json`: Binance TradFi perpetual blacklist.
- `blacklist-okx-spot.json`: OKX Unified Tokenized Stocks spot blacklist.
- `blacklist-okx-futures.json`: OKX USDT perpetual `SWAP` blacklist.
- `blacklist.json`: backward-compatible copy of `blacklist-binance-futures.json`.
- `generate_tradfi_blacklists.py`: standard-library-only generator and live-market validator.
- `bstocks-source.json`: Binance-officially confirmed bStocks base assets.
- `binance-bstocks.json`: active Binance bStocks USDT spot whitelist for Freqtrade.
- `generate_bstocks.py`: generates `binance-bstocks.json` by intersecting the confirmed assets with
  the live Binance spot inventory.

OKX dated `FUTURES`/XPERP instruments are intentionally excluded because Freqtrade futures
mode uses perpetual swaps.

## Policy

The current policy excludes:

- ordinary companies from mainland China and Hong Kong, while retaining confirmed Chinese AI
  and AI-infrastructure companies;
- inverse or short leveraged products;
- volatility products;
- existing manual exclusions that have not yet been reviewed.

`AAOI` and `STRC` are preserved for compatibility with the existing blacklist, but their
historical exclusion reasons were not recorded. They are marked `manual_legacy_exclusion` in
the canonical file instead of assigning an unsupported reason.

## Generate

Run against the current public market inventories:

```bash
python3 generate_tradfi_blacklists.py
```

The generator only emits confirmed aliases that are currently active in each market. A delisted
alias remains in the canonical file and will automatically return to the generated blacklist if
the same market is relisted.

Verify that committed outputs are current without modifying files:

```bash
python3 generate_tradfi_blacklists.py --check
```

Run tests without third-party packages:

```bash
python3 -m unittest discover -s tests -v
```

Generate or verify the Binance bStocks whitelist:

```bash
python3 generate_bstocks.py
python3 generate_bstocks.py --check
```

The public Binance spot `exchangeInfo` response does not expose a reliable bStocks category.
New entries in `bstocks-source.json` therefore require confirmation from an official Binance
bStocks listing or product source before generation. A trailing `B` alone is not sufficient.

## Freqtrade usage

Use the venue-appropriate file through `RemotePairList` in blacklist mode. For example:

```json
{
  "method": "RemotePairList",
  "mode": "blacklist",
  "pairlist_url": "https://denny8023.github.io/freqtrade_pairs/blacklist-okx-spot.json",
  "refresh_period": 3600,
  "keep_pairlist_on_failure": true
}
```

Update `tradfi-exclusions.json` when a policy decision or venue alias changes, then regenerate
all outputs together. Do not edit generated blacklist files independently.

Use `binance-bstocks.json` as the Binance spot whitelist and `blacklist-binance-spot.json` as its
blacklist when both lists are needed.
