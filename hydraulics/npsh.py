"""NPSH calculations using existing water_properties.py; SI units throughout."""
import math
from water_properties import calculate_water_properties

G = 9.80665

def calculate_npsh(*, water_type="seawater", temperature_C=30, ec_ms_cm=58,
                   flow_m3h=150, inside_diameter_mm=200, length_m=10,
                   roughness_mm=0.0015, fittings_k=1.0, static_height_m=7,
                   surface_pressure_bar_abs=1.01325, npshr_m=4,
                   known_loss_m=None):
    """static_height_m = free-surface elevation minus pump inlet elevation."""
    vals = [temperature_C, flow_m3h, inside_diameter_mm, length_m, roughness_mm,
            fittings_k, static_height_m, surface_pressure_bar_abs, npshr_m]
    if not all(math.isfinite(float(x)) for x in vals):
        raise ValueError("All inputs must be finite.")
    if surface_pressure_bar_abs <= 0 or npshr_m < 0:
        raise ValueError("Pressure must be positive and NPSHr nonnegative.")
    if known_loss_m is not None and (not math.isfinite(known_loss_m) or known_loss_m < 0):
        raise ValueError("Known suction loss must be nonnegative.")
    kwargs = dict(water_type=water_type, temperature_C=temperature_C,
                  pressure_MPa_abs=surface_pressure_bar_abs*0.1)
    if water_type == "seawater":
        kwargs.update(EC_value=ec_ms_cm, EC_unit="mS/cm",
                      conductivity_temperature_mode="in_situ")
    props = calculate_water_properties(**kwargs)
    rho = props["density_kg_m3"]
    nu = props["kinematic_viscosity_m2_s"]
    pv = props["vapor_pressure_MPa"]*1e6
    if pv is None:
        raise ValueError("Vapor pressure unavailable for this temperature.")
    if inside_diameter_mm <= 0:
        raise ValueError("Internal diameter must be positive.")
    if any(x < 0 for x in (flow_m3h, length_m, roughness_mm, fittings_k)):
        raise ValueError("Flow, length, roughness and K must be nonnegative.")
    d = inside_diameter_mm / 1000
    v = (flow_m3h/3600)/(math.pi*d*d/4)
    re = v*d/nu
    if re == 0:
        f = 0
    elif re < 2300:
        f = 64/re
    else:
        # Churchill 1977, continuous correlation across regimes.
        a = (2.457*math.log(1/((7/re)**0.9 + 0.27*(roughness_mm/1000)/d)))**16
        b = (37530/re)**16
        f = 8*((8/re)**12 + (a+b)**(-1.5))**(1/12)
    calculated_loss = (f*length_m/d + fittings_k)*v*v/(2*G)
    loss = calculated_loss if known_loss_m is None else known_loss_m
    npsha = (surface_pressure_bar_abs*1e5-pv)/(rho*G) + static_height_m-loss
    margin = npsha-npshr_m
    inlet_pressure_abs_pa = surface_pressure_bar_abs*1e5 + rho*G*(static_height_m-loss-v*v/(2*G))
    return dict(npsha_m=npsha, npshr_m=npshr_m, margin_m=margin,
                ratio=npsha/npshr_m if npshr_m > 0 else None,
                velocity_ms=v, reynolds=re, darcy_f=f, loss_m=loss,
                calculated_loss_m=calculated_loss, density_kg_m3=rho,
                vapor_pressure_kpa=pv/1000, suction_pressure_bar_abs=inlet_pressure_abs_pa/1e5,
                fluid_warnings=props.get("warnings", []),
                status="INSUFFICIENT MARGIN" if margin <= 0 else "POSITIVE MARGIN - VERIFY OEM REQUIREMENT")
