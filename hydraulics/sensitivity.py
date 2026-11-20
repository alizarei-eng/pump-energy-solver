"""Finite-difference sensitivity of serial-pipe system head at a specified flow."""
from copy import deepcopy
from hydraulics.system_curve import calculate_system_curve


def analyze_sensitivity(segments, transitions, dz, dp, rho, nu, flow, change=0.10):
    """Compare ±relative changes at fixed flow; return ranked dimensionless sensitivities.

    Diameter changes retain the specified transition K model. Static elevation
    is excluded because its baseline may be zero or negative.
    """
    if not 0 < change < 1:
        raise ValueError("Sensitivity change must be between 0 and 1.")
    if flow <= 0:
        raise ValueError("Sensitivity flow must be positive.")

    def head(parts, q=flow, t=transitions):
        return calculate_system_curve(parts, t, dz, dp, rho, nu, q, 2)[2][-1]

    baseline = head(segments)
    parameters = (
        ("Flow rate", "flow"),
        ("Pipe length", "length"),
        ("Internal diameter", "diameter"),
        ("Pipe roughness", "roughness"),
        ("Fittings K", "k"),
    )
    results = []
    for label, key in parameters:
        if key != "flow" and not any(seg[key] > 0 for seg in segments):
            continue
        values = []
        for factor in (1 - change, 1 + change):
            modified = deepcopy(segments)
            if key == "flow":
                values.append(head(modified, flow * factor))
            else:
                for seg in modified:
                    seg[key] *= factor
                # Diameter variation changes geometry of the transitions:
                # recalculate sudden-transition K using the same geometry model.
                adjusted = []
                for i, (kind, k, reference) in enumerate(transitions):
                    if kind == "Sudden expansion":
                        d1, d2 = modified[i]["diameter"], modified[i + 1]["diameter"]
                        k = (1 - (d1 / d2) ** 2) ** 2
                    elif kind == "Sudden contraction":
                        d1, d2 = modified[i]["diameter"], modified[i + 1]["diameter"]
                        k = 0.42 * (1 - (d2 / d1) ** 2)
                    adjusted.append((kind, k, reference))
                values.append(head(modified, t=adjusted))
        low, high = values
        derivative = (high - low) / (2 * change)
        elasticity = derivative / baseline if baseline != 0 else None
        results.append({"parameter": label, "head_minus_m": low,
                        "head_plus_m": high, "derivative_m": derivative,
                        "elasticity": elasticity})
    results.sort(key=lambda row: abs(row["derivative_m"]), reverse=True)
    return {"baseline_head_m": baseline, "flow_m3h": flow,
            "change": change, "results": results}
