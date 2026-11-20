# Pump Energy Solver

Interactive Python CLI that **calculates every quantity supported by the available input data**, using the full mechanical energy equation, continuity, and pump-power relations. No external dependencies. Python 3.9+.

## Install and run

```bash
git clone https://github.com/alizarei-eng/pump-energy-solver.git
cd pump-energy-solver
python pump_energy.py
```

On Windows: `py pump_energy.py`.

## How to use

1. Run the script. All fields initially show **Unknown**.
2. Press **E**, select the numbered parameter, and enter its value. Blank clears a value; **B** cancels.
3. Enter only known values. Use **0** explicitly for known zero head loss or elevation difference. Neither is assumed zero automatically.
4. Press **C**. The program iteratively solves all supported equations, showing each parameter as **INPUT**, **CALCULATED**, or **INSUFFICIENT DATA**.
5. Press Enter to return to the input editor. Change any value and press **C** again. Calculated results never overwrite user inputs.
6. **R** clears inputs; **0** exits. Contradictory supplied values produce warnings.

## Example: textbook question 4

Enter:

| Input | Value |
|---|---:|
| D1 | 40 mm |
| D2 | 80 mm |
| V1 | 40 m/s |
| dP | 800 kPa |
| rho | 1000 kg/m³ |
| eta | 80 % |
| dz | 0 m |
| hL | 0 m |

Expected (approximately): `Q=180.96 m³/h`, `V2=10 m/s`, `Hp=5.10 m`, `Ph=2.513 kW`, `Ps=3.142 kW`.

The book's answer `16π kW` applies the pressure-only power approximation; this program **does not use that approximation**. The full mechanical energy equation includes the velocity-head change.

## Equations and units

```text
Q = (pi/4) * D1² * V1 = (pi/4) * D2² * V2
dP = P2 - P1
Hp = dP/(rho*g) + (V2²-V1²)/(2*g) + dz + hL
Ph = rho*g*Q*Hp
Ps = Ph/(eta/100)
```

Internally, SI units are used. CLI units: diameter mm, velocity m/s, flow m³/h, pressure kPa (gauge), head/elevation m, density kg/m³, power kW, efficiency percent. `g=9.80665 m/s²`.

The engine can also solve inverse problems (for example shaft power + efficiency → hydraulic power, or known flow and speed → diameter).

## Assumptions and limitations

- Steady, incompressible, single-inlet/single-outlet flow; kinetic-energy correction factors are taken as 1.
- `hL` is the **total head loss between the selected sections**, and must be supplied if relevant. `dz=z2-z1`.
- Pressures are gauge values with a common reference; `dP=P2-P1`.
- `Ps` is **mechanical shaft power**, not electric input power.
- Reverse solutions requiring square roots may have sign ambiguities; the tool uses nonnegative velocities.
- A negative computed pump head or hydraulic power may indicate a turbine-like operating condition; this first version targets pumps and flags negative power.
- Missing independent data remain unknown; no water density, efficiency, head loss, or elevation defaults are silently imposed.
- This is a preliminary engineering tool. Validate against hand calculations and equipment curves before design decisions.
