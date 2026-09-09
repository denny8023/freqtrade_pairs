import copy
import json
import unittest
from pathlib import Path

from generate_bstocks import active_usdt_spot_assets, build_output, validate_source


ROOT = Path(__file__).resolve().parents[1]


class GenerateBstocksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads((ROOT / "bstocks-source.json").read_text(encoding="utf-8"))

    def test_committed_source_is_valid(self):
        validate_source(self.source)
        self.assertEqual(len(self.source["base_assets"]), 74)

    def test_only_confirmed_active_assets_are_emitted(self):
        source = {
            "schema_version": 1,
            "refresh_period": 3600,
            "quote_asset": "USDT",
            "base_assets": ["AAPLB", "MUB", "SQQQB"],
        }
        output, selected = build_output(source, {"AAPLB", "BNB", "MUB"})

        self.assertEqual(selected, ["AAPLB", "MUB"])
        self.assertEqual(output["pairs"], ["AAPLB/USDT", "MUB/USDT"])
        self.assertNotIn("BNB/USDT", output["pairs"])

    def test_active_inventory_requires_spot_trading(self):
        exchange_info = {
            "symbols": [
                {
                    "baseAsset": "AAPLB",
                    "quoteAsset": "USDT",
                    "status": "TRADING",
                    "isSpotTradingAllowed": True,
                },
                {
                    "baseAsset": "SQQQB",
                    "quoteAsset": "USDT",
                    "status": "BREAK",
                    "isSpotTradingAllowed": True,
                },
            ]
        }

        self.assertEqual(active_usdt_spot_assets(exchange_info), {"AAPLB"})

    def test_duplicate_assets_are_rejected(self):
        source = copy.deepcopy(self.source)
        source["base_assets"].append(source["base_assets"][-1])
        with self.assertRaisesRegex(ValueError, "duplicates"):
            validate_source(source)


if __name__ == "__main__":
    unittest.main()
