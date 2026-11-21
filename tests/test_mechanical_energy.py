"""Regression checks for the main mechanical-energy solver."""
import math
import unittest

from pump_energy import G, solve


class MechanicalEnergySolverTests(unittest.TestCase):
    def test_continuity_calculates_velocity(self):
        values, _, errors = solve({"Q": 150.0, "D1": 200.0})
        expected = (150 / 3600) / (math.pi * (0.2 ** 2) / 4)
        self.assertAlmostEqual(values["V1"], expected, places=9)
        self.assertFalse(errors)

    def test_head_and_power_with_known_boundaries(self):
        data = {"Q": 150.0, "rho": 1022.0, "dP": 0.0,
                "V1": 0.0, "V2": 0.0, "dz": 24.0,
                "hL": 1.5, "eta": 75.0}
        values, _, errors = solve(data)
        self.assertAlmostEqual(values["Hp"], 25.5)
        hydraulic = 1022.0 * G * (150 / 3600) * 25.5 / 1000
        self.assertAlmostEqual(values["Ph"], hydraulic)
        self.assertAlmostEqual(values["Ps"], hydraulic / 0.75)
        self.assertFalse(errors)

    def test_conflicting_power_is_reported(self):
        data = {"Q": 150.0, "rho": 1000.0, "Hp": 20.0, "Ph": 1.0}
        _, _, errors = solve(data)
        self.assertTrue(any("Conflict for Ph" in e for e in errors))

    def test_zero_flow_gives_zero_hydraulic_power(self):
        values, _, errors = solve({"Q": 0.0, "rho": 1000.0, "Hp": 25.0})
        self.assertEqual(values["Ph"], 0.0)
        self.assertFalse(errors)


if __name__ == "__main__":
    unittest.main()
