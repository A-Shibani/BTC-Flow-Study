import unittest

import numpy as np
import pandas as pd

from src.build_multiday_dataset import (
    calculate_forward_return_bps,
    forward_fill_known_price,
    normalize_flow_imbalance,
    signed_trade_quantity,
)


class ResearchDataFunctionTests(unittest.TestCase):
    def test_aggressor_signing(self):
        quantity = pd.Series([2.0, 3.0, 4.0, 5.0])
        buyer_is_maker = pd.Series([False, True, "false", "true"])

        result = signed_trade_quantity(quantity, buyer_is_maker)

        np.testing.assert_allclose(result, [2.0, -3.0, 4.0, -5.0])

    def test_flow_imbalance_normalisation(self):
        signed = pd.Series([2.0, -3.0, 0.0, 1.0])
        total = pd.Series([2.0, 3.0, 0.0, 4.0])

        result = normalize_flow_imbalance(signed, total)

        self.assertEqual(result.iloc[0], 1.0)
        self.assertEqual(result.iloc[1], -1.0)
        self.assertTrue(np.isnan(result.iloc[2]))
        self.assertEqual(result.iloc[3], 0.25)

        finite = result.dropna()
        self.assertTrue((finite >= -1.0).all())
        self.assertTrue((finite <= 1.0).all())

    def test_forward_fill_uses_only_past_prices(self):
        price = pd.Series([np.nan, 100.0, np.nan, 103.0, np.nan])

        result = forward_fill_known_price(price)

        self.assertTrue(np.isnan(result.iloc[0]))
        np.testing.assert_allclose(
            result.iloc[1:].to_numpy(),
            [100.0, 100.0, 103.0, 103.0],
        )

    def test_forward_target_uses_future_not_past_price(self):
        known_price = pd.Series([100.0, 101.0, 103.0])

        result = calculate_forward_return_bps(known_price, horizon=1)

        self.assertAlmostEqual(result.iloc[0], 100.0)
        self.assertAlmostEqual(result.iloc[1], (103.0 / 101.0 - 1) * 10_000)
        self.assertTrue(np.isnan(result.iloc[2]))

    def test_invalid_horizon_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_forward_return_bps(
                pd.Series([100.0, 101.0]),
                horizon=0,
            )


if __name__ == "__main__":
    unittest.main()