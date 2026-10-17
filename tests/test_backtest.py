"""Unit tests for the frozen OFI backtest mechanics.

These tests use synthetic data only; they do not read market-data files.
"""

from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import backtest  # noqa: E402


class BacktestLogicTests(unittest.TestCase):
    def setUp(self):
        # Pin these expected choices so an accidental edit to the frozen
        # primary strategy causes a visible test failure.
        self.assertEqual(backtest.SIGNAL_INTERVAL_SECONDS, 5)
        self.assertEqual(backtest.ENTRY_DELAY_SECONDS, 1)
        self.assertEqual(backtest.HOLD_SECONDS, 5)

    @staticmethod
    def make_frame(periods=40):
        index = pd.date_range(
            "2025-06-01T00:00:00Z",
            periods=periods,
            freq="s",
            name="feature_available_at_utc",
        )
        return pd.DataFrame(
            {
                "flow_imbalance": np.zeros(periods, dtype=float),
                "close_price": np.arange(100.0, 100.0 + periods),
            },
            index=index,
        )

    def test_decisions_are_on_five_second_grid(self):
        df = self.make_frame(40)
        sampled, _, _ = backtest.build_trades(df)
        expected = df.index[df.index.second % 5 == 0]
        self.assertEqual(len(sampled), 8)
        self.assertTrue(sampled.index.equals(expected))
        self.assertTrue((sampled.index.second % 5 == 0).all())

    def test_threshold_boundaries_and_neutral_values(self):
        df = self.make_frame(40)
        df.loc[df.index[0], "flow_imbalance"] = 0.75
        df.loc[df.index[5], "flow_imbalance"] = -0.75
        df.loc[df.index[10], "flow_imbalance"] = 0.749
        df.loc[df.index[15], "flow_imbalance"] = -0.749
        df.loc[df.index[20], "flow_imbalance"] = 0.90

        sampled, trades, dropped = backtest.build_trades(df)
        self.assertEqual(sampled.loc[df.index[0], "direction"], 1)
        self.assertEqual(sampled.loc[df.index[5], "direction"], -1)
        self.assertEqual(sampled.loc[df.index[10], "direction"], 0)
        self.assertEqual(sampled.loc[df.index[15], "direction"], 0)
        self.assertEqual(sampled.loc[df.index[20], "direction"], 1)
        self.assertEqual(len(trades), 3)
        self.assertEqual(dropped, 0)

    def test_entry_is_t_plus_one_and_exit_is_t_plus_six(self):
        df = self.make_frame(40)
        signal_time = df.index[0]
        df.loc[signal_time, "flow_imbalance"] = 0.90

        _, trades, dropped = backtest.build_trades(df)
        self.assertEqual(dropped, 0)
        trade = trades.loc[signal_time]

        # Synthetic close is 100 at t=0, 101 at t+1, and 106 at t+6.
        self.assertEqual(trade["entry_price"], 101.0)
        self.assertEqual(trade["exit_price"], 106.0)
        expected_return = (106.0 / 101.0 - 1.0) * 10_000
        self.assertAlmostEqual(trade["gross_return_bps"], expected_return)

    def test_internal_missing_trade_price_is_forward_filled(self):
        df = self.make_frame(40)
        signal_time = df.index[0]
        df.loc[signal_time, "flow_imbalance"] = 0.90
        # This timestamp is the intended exit proxy (t+6).
        df.loc[df.index[6], "close_price"] = np.nan

        _, trades, dropped = backtest.build_trades(df)
        self.assertEqual(dropped, 0)
        trade = trades.loc[signal_time]
        # Last known close before t+6 is the value at t+5 (= 105).
        self.assertEqual(trade["exit_price"], 105.0)

    def test_signal_without_future_exit_price_is_dropped(self):
        df = self.make_frame(20)  # timestamps run from t=0 through t=19
        signal_time = df.index[15]
        df.loc[signal_time, "flow_imbalance"] = 0.90
        # Entry at t+1 exists, but exit at t+6 (t=21) is outside the file.

        sampled, trades, dropped = backtest.build_trades(df)
        self.assertEqual(sampled.loc[signal_time, "direction"], 1)
        self.assertEqual(len(trades), 0)
        self.assertEqual(dropped, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
