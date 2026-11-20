"""Regression tests for the standalone system curve engine."""
import unittest

from hydraulics.system_curve import calculate_system_curve


class SystemCurveTests(unittest.TestCase):
    def test_static_head_and_power(self):
        segment = {"diameter": 0.2, "roughness": 0.0015, "length": 0, "k": 0}
        static, flows, heads, powers, rows = calculate_system_curve(
            [segment], [], 25.5, 0, 1022, 8.46e-7, 150, 50
        )
        self.assertAlmostEqual(static, 25.5)
        self.assertAlmostEqual(heads[-1], 25.5)
        self.assertAlmostEqual(powers[-1], 1022 * 9.80665 * (150 / 3600) * 25.5 / 1000)
        self.assertEqual(powers[0], 0)
        self.assertEqual(len(rows), 50)

    def test_pipe_losses_increase_head(self):
        segment = {"diameter": 0.2, "roughness": 0.0015, "length": 120, "k": 1.5}
        _, _, heads, _, _ = calculate_system_curve(
            [segment], [], 24, 0, 1022, 8.46e-7, 150
        )
        self.assertGreater(heads[-1], 24)

    def test_invalid_flow_rejected(self):
        with self.assertRaises(ValueError):
            calculate_system_curve([{"diameter": 0.2}], [], 0, 0, 1000, 1e-6, 0)


if __name__ == "__main__":
    unittest.main()
