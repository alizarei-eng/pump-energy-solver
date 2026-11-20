"""Pump Energy Solver: interactive, bidirectional, no external dependencies."""
import math

G = 9.80665
FIELDS = {
    "D1": ("Inlet diameter", "mm"), "D2": ("Outlet diameter", "mm"),
    "V1": ("Inlet velocity", "m/s"), "V2": ("Outlet velocity", "m/s"),
    "Q": ("Flow rate", "m3/h"),
    "P1": ("Inlet gauge pressure", "kPa"), "P2": ("Outlet gauge pressure", "kPa"),
    "dP": ("Pressure difference P2-P1", "kPa"),
    "dz": ("Elevation difference z2-z1", "m"),
    "hL": ("Head loss", "m"),
    "rho": ("Density", "kg/m3"), "eta": ("Pump efficiency", "%"),
    "Hp": ("Pump head", "m"), "Ph": ("Hydraulic power", "kW"),
    "Ps": ("Pump shaft power", "kW"),
}
NONNEGATIVE = {"D1", "D2", "V1", "V2", "Q", "hL", "rho", "eta", "Ph", "Ps"}
POSITIVE = {"D1", "D2", "rho", "eta"}
TOL = 1e-6


def solve(inputs):
    """Iteratively solve each equation in either direction; flag contradictions."""
    values = dict(inputs)
    source = {k: "INPUT" for k in values}
    errors = []

    def set_value(key, number, reason):
        if number is None or not math.isfinite(number):
            return False
        if key in NONNEGATIVE and number < -1e-10:
            errors.append(f"{key}: negative result from {reason}")
            return False
        if key in POSITIVE and number <= 0:
            errors.append(f"{key}: nonpositive result from {reason}")
            return False
        if key == "eta" and number > 100 + 1e-8:
            errors.append("Efficiency must not exceed 100%")
            return False
        if key in values:
            if not math.isclose(values[key], number, rel_tol=TOL, abs_tol=1e-7):
                errors.append(f"Conflict for {key}: {values[key]:.7g} vs {number:.7g} ({reason})")
            return False
        values[key] = max(0, number) if key in NONNEGATIVE else number
        source[key] = "CALCULATED"
        return True

    def relation(keys, fn, reason):
        missing = [k for k in keys if k not in values]
        if len(missing) > 1:
            return False
        try:
            outcome = fn(values, missing[0] if missing else None)
            if outcome is None:
                return False
            if missing:
                return set_value(missing[0], outcome, reason)
            # Consistency checks use the same equation solving for its last variable.
            last = keys[-1]
            expected = fn(values, last)
            if expected is not None:
                set_value(last, expected, reason)
        except (ZeroDivisionError, ValueError, OverflowError):
            return False
        return False

    def area_relation(v, unknown, d, vel):
        q = v.get("Q")
        diameter = v.get(d)
        speed = v.get(vel)
        if unknown == "Q":
            return math.pi * (diameter / 1000)**2 / 4 * speed * 3600
        if unknown == vel:
            return q / 3600 / (math.pi * (diameter / 1000)**2 / 4)
        if unknown == d:
            if speed == 0:
                return None
            return math.sqrt(4 * q / 3600 / (math.pi * speed)) * 1000
        return q / 3600 / (math.pi * (diameter / 1000)**2 / 4)

    def pressure(v, unknown):
        if unknown == "P1":
            return v["P2"] - v["dP"]
        if unknown == "P2":
            return v["P1"] + v["dP"]
        return v["P2"] - v["P1"]

    def head(v, unknown):
        # Hp = dP*1000/(rho*g) + (V2²-V1²)/(2*g) + dz + hL
        if unknown == "rho":
            remainder = v["Hp"] - (v["V2"]**2-v["V1"]**2)/(2*G)-v["dz"]-v["hL"]
            return v["dP"]*1000/(G*remainder)
        pressure_head = v["dP"]*1000/(v["rho"]*G) if unknown != "dP" else 0
        if unknown == "dP":
            return (v["Hp"]-(v["V2"]**2-v["V1"]**2)/(2*G)-v["dz"]-v["hL"])*v["rho"]*G/1000
        if unknown == "V1":
            square = v["V2"]**2+2*G*(pressure_head+v["dz"]+v["hL"]-v["Hp"])
            return math.sqrt(square) if square >= 0 else None
        if unknown == "V2":
            square = v["V1"]**2+2*G*(v["Hp"]-pressure_head-v["dz"]-v["hL"])
            return math.sqrt(square) if square >= 0 else None
        kinetic = (v["V2"]**2-v["V1"]**2)/(2*G)
        if unknown == "dz":
            return v["Hp"]-pressure_head-kinetic-v["hL"]
        if unknown == "hL":
            return v["Hp"]-pressure_head-kinetic-v["dz"]
        return pressure_head+kinetic+v["dz"]+v["hL"]

    def hydraulic(v, unknown):
        # Ph[kW] = rho*g*Q[m3/h]*Hp / 3.6e6
        if unknown == "Ph" or unknown is None:
            return v["rho"]*G*v["Q"]*v["Hp"]/3.6e6
        return v["Ph"]*3.6e6/(G*math.prod(v[k] for k in ("rho", "Q", "Hp") if k != unknown))

    def shaft(v, unknown):
        # Ps = Ph/(eta/100)
        if unknown == "Ps" or unknown is None:
            return v["Ph"]*100/v["eta"]
        if unknown == "Ph":
            return v["Ps"]*v["eta"]/100
        return 100*v["Ph"]/v["Ps"]

    for _ in range(20):
        count = len(values)
        for d, vel in (("D1", "V1"), ("D2", "V2")):
            relation(("Q", d, vel), lambda v, u, d=d, vel=vel: area_relation(v, u, d, vel), "continuity")
        relation(("P1", "P2", "dP"), pressure, "pressure difference")
        relation(("Hp", "dP", "rho", "V1", "V2", "dz", "hL"), head, "full mechanical energy")
        relation(("Ph", "rho", "Q", "Hp"), hydraulic, "hydraulic power")
        relation(("Ps", "Ph", "eta"), shaft, "shaft power")
        if len(values) == count:
            break
    return values, source, sorted(set(errors))


