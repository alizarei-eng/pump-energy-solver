"""Shared, validated water-property service for pump and system calculations.

This module is the single application-facing interface to the scientific
correlations in water_properties.py. It does not invent properties from EC.
"""
from dataclasses import dataclass
from functools import lru_cache
from water_properties import calculate_water_properties

PROPERTY_FIELDS = (
    ("density_kg_m3", "Density", "kg/m3"),
    ("dynamic_viscosity_Pa_s", "Dynamic viscosity", "Pa.s"),
    ("kinematic_viscosity_m2_s", "Kinematic viscosity", "m2/s"),
    ("vapor_pressure_MPa", "Vapor pressure (absolute)", "MPa"),
    ("conductivity_mS_cm", "Electrical conductivity (in situ)", "mS/cm"),
    ("practical_salinity", "Practical salinity (PSS-78)", "unitless"),
    ("absolute_salinity_g_kg", "Absolute / reference salinity", "g/kg"),
    ("conservative_temperature_C", "Conservative temperature", "deg C"),
    ("sea_pressure_dbar", "Sea pressure", "dbar"),
)

@dataclass(frozen=True)
class FluidSpec:
    water_type: str = "seawater"
    temperature_C: float = 30.0
    ec_ms_cm: float | None = 58.0
    pressure_MPa_abs: float = 0.101325
    latitude_deg: float | None = None
    longitude_deg: float | None = None

    def calculate(self):
        args = dict(water_type=self.water_type, temperature_C=self.temperature_C,
                    pressure_MPa_abs=self.pressure_MPa_abs)
        if self.water_type == "seawater":
            args.update(EC_value=self.ec_ms_cm, EC_unit="mS/cm",
                        conductivity_temperature_mode="in_situ")
            if self.latitude_deg is not None or self.longitude_deg is not None:
                args.update(latitude_deg=self.latitude_deg, longitude_deg=self.longitude_deg)
        return calculate_water_properties(**args)

@lru_cache(maxsize=128)
def properties_for(spec: FluidSpec):
    """Cached calculations; caller must not mutate the returned dictionary."""
    return spec.calculate()

def property_report(props):
    lines = ["FLUID PROPERTY REPORT", "=" * 64,
             f"Model: {props.get('method', 'Unknown')}",
             f"Fluid: {props['water_type']}",
             f"Temperature: {props['temperature_C']} deg C",
             f"Absolute pressure: {props['pressure_MPa_abs']} MPa", ""]
    for key, label, unit in PROPERTY_FIELDS:
        value = props.get(key)
        if value is not None:
            lines.append(f"{label:39} {value:.8g} {unit}")
    for section in ("assumptions", "warnings"):
        lines.append("\n" + section.upper())
        lines.extend("- " + note for note in props.get(section, []))
    lines.append("\nVALIDITY / PROVENANCE")
    lines.extend(f"{key}: {value}" for key, value in props.get("validity", {}).items())
    lines.append("Not a laboratory analysis. EC does not identify individual ions, TDS, or RO reject chemistry.")
    return "\n".join(lines)
