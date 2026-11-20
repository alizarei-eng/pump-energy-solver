"""Tkinter desktop interface for the existing Pump Energy Solver engine."""
import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from pump_energy import FIELDS, NONNEGATIVE, POSITIVE, G, solve
from water_properties import calculate_water_properties
PRESSURE_TO_KPA = {"bar": 100.0, "psi": 6.894757293168, "kPa": 1.0, "Pa": 0.001}
PRESSURE_KEYS = {"P1", "P2", "dP"}

AUTHOR = "Ali_zarei_eng"

class PumpEnergyApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PUMP ENERGY SOLVER")
        self.geometry("940x730")
        self.minsize(780, 580)
        self.entries = {}
        self.fluid = tk.StringVar(value="seawater")
        self.temperature = tk.StringVar(value="30")
        self.ec = tk.StringVar(value="58")
        self.pressure_unit = tk.StringVar(value="kPa")
        self.report = None
        self._build()

    def _build(self):
        heading = ttk.Frame(self, padding=(16, 12))
        heading.pack(fill="x")
        ttk.Label(heading, text="PUMP ENERGY SOLVER", font=("Segoe UI", 19, "bold")).pack(anchor="w")
        ttk.Label(heading, text=f"Developed by {AUTHOR}  |  Full mechanical energy equation", font=("Segoe UI", 10)).pack(anchor="w")

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=16, pady=8)
        tab_names = ["Flow & Geometry", "Pressure & Elevation", "Fluid & Losses",
                     "Pump Performance", "Results & Report"]
        self.tab_frames = {}
        for name in tab_names:
            tab = ttk.Frame(self.tabs, padding=16)
            self.tabs.add(tab, text=name)
            self.tab_frames[name] = tab

        groups = {
            "Flow & Geometry": ["Q", "D1", "D2", "V1", "V2"],
            "Pressure & Elevation": ["P1", "P2", "dP", "dz"],
            "Fluid & Losses": ["hL"],
            "Pump Performance": ["Hp", "eta", "Ph", "Ps"],
        }
        for tab_name, keys in groups.items():
            frame = ttk.LabelFrame(self.tab_frames[tab_name],
                                   text="Known parameters (leave unknown values blank)", padding=14)
            frame.pack(anchor="nw", fill="x")
            for row, key in enumerate(keys):
                title, unit = FIELDS[key]
                ttk.Label(frame, text=f"{title} ({key})").grid(
                    row=row, column=0, sticky="w", padx=(0, 12), pady=7)
                entry = ttk.Entry(frame, width=10)
                entry.grid(row=row, column=1, sticky="w", pady=7)
                ttk.Label(frame, text=unit if key not in PRESSURE_KEYS else "selected unit").grid(
                    row=row, column=2, sticky="w", padx=10, pady=7)
                self.entries[key] = entry

        pressure_tab = self.tab_frames["Pressure & Elevation"]
        pressure_settings = ttk.LabelFrame(pressure_tab, text="Pressure units", padding=12)
        pressure_settings.pack(fill="x", pady=12)
        ttk.Label(pressure_settings, text="Pressure unit").pack(side="left", padx=(0, 10))
        ttk.Combobox(pressure_settings, textvariable=self.pressure_unit,
                     values=list(PRESSURE_TO_KPA), state="readonly", width=8).pack(side="left")
        ttk.Label(pressure_settings, text="Applies to P1, P2 and dP.").pack(side="left", padx=14)

        fluid_tab = self.tab_frames["Fluid & Losses"]
        fluid_frame = ttk.LabelFrame(fluid_tab, text="Fluid properties (automatic density)", padding=12)
        fluid_frame.pack(fill="x", pady=12)
        ttk.Label(fluid_frame, text="Fluid").grid(row=0, column=0, sticky="w", pady=7)
        ttk.Combobox(fluid_frame, textvariable=self.fluid,
                     values=["freshwater", "seawater"], state="readonly", width=14).grid(
                         row=0, column=1, sticky="w", padx=12, pady=7)
        ttk.Label(fluid_frame, text="Temperature [°C]").grid(row=1, column=0, sticky="w", pady=7)
        ttk.Entry(fluid_frame, textvariable=self.temperature, width=10).grid(
            row=1, column=1, sticky="w", padx=12, pady=7)
        ttk.Label(fluid_frame, text="EC [mS/cm] (in-situ)").grid(row=2, column=0, sticky="w", pady=7)
        self.ec_entry = ttk.Entry(fluid_frame, textvariable=self.ec, width=10)
        self.ec_entry.grid(row=2, column=1, sticky="w", padx=12, pady=7)
        self.fluid.trace_add("write", lambda *_: self.ec_entry.configure(
            state="normal" if self.fluid.get() == "seawater" else "disabled"))

        controls = ttk.Frame(self, padding=(16, 8))
        controls.pack(fill="x")
        ttk.Button(controls, text="Calculate", command=self.calculate).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Clear inputs", command=self.clear_inputs).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Clear results", command=self.clear_results).pack(side="left", padx=(0, 8))
        self.export_button = ttk.Button(controls, text="Export TXT", command=self.export_txt, state="disabled")
        self.export_button.pack(side="left")

        output_frame = ttk.LabelFrame(self.tab_frames["Results & Report"],
                                      text="Detailed calculation results", padding=8)
        output_frame.pack(fill="both", expand=True)
        summary = ttk.LabelFrame(self.tab_frames["Results & Report"],
                                 text="Calculation summary", padding=8)
        summary.pack(fill="x", before=output_frame, pady=(0, 8))
        self.summary_label = ttk.Label(summary, text="Calculate to display pump performance.",
                                       font=("Segoe UI", 10))
        self.summary_label.pack(anchor="w")
        self.output = tk.Text(output_frame, wrap="none", font=("Consolas", 10), height=17)
        self.output.grid(row=0, column=0, sticky="nsew")
        sy = ttk.Scrollbar(output_frame, orient="vertical", command=self.output.yview)
        sy.grid(row=0, column=1, sticky="ns")
        sx = ttk.Scrollbar(output_frame, orient="horizontal", command=self.output.xview)
        sx.grid(row=1, column=0, sticky="ew")
        self.output.configure(yscrollcommand=sy.set, xscrollcommand=sx.set, state="disabled")
        output_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)
        self._display("Enter only the values you know, then click Calculate.\n"
                      "Unknown values are not assumed to be zero.\n"
                      "Shaft power (Ps) is mechanical power, not electrical input power.")

    def _display(self, text):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")

    def clear_results(self):
        self.report = None
        self.export_button.configure(state="disabled")
        self._display("Results cleared.")\n        self.summary_label.configure(text="Calculate to display pump performance.")

    def clear_inputs(self):
        for entry in self.entries.values():
            entry.delete(0, "end")
        self.clear_results()

    def calculate(self):
        inputs = {}
        for key, entry in self.entries.items():
            raw = entry.get().strip()
            if not raw:
                continue
            try:
                value = float(raw)
                if not math.isfinite(value):
                    raise ValueError
                if key in NONNEGATIVE and value < 0:
                    raise ValueError
                if key in POSITIVE and value <= 0:
                    raise ValueError
                if key == "eta" and value > 100:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid input", f"{key}: enter a finite number in the permitted physical range.")
                entry.focus_set()
                return
            inputs[key] = value
        if not inputs:
            messagebox.showinfo("No inputs", "Enter at least one known parameter.")
            return
        try:
            t = float(self.temperature.get())
            if not math.isfinite(t):
                raise ValueError("Temperature must be finite")
            kwargs = {"temperature_C": t, "water_type": self.fluid.get(), "pressure_MPa_abs": 0.101325}
            if self.fluid.get() == "seawater":
                ec = float(self.ec.get())
                if not math.isfinite(ec) or ec <= 0:
                    raise ValueError("Seawater EC must be positive and finite")
                kwargs.update(EC_value=ec, EC_unit="mS/cm", conductivity_temperature_mode="in_situ")
            props = calculate_water_properties(**kwargs)
            inputs["rho"] = props["density_kg_m3"]
        except (ValueError, ImportError, ArithmeticError, NotImplementedError) as exc:
            messagebox.showerror("Fluid properties", str(exc))
            return
        selected_unit = self.pressure_unit.get()
        for pressure_key in PRESSURE_KEYS:
            if pressure_key in inputs:
                inputs[pressure_key] *= PRESSURE_TO_KPA[selected_unit]
        values, sources, errors = solve(inputs)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "PUMP ENERGY SOLVER", f"Developed by {AUTHOR}",
            f"Generated: {timestamp}", "=" * 82,
            f"Fluid: {self.fluid.get()}",
            f"Temperature: {self.temperature.get()} °C",
            f"Density (calculated): {props['density_kg_m3']:.4f} kg/m3",
            f"Density method: {props['method']}",
            f"Pressure unit: {selected_unit}",
            "KNOWN INPUTS",
        ]
        for key, value in inputs.items():
            if key == "rho":
                continue
            label, display_unit = FIELDS[key]
            if key in PRESSURE_KEYS:
                value /= PRESSURE_TO_KPA[selected_unit]
                display_unit = selected_unit
            lines.append(f"{label:36} {value:>14.8g} {display_unit}")
        lines.extend(["", "RESULTS", "-" * 82])
        for key, (label, display_unit) in FIELDS.items():
            if key == "rho":
                continue
            if key in PRESSURE_KEYS:
                display_unit = selected_unit
            if key in values:
                value = values[key]
                if key in PRESSURE_KEYS:
                    value /= PRESSURE_TO_KPA[selected_unit]
                lines.append(f"{label:36} {value:>14.8g} {display_unit:<7} [{sources[key]}]")
            else:
                lines.append(f"{label:36} {'Unknown':>14} {display_unit:<7} [INSUFFICIENT DATA]")
        lines.extend(["", "DERIVED QUANTITIES"])
        if "Q" in values:
            lines.append(f"Flow rate (m3/s): {values['Q']/3600:.8g}")
        for key in ("D1", "D2"):
            if key in values:
                lines.append(f"Area {key[-1]} (m2): {math.pi*(values[key]/1000)**2/4:.8g}")
        if all(k in values for k in ("dP", "rho")):
            lines.append(f"Pressure head (m): {values['dP']*1000/(values['rho']*G):.8g}")
        if all(k in values for k in ("V1", "V2")):
            lines.append(f"Velocity head change (m): {(values['V2']**2-values['V1']**2)/(2*G):.8g}")
        if props.get("warnings"):
            lines.extend(["", "FLUID MODEL NOTES"])
            lines.extend("- " + warning for warning in props["warnings"])
        if errors:
            lines.extend(["", "WARNING: INCONSISTENT DATA"])
            lines.extend(f"- {error}" for error in errors)
        lines.extend(["", "EQUATIONS",
                      "Hp = dP/(rho*g) + (V2^2-V1^2)/(2*g) + dz + hL",
                      "Ph = rho*g*Q*Hp; Ps = Ph/(eta/100)",
                      "", "NOTES",
                      "Steady incompressible flow; kinetic correction factors = 1.",
                      "Input zero explicitly when elevation difference or head loss is known zero.",
                      "Ps is shaft power, not electric input power.",
                      "Validate calculations against pump curves and field measurements."])
        self.report = "\n".join(lines) + "\n"
        self._display(self.report)
        self.export_button.configure(state="normal")

    def export_txt(self):
        if self.report is None:
            return
        default = "pump_energy_report_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt"
        path = filedialog.asksaveasfilename(title="Export calculation report", defaultextension=".txt",
                                            initialfile=default, filetypes=[("Text files", "*.txt")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as file:
                file.write(self.report)
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc))
            return
        messagebox.showinfo("Export complete", f"Report saved to:\n{path}")


if __name__ == "__main__":
    PumpEnergyApp().mainloop()
