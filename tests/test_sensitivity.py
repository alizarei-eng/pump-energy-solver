"""Sensitivity engine smoke tests."""
import unittest
from hydraulics.sensitivity import analyze_sensitivity


class SensitivityTests(unittest.TestCase):
    def test_length_and_flow_raise_head(self):
        segment = {"diameter": 0.2, "roughness": 0.0015, "length": 120.0, "k": 1.5}
        result = analyze_sensitivity([segment], [], 24, 0, 1022, 8.46e-7, 150)
        rows = {item["parameter"]: item for item in result["results"]}
        self.assertGreater(rows["Flow rate"]["derivative_m"], 0)
        self.assertGreater(rows["Pipe length"]["derivative_m"], 0)
        self.assertLess(rows["Internal diameter"]["derivative_m"], 0)
        self.assertGreater(result["baseline_head_m"], 24)

    def test_invalid_flow(self):
        with self.assertRaises(ValueError):
            analyze_sensitivity([{"diameter": 0.2}], [], 0, 0, 1000, 1e-6, 0)


if __name__ == "__main__":
    unittest.main()
