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
KW_PER_METRIC_HP = 0.73549875
PE_MRS_MPA = {"PE80": 8.0, "PE100": 10.0, "PE100-RC": 10.0}
SDR_OPTIONS = ("6", "7.4", "9", "11", "13.6", "17", "17.6", "21", "26", "33", "41")
PIPE_TYPES = ("HDPE / PE", "PVC", "Steel", "Other")

class PumpEnergyApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PUMP ENERGY SOLVER")
        self.geometry("940x730")
        self.minsize(780, 580)
        self.entries = {}
        self.pipe_widgets = {}
        self.pipe_types = {}
        self.pipe_od = {}
        self.pipe_sdr = {}
        self.pipe_grade = {}
        self.curve_rows = []
        self.curve_canvas = None
        self.curve_figure = None
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
                     "Pump Performance", "Pump Q-H Curve", "Results & Report"]
        self.tab_frames = {}
        for name in tab_names:
            tab = ttk.Frame(self.tabs, padding=16)
            self.tabs.add(tab, text=name)
            self.tab_frames[name] = tab

        groups = {
            "Flow & Geometry": ["Q", "V1", "V2"],
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

        geometry_tab = self.tab_frames["Flow & Geometry"]
        for section, key in (("Inlet", "D1"), ("Outlet", "D2")):
            pipe_frame = ttk.LabelFrame(geometry_tab, text=f"{section} pipe geometry", padding=10)
            pipe_frame.pack(fill="x", pady=7)
            pipe_type = tk.StringVar(value="HDPE / PE")
            od = tk.StringVar()
            sdr = tk.StringVar(value="11")
            grade = tk.StringVar(value="PE100")
            self.pipe_types[key] = pipe_type
            self.pipe_od[key] = od
            self.pipe_sdr[key] = sdr
            self.pipe_grade[key] = grade
            ttk.Label(pipe_frame, text="Pipe material").grid(row=0, column=0, sticky="w", padx=5, pady=5)
            ttk.Combobox(pipe_frame, textvariable=pipe_type, values=PIPE_TYPES,
                         state="readonly", width=14).grid(row=0, column=1, padx=5, pady=5)
            ttk.Label(pipe_frame, text="Outside diameter [mm]").grid(row=0, column=2, padx=5)
            od_entry = ttk.Entry(pipe_frame, textvariable=od, width=10)
            od_entry.grid(row=0, column=3, padx=5)
            ttk.Label(pipe_frame, text="SDR").grid(row=1, column=0, sticky="w", padx=5, pady=5)
            sdr_entry = ttk.Combobox(pipe_frame, textvariable=sdr, values=SDR_OPTIONS, width=11)
            sdr_entry.grid(row=1, column=1, padx=5, pady=5)
            ttk.Label(pipe_frame, text="PE grade").grid(row=1, column=2, padx=5)
            grade_entry = ttk.Combobox(pipe_frame, textvariable=grade, values=list(PE_MRS_MPA),
                                       state="readonly", width=11)
            grade_entry.grid(row=1, column=3, padx=5)
            ttk.Label(pipe_frame, text="Inside diameter [mm]").grid(row=2, column=0, sticky="w", padx=5, pady=5)
            id_entry = ttk.Entry(pipe_frame, width=10)
            id_entry.grid(row=2, column=1, padx=5, pady=5)
            self.entries[key] = id_entry
            ttk.Label(pipe_frame, text="For non-PE pipes, enter the measured ID.").grid(
                row=2, column=2, columnspan=2, sticky="w", padx=5)
            self.pipe_widgets[key] = (od_entry, sdr_entry, grade_entry, id_entry)
            pipe_type.trace_add("write", lambda *_args, k=key: self._toggle_pipe(k))
            self._toggle_pipe(key)

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

        curve_tab = self.tab_frames["Pump Q-H Curve"]
        ttk.Label(curve_tab, text="Pump Q-H characteristic points", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(curve_tab, text="Enter catalog or measured flow and head pairs. Units: m3/h and m.").pack(anchor="w", pady=8)
        bar = ttk.Frame(curve_tab)
        bar.pack(fill="x")
        ttk.Button(bar, text="Add row", command=self.add_curve_row).pack(side="left", padx=4)
        ttk.Button(bar, text="Remove last row", command=self.remove_curve_row).pack(side="left", padx=4)
        ttk.Button(bar, text="Clear table", command=self.clear_curve_rows).pack(side="left", padx=4)
        ttk.Button(bar, text="Calculate Q-H", command=self.calculate_curve).pack(side="left", padx=14)
        content = ttk.Frame(curve_tab)
        content.pack(fill="both", expand=True, pady=10)
        self.curve_frame = ttk.LabelFrame(content, text="Flow - Head Table", padding=10)
        self.curve_frame.pack(side="left", fill="y", padx=(0, 12))
        self.curve_plot_frame = ttk.LabelFrame(content, text="Q-H Diagram", padding=8)
        self.curve_plot_frame.pack(side="left", fill="both", expand=True)
        self.curve_status = ttk.Label(curve_tab, text="Enter at least two Q-H points, then click Calculate Q-H.")
        self.curve_status.pack(anchor="w")
        for column, label in enumerate(("Point", "Flow Q (m3/h)", "Head H (m)")):
            ttk.Label(self.curve_frame, text=label).grid(row=0, column=column, padx=12, pady=6)
        for _ in range(6):
            self.add_curve_row()

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

    def calculate_curve(self):
        try:
            points = self.read_curve()
            if len(points) < 2:
                raise ValueError("At least two complete Q-H points are required.")
        except ValueError as exc:
            messagebox.showerror("Pump Q-H curve", str(exc))
            return
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError:
            messagebox.showerror("Missing dependency", "Install matplotlib: python -m pip install matplotlib")
            return
        if self.curve_canvas is not None:
            self.curve_canvas.get_tk_widget().destroy()
            self.curve_canvas = None
        if self.curve_figure is not None:
            from matplotlib import pyplot as plt
            plt.close(self.curve_figure)
        self.curve_figure = Figure(figsize=(5.5, 4.0), dpi=100)
        axis = self.curve_figure.add_subplot(111)
        flows, heads = zip(*points)
        axis.plot(flows, heads, marker="o", linewidth=1.8)
        axis.set_xlabel("Flow rate Q (m3/h)")
        axis.set_ylabel("Pump head H (m)")
        axis.set_title("Pump Q-H characteristic")
        axis.grid(True, alpha=0.35)
        self.curve_figure.tight_layout()
        self.curve_canvas = FigureCanvasTkAgg(self.curve_figure, master=self.curve_plot_frame)
        self.curve_canvas.draw()
        self.curve_canvas.get_tk_widget().pack(fill="both", expand=True)
        self.curve_status.configure(text=f"Plotted {len(points)} points. Straight lines connect measured points; no extrapolation.")
        
    def add_curve_row(self):
        index = len(self.curve_rows) + 1
        label = ttk.Label(self.curve_frame, text=str(index))
        q = ttk.Entry(self.curve_frame, width=12)
        h = ttk.Entry(self.curve_frame, width=12)
        for column, widget in enumerate((label, q, h)):
            widget.grid(row=index, column=column, padx=12, pady=4, sticky="w")
        self.curve_rows.append((label, q, h))

    def remove_curve_row(self):
        if self.curve_rows:
            for widget in self.curve_rows.pop():
                widget.destroy()

    def clear_curve_rows(self):
        for _, q, h in self.curve_rows:
            q.delete(0, "end")
            h.delete(0, "end")
        if self.curve_canvas is not None:
            self.curve_canvas.get_tk_widget().destroy()
            self.curve_canvas = None
        self.curve_status.configure(text="Table cleared. Enter Q-H points and click Calculate Q-H.")

    def read_curve(self):
        points = []
        for index, (_, q_entry, h_entry) in enumerate(self.curve_rows, 1):
            q_text, h_text = q_entry.get().strip(), h_entry.get().strip()
            if not q_text and not h_text:
                continue
            if not q_text or not h_text:
                raise ValueError(f"Row {index}: enter both Q and H.")
            try:
                q, h = float(q_text), float(h_text)
            except ValueError:
                raise ValueError(f"Row {index}: invalid number.") from None
            if not all(math.isfinite(v) for v in (q, h)) or q < 0 or h < 0:
                raise ValueError(f"Row {index}: Q and H must be finite and nonnegative.")
            points.append((q, h))
        if len(set(q for q, _ in points)) != len(points):
            raise ValueError("Duplicate Q values in pump curve.")
        return sorted(points)

    def _toggle_pipe(self, key):
        od, sdr, grade, inner = self.pipe_widgets[key]
        pe = self.pipe_types[key].get() == "HDPE / PE"
        for widget in (od, sdr):
            widget.configure(state="normal" if pe else "disabled")
        grade.configure(state="readonly" if pe else "disabled")
        inner.configure(state="disabled" if pe else "normal")

    def _pipe_inputs(self, inputs):
        """Compute nominal PE bore and indicative 20 C pressure; not a certified PN."""
        notes = []
        for key in ("D1", "D2"):
            material = self.pipe_types[key].get()
            side = "Inlet" if key == "D1" else "Outlet"
            if material != "HDPE / PE":
                if key in inputs:
                    notes.append(f"{side}: {material}, specified inside diameter = {inputs[key]:.4f} mm")
                else:
                    notes.append(f"{side}: {material}, inside diameter unknown")
                continue
            od_text = self.pipe_od[key].get().strip()
            if not od_text:
                notes.append(f"{side}: PE diameter not specified")
                continue
            od = float(od_text)
            sdr = float(self.pipe_sdr[key].get())
            if not (math.isfinite(od) and od > 0 and math.isfinite(sdr) and sdr > 2):
                raise ValueError(f"{side}: OD must be positive and SDR must exceed 2.")
            inner = od * (1 - 2 / sdr)
            grade = self.pipe_grade[key].get()
            mrs = PE_MRS_MPA[grade]
            reference_bar = 20 * (mrs / 1.25) / (sdr - 1)
            inputs[key] = inner
            notes.append(
                f"{side}: PE {grade}, OD={od:g} mm, SDR={sdr:g}, "
                f"nominal wall={od/sdr:.3f} mm, calculated ID={inner:.3f} mm; "
                f"reference pressure={reference_bar:.2f} bar (20 C, C=1.25; NOT certified PN)"
            )
        return notes

    def _display(self, text):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")

    def clear_results(self):
        self.report = None
        self.export_button.configure(state="disabled")
        self._display("Results cleared.")
        self.summary_label.configure(text="Calculate to display pump performance.")

    def clear_inputs(self):
        for entry in self.entries.values():
            entry.delete(0, "end")
        for key in ("D1", "D2"):
            self.pipe_od[key].set("")
            self.pipe_sdr[key].set("11")
            self.pipe_grade[key].set("PE100")
        self.clear_curve_rows()
        self.clear_results()

    def calculate(self):
        try:
            curve_points = self.read_curve()
        except ValueError as exc:
            messagebox.showerror("Pump Q-H curve", str(exc))
            self.tabs.select(self.tab_frames["Pump Q-H Curve"])
            return
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
        try:
            pipe_notes = self._pipe_inputs(inputs)
        except (ValueError, KeyError) as exc:
            messagebox.showerror("Pipe geometry", str(exc))
            self.tabs.select(self.tab_frames["Flow & Geometry"])
            return
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
        lines.extend(["", "PUMP Q-H CURVE (CATALOG / FIELD DATA)"])
        if curve_points:
            lines.append("Flow Q [m3/h]    Pump head H [m]")
            for q, h in curve_points:
                lines.append(f"{q:14.6g}    {h:14.6g}")
        else:
            lines.append("No Q-H points entered.")
        lines.append("Reference table only; no curve fitting or interpolation.")
        lines.extend(["", "PIPE GEOMETRY AND REFERENCE PRESSURE"])
        lines.extend(pipe_notes)
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
        lines.extend(["", "POWER IN METRIC HORSEPOWER (PS / cv)"])
        for key, title in (("Ph", "Hydraulic power"), ("Ps", "Shaft power")):
            if key in values:
                lines.append(f"{title}: {values[key]/KW_PER_METRIC_HP:.5f} PS (metric hp)")
            else:
                lines.append(f"{title}: Unknown")
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
                      "1 metric horsepower (PS) = 0.73549875 kW.",
                      "PE reference pressure assumes 20 C and design coefficient C=1.25.",
                      "Check certified PN, temperature derating and manufacturer datasheet.",
                      "PE inside diameter is nominal; manufacturing tolerances apply.",
                      "Validate calculations against pump curves and field measurements."])
        self.report = "\n".join(lines) + "\n"
        self._display(self.report)
        def metric(key, unit):
            return f"{values[key]:.4g} {unit}" if key in values else "Unknown"
        horsepower = f"{values['Ps']/KW_PER_METRIC_HP:.3g} PS" if "Ps" in values else "Unknown"
        self.summary_label.configure(text=(
            f"Q: {metric('Q', 'm3/h')}    Hp: {metric('Hp', 'm')}    "
            f"Ph: {metric('Ph', 'kW')}    Ps: {metric('Ps', 'kW')} / {horsepower}"
        ))
        self.tabs.select(self.tab_frames["Results & Report"])
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
