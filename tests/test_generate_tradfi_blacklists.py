import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from generate_tradfi_blacklists import build_outputs, fetch_live_inventory, validate_source


ROOT = Path(__file__).resolve().parents[1]


class GenerateTradfiBlacklistsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads((ROOT / "tradfi-exclusions.json").read_text(encoding="utf-8"))

    def test_current_market_mapping(self):
        inventory = {
            "binance_spot": {"AAOIB", "BABAB", "SOXSB", "SQQQB", "BTC"},
            "binance_futures": {
                "BABA", "TENCENT", "HK0700", "HK1810", "POPMART", "MEITUAN",
                "KUAISHOU", "SQQQ", "SOXS", "TZA", "TBT", "UVXY", "SKDD",
                "PDD", "AAOI", "STRC", "HK0625", "BTC",
            },
            "okx_spot": {"XAAOI", "XPOPMART", "XSTRC", "XXIAOMI", "BTC"},
            "okx_futures": {
                "AAOI", "POPMART", "SHEIN", "SKDD", "SOXS", "SQQQ", "STRC",
                "UVXY", "XIAOMI", "BTC",
            },
        }

        outputs, selected = build_outputs(self.source, inventory)

        self.assertEqual(selected["binance_spot"], ["BABAB", "SQQQB", "SOXSB", "AAOIB"])
        self.assertEqual(
            outputs["blacklist-okx-spot.json"]["pairs"],
            ["^(XXIAOMI|XPOPMART|XAAOI|XSTRC)/USDT$"],
        )
        self.assertEqual(
            outputs["blacklist-okx-futures.json"]["pairs"],
            ["^(XIAOMI|POPMART|SQQQ|SOXS|UVXY|SKDD|AAOI|STRC|SHEIN)/USDT:USDT$"],
        )
        self.assertEqual(outputs["blacklist.json"], outputs["blacklist-binance-futures.json"])

    def test_unlisted_aliases_are_not_emitted(self):
        inventory = {venue: set() for venue in (
            "binance_spot", "binance_futures", "okx_spot", "okx_futures"
        )}
        outputs, selected = build_outputs(self.source, inventory)
        self.assertTrue(all(not symbols for symbols in selected.values()))
        self.assertTrue(all(not payload["pairs"] for payload in outputs.values()))

    @patch("generate_tradfi_blacklists.fetch_json")
    def test_binance_futures_uses_margin_asset(self, mock_fetch_json):
        mock_fetch_json.side_effect = [
            {"symbols": []},
            {
                "symbols": [
                    {
                        "baseAsset": "BABA",
                        "quoteAsset": "USDT",
                        "marginAsset": "USDT",
                        "status": "TRADING",
                        "contractType": "TRADIFI_PERPETUAL",
                    }
                ]
            },
            {"data": []},
            {"data": []},
        ]

        inventory = fetch_live_inventory()

        self.assertEqual(inventory["binance_futures"], {"BABA"})

    def test_duplicate_underlying_id_is_rejected(self):
        source = copy.deepcopy(self.source)
        source["underlyings"].append(copy.deepcopy(source["underlyings"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate underlying id"):
            validate_source(source)


if __name__ == "__main__":
    unittest.main()