def main():
    inputs = {}
    print("PUMP ENERGY SOLVER | Full energy equation | No hidden defaults")
    while True:
        print("\nPARAMETERS:")
        keys = list(FIELDS)
        for i, k in enumerate(keys, 1):
            title, unit = FIELDS[k]
            val = f"{inputs[k]:.8g}" if k in inputs else "Unknown"
            print(f"{i:2}. {title:32} {val:>12} {unit}")
        print("\nE Edit | C Calculate all | R Reset | 0 Exit")
        action = input("Select: ").strip().lower()
        if action == "0":
            return
        if action == "r":
            inputs.clear()
        elif action == "e":
            item = input("Parameter number (B back): ").strip().lower()
            if item == "b":
                continue
            if not item.isdigit() or not 1 <= int(item) <= len(keys):
                print("Invalid selection.")
                continue
            key = keys[int(item)-1]
            raw = input(f"{key} [{FIELDS[key][1]}] (blank = unknown, B = back): ").strip()
            if raw.lower() == "b":
                continue
            if not raw:
                inputs.pop(key, None)
                continue
            try:
                number = float(raw)
                if not math.isfinite(number):
                    raise ValueError
                if key in NONNEGATIVE and number < 0:
                    raise ValueError
                if key in POSITIVE and number == 0:
                    raise ValueError
                if key == "eta" and number > 100:
                    raise ValueError
                inputs[key] = number
            except ValueError:
                print("Invalid number or physical range.")
        elif action == "c":
            values, source, errors = solve(inputs)
            print("\n========== RESULTS ==========")
            for key, (title, unit) in FIELDS.items():
                if key in values:
                    print(f"{title:32} {values[key]:>12.7g} {unit:6} [{source[key]}]")
                else:
                    print(f"{title:32} {'Unknown':>12} {unit:6} [INSUFFICIENT DATA]")
            if "Q" in values:
                print(f"Flow rate (m3/s): {values['Q']/3600:.7g}")
            for k in ("D1", "D2"):
                if k in values:
                    print(f"Area {k[-1]} (m2): {math.pi*(values[k]/1000)**2/4:.7g}")
            if all(k in values for k in ("dP", "rho")):
                print(f"Pressure head (m): {values['dP']*1000/(values['rho']*G):.7g}")
            if all(k in values for k in ("V1", "V2")):
                print(f"Velocity head change (m): {(values['V2']**2-values['V1']**2)/(2*G):.7g}")
            if errors:
                print("\nWARNING: INCONSISTENT DATA")
                for message in errors:
                    print("-", message)
            print("\nHp=dP/(rho*g)+(V2^2-V1^2)/(2*g)+dz+hL")
            print("Ph=rho*g*Q*Hp; Ps=Ph/(eta/100)")
            print("Assumptions: steady incompressible flow; kinetic correction factors = 1.")
            print("Input zero explicitly for known zero elevation difference or head loss.")
            input("\nEnter to edit inputs...")
        else:
            print("Invalid command.")


if __name__ == "__main__":
    main()
