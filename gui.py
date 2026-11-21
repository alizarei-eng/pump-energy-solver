"""Tkinter desktop interface for the existing Pump Energy Solver engine."""
import math
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from datetime import datetime
from pump_energy import FIELDS, NONNEGATIVE, POSITIVE, G, solve
from water_properties import calculate_water_properties
from hydraulics.system_curve import calculate_system_curve as compute_system_curve
from plotting.system_plot import build_system_figure
from hydraulics.sensitivity import analyze_sensitivity
PRESSURE_TO_KPA = {"bar": 100.0, "psi": 6.894757293168, "kPa": 1.0, "Pa": 0.001}
PRESSURE_KEYS = {"P1", "P2", "dP"}

AUTHOR = "Ali_zarei_eng"
KW_PER_METRIC_HP = 0.73549875
PE_MRS_MPA = {"PE80": 8.0, "PE100": 10.0, "PE100-RC": 10.0}
SDR_OPTIONS = ("6", "7.4", "9", "11", "13.6", "17", "17.6", "21", "26", "33", "41")
PIPE_TYPES = ("HDPE / PE", "PVC", "Steel", "Other")
FITTING_CATALOG = (
    ("90-degree elbow - long radius", 0.2),
    ("90-degree elbow - standard", 0.9),
    ("45-degree elbow", 0.4),
    ("Tee - straight run", 0.6),
    ("Tee - branch flow", 1.8),
    ("Gate valve - fully open", 0.15),
    ("Ball valve - fully open", 0.05),
    ("Globe valve - fully open", 10.0),
    ("Swing check valve", 2.0),
    ("Sharp-edged pipe entrance", 0.5),
    ("Pipe exit into large tank", 1.0),
)  # From pipe-pressure-loss-calculator/databases/fittings.json; indicative K values
SYSTEM_ROUGHNESS_MM = {"HDPE / PE": 0.0015, "PVC": 0.0015, "Steel": 0.045, "Other": 0.05}  # indicative clean-pipe references, not certified catalogs

class PumpEnergyApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PUMP ENERGY SOLVER")
        self.geometry("1120x790")
        self.minsize(650, 500)
        self.entries = {}
        self.pipe_widgets = {}
        self.pipe_types = {}
        self.pipe_od = {}
        self.pipe_sdr = {}
        self.pipe_grade = {}
        self.pipe_result_labels = {}
        self.curve_rows = []
        self.curve_canvas = None
        self.curve_figure = None
        self.system_vars = {}
        self.system_canvas = None
        self.system_report = None
        self.pump_selection_duty = None
        self.pump_selection_curve = None
        self.pump_selection_heads = None
        self.selection_canvas = None
        self.system_sensitivity_inputs = None
        self.system_segments = []
        self.system_selected_segment = tk.IntVar(value=0)
        self.system_units = tk.StringVar(value="SI")
        self.system_fluid = tk.StringVar(value="seawater")
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
                     "Pump Performance", "Pump Q-H Curve", "System H-Q Curve", "Pump Selection", "Results & Report"]
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
            ttk.Button(pipe_frame, text="Calculate", command=lambda k=key: self.calculate_pipe(k)).grid(
                row=3, column=0, padx=5, pady=7, sticky="w")
            result = ttk.Label(pipe_frame, text="Enter OD and SDR, then calculate.", wraplength=610)
            result.grid(row=3, column=1, columnspan=3, padx=5, pady=7, sticky="w")
            self.pipe_result_labels[key] = result

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

        system_tab = self.tab_frames["System H-Q Curve"]
        ttk.Label(system_tab, text="System Curve | Multi-segment pipe and fitting losses",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w")
        selectors = ttk.Frame(system_tab)
        selectors.pack(fill="x", pady=5)
        ttk.Label(selectors, text="Units").pack(side="left")
        ttk.Combobox(selectors, textvariable=self.system_units, values=("SI", "US"),
                     state="readonly", width=7).pack(side="left", padx=5)
        ttk.Label(selectors, text="Water type").pack(side="left", padx=(10, 0))
        ttk.Combobox(selectors, textvariable=self.system_fluid, values=("seawater", "freshwater"),
                     state="readonly", width=12).pack(side="left", padx=5)
        self.system_unit_note = ttk.Label(selectors, text="")
        self.system_unit_note.pack(side="left", padx=6)

        globals_box = ttk.LabelFrame(system_tab, text="System boundary conditions", padding=5)
        globals_box.pack(fill="x")
        specs = (("dz", "Elevation difference", "0"),
                 ("dp", "Pressure difference", "0"),
                 ("temp", "Water temperature", "30"),
                 ("ec", "In-situ EC (mS/cm)", "58"),
                 ("qmax", "Maximum flow", ""))
        self.system_widgets, self.system_unit_labels = {}, {}
        for index, (key, label, default) in enumerate(specs):
            col = (index % 4) * 3
            row = index // 4
            ttk.Label(globals_box, text=label).grid(row=row, column=col, sticky="w", padx=3, pady=3)
            var = tk.StringVar(value=default)
            self.system_vars[key] = var
            widget = ttk.Entry(globals_box, textvariable=var, width=10)
            widget.grid(row=row, column=col+1, padx=3)
            self.system_widgets[key] = widget
            unit = ttk.Label(globals_box, text="")
            unit.grid(row=row, column=col+2, sticky="w")
            self.system_unit_labels[key] = unit

        pipe_box = ttk.LabelFrame(system_tab, text="Pipe segments (series, no branches)", padding=5)
        pipe_box.pack(fill="x", pady=5)
        pipe_bar = ttk.Frame(pipe_box)
        pipe_bar.pack(fill="x")
        ttk.Button(pipe_bar, text="Add Segment", command=self.add_system_segment).pack(side="left", padx=3)
        ttk.Button(pipe_bar, text="Remove Selected", command=self.remove_system_segment).pack(side="left", padx=3)
        ttk.Label(pipe_bar, text="Selected segment for fittings:").pack(side="left", padx=(15, 4))
        self.system_segment_selector = ttk.Combobox(pipe_bar, state="readonly", width=10)
        self.system_segment_selector.pack(side="left")
        self.system_segment_selector.bind("<<ComboboxSelected>>", self._select_system_segment)
        self.system_segments_frame = ttk.Frame(pipe_box)
        self.system_segments_frame.pack(fill="x")
        for col, name in enumerate(("Segment", "Material", "Length", "OD (PE) / ID (other)", "SDR (PE)", "Roughness mm", "Fittings K", "Connection from previous")):
            ttk.Label(self.system_segments_frame, text=name).grid(row=0, column=col, padx=4, pady=3)

        fitting_box = ttk.LabelFrame(system_tab, text="Fittings for selected segment", padding=5)
        fitting_box.pack(fill="x", pady=4)
        self.system_fitting_frame = ttk.Frame(fitting_box)
        self.system_fitting_frame.pack(fill="x")
        self.system_fitting_widgets = []
        self.system_fitting_picker = tk.StringVar(value=FITTING_CATALOG[0][0])
        ttk.Combobox(self.system_fitting_frame, textvariable=self.system_fitting_picker,
                     values=[name for name, _ in FITTING_CATALOG], state="readonly", width=34).pack(side="left", padx=4)
        ttk.Label(self.system_fitting_frame, text="Quantity").pack(side="left")
        self.system_fitting_quantity = tk.StringVar(value="1")
        ttk.Spinbox(self.system_fitting_frame, textvariable=self.system_fitting_quantity,
                    from_=1, to=999, width=5).pack(side="left", padx=4)
        ttk.Button(self.system_fitting_frame, text="Add / Update", command=self._add_system_fitting).pack(side="left", padx=4)
        ttk.Button(self.system_fitting_frame, text="Remove", command=self._remove_system_fitting).pack(side="left", padx=4)
        self.system_fitting_summary = ttk.Label(fitting_box, text="No fittings for this segment.", wraplength=850)
        self.system_fitting_summary.pack(anchor="w", pady=3)

        plot_controls = ttk.Frame(system_tab)
        plot_controls.pack(fill="x", pady=5)
        ttk.Button(plot_controls, text="Calculate System Curve", command=self.calculate_system_curve).pack(side="left", padx=4)
        ttk.Button(plot_controls, text="Sensitivity ±10%", command=self.show_system_sensitivity).pack(side="left", padx=4)
        ttk.Button(plot_controls, text="Export System TXT", command=self.export_system_txt).pack(side="left", padx=4)
        ttk.Button(plot_controls, text="Save Project", command=self.save_system_project).pack(side="left", padx=4)
        ttk.Button(plot_controls, text="Open Project", command=self.load_system_project).pack(side="left", padx=4)
        self.system_status = ttk.Label(system_tab, text="Add pipe segments, then calculate.", anchor="w")
        self.system_status.pack(fill="x", padx=8, pady=(4, 1))
        self.system_result_label = ttk.Label(system_tab,
            text="Flow: --  |  System head: --  |  Hydraulic power: --",
            anchor="w", font=("TkDefaultFont", 11, "bold"))
        self.system_result_label.pack(fill="x", padx=8, pady=(1, 5))
        self.system_plot_frame = ttk.LabelFrame(system_tab, text="System H-Q diagram", padding=4)
        self.system_plot_frame.pack(fill="both", expand=True)
        self.system_units.trace_add("write", lambda *_: self._update_system_units())
        self.system_fluid.trace_add("write", lambda *_: self._toggle_system_fluid())
        self._update_system_units()
        self._toggle_system_fluid()
        self.add_system_segment()
        selection_tab = self.tab_frames["Pump Selection"]
        ttk.Label(selection_tab, text="Single pump sizing | System H-Q Curve duty at maximum flow",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 12))
        self.selection_duty_label = ttk.Label(selection_tab,
            text="Calculate System H-Q Curve first to import flow, head and hydraulic power.")
        self.selection_duty_label.pack(anchor="w", pady=(0, 12))
        efficiency_frame = ttk.LabelFrame(selection_tab, text="User-supplied efficiencies (%)", padding=12)
        efficiency_frame.pack(anchor="nw", fill="x")
        self.selection_pump_eta = tk.StringVar(value="75")
        self.selection_motor_eta = tk.StringVar(value="93")
        for row, (label, var) in enumerate((("Pump efficiency (hydraulic output / shaft input)", self.selection_pump_eta),
                                             ("Motor efficiency (shaft output / electrical input)", self.selection_motor_eta))):
            ttk.Label(efficiency_frame, text=label).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Entry(efficiency_frame, textvariable=var, width=12).grid(
                row=row, column=1, padx=12, pady=5)
        curve_input = ttk.LabelFrame(selection_tab, text="Manual Pump Q-H Curve", padding=8)
        curve_input.pack(fill="x", pady=6)
        rpm_row = ttk.Frame(curve_input)
        rpm_row.pack(fill="x", pady=(0, 4))
        ttk.Label(rpm_row, text="Reference RPM:").pack(side="left")
        self.selection_rpm = tk.StringVar(value="2900")
        ttk.Entry(rpm_row, textvariable=self.selection_rpm, width=10).pack(side="left", padx=6)

        # Fixed-height scrollable input table: adding points must not shrink the plot.
        table_container = ttk.Frame(curve_input)
        table_container.pack(fill="x", expand=False)
        points_canvas = tk.Canvas(table_container, height=120, highlightthickness=0)
        points_scroll = ttk.Scrollbar(table_container, orient="vertical",
                                      command=points_canvas.yview)
        points_canvas.configure(yscrollcommand=points_scroll.set)
        points_scroll.pack(side="right", fill="y")
        points_canvas.pack(side="left", fill="both", expand=True)
        points_frame = ttk.Frame(points_canvas)
        points_window = points_canvas.create_window((0, 0), window=points_frame, anchor="nw")
        points_frame.bind("<Configure>", lambda event: points_canvas.configure(
            scrollregion=points_canvas.bbox("all")))
        points_canvas.bind("<Configure>", lambda event: points_canvas.itemconfigure(
            points_window, width=event.width))
        ttk.Label(points_frame, text="Point").grid(row=0, column=0, sticky="w", padx=4)
        ttk.Label(points_frame, text="Flow Q (m3/h)").grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(points_frame, text="Head H (m)").grid(row=0, column=2, sticky="w", padx=4)
        points_frame.columnconfigure(1, weight=1)
        points_frame.columnconfigure(2, weight=1)
        self.selection_point_rows = []

        def add_point():
            row = len(self.selection_point_rows) + 1
            q_var, h_var = tk.StringVar(), tk.StringVar()
            ttk.Label(points_frame, text=f"Point {row}").grid(
                row=row, column=0, sticky="w", padx=4, pady=2)
            ttk.Entry(points_frame, textvariable=q_var, width=14).grid(
                row=row, column=1, sticky="ew", padx=4, pady=2)
            ttk.Entry(points_frame, textvariable=h_var, width=14).grid(
                row=row, column=2, sticky="ew", padx=4, pady=2)
            self.selection_point_rows.append((q_var, h_var))
            points_canvas.update_idletasks()
            points_canvas.yview_moveto(1.0)

        def remove_point():
            if len(self.selection_point_rows) <= 2:
                return
            row = len(self.selection_point_rows)
            for widget in points_frame.grid_slaves(row=row):
                widget.destroy()
            self.selection_point_rows.pop()
            points_canvas.configure(scrollregion=points_canvas.bbox("all"))

        buttons_frame = ttk.Frame(curve_input)
        buttons_frame.pack(fill="x", pady=(5, 0))
        ttk.Button(buttons_frame, text="Add Point", command=add_point).pack(
            side="left", padx=(0, 8))
        ttk.Button(buttons_frame, text="Remove Point", command=remove_point).pack(side="left")
        add_point()
        add_point()
        add_point()
        ttk.Button(selection_tab, text="Calculate pump & motor power",
                   command=self.calculate_pump_selection).pack(anchor="w", pady=12)
        self.selection_result_label = ttk.Label(selection_tab, text="No sizing calculation yet.",
            font=("Segoe UI", 11), justify="left")
        self.selection_result_label.pack(anchor="w", pady=6)
        self.selection_plot_frame = ttk.LabelFrame(selection_tab, text="Hydraulic & Electrical Power vs Flow", padding=4)
        self.selection_plot_frame.pack(fill="both", expand=True, pady=(8, 4))
        ttk.Label(selection_tab, text="Preliminary sizing only. Check manufacturer Q-H, efficiency and shaft-power curves.",
                  wraplength=750).pack(anchor="w", pady=12)
        results_tab = self.tab_frames["Results & Report"]
        controls = ttk.Frame(results_tab, padding=(0, 0, 0, 10))
        controls.pack(fill="x")
        ttk.Button(controls, text="Calculate Main Solver", command=self.calculate).pack(side="left", padx=(0, 8))
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

    def _system_factor(self, key, us=None):
        if us is None:
            us = self.system_units.get() == "US"
        if not us:
            return 1.0
        return {"dz": 3.280839895, "dp": 0.1450377377,
                "length": 3.280839895, "od": 1/25.4,
                "qmax": 4.402867539}.get(key, 1.0)

    def _update_system_units(self):
        current = self.system_units.get()
        previous = getattr(self, "_system_previous_units", current)
        if previous != current:
            for key in ("dz", "dp", "qmax"):
                var = self.system_vars[key]
                try:
                    val = float(var.get()) / self._system_factor(key, previous == "US")
                    var.set(f"{val * self._system_factor(key, current == 'US'):.10g}")
                except ValueError:
                    pass
            try:
                t = float(self.system_vars["temp"].get())
                self.system_vars["temp"].set(f"{(t*9/5+32) if current == 'US' else (t-32)*5/9:.10g}")
            except ValueError:
                pass
            for segment in self.system_segments:
                for key in ("length", "od"):
                    try:
                        value = float(segment[key].get()) / self._system_factor(key, previous == "US")
                        segment[key].set(f"{value * self._system_factor(key, current == 'US'):.10g}")
                    except ValueError:
                        pass
            self.system_report = None
        self._system_previous_units = current
        us = current == "US"
        units = {"dz": "ft" if us else "m", "dp": "psi" if us else "kPa",
                 "temp": "F" if us else "C",
                 "qmax": "US gpm" if us else "m3/h"}
        for key, label in self.system_unit_labels.items():
            label.configure(text=units.get(key, ""))
        self.system_unit_note.configure(text="Pipe length: ft | diameter: in" if us else "Pipe length: m | diameter: mm")

    def _toggle_system_fluid(self):
        self.system_widgets["ec"].configure(state="normal" if self.system_fluid.get() == "seawater" else "disabled")
        self.system_report = None

    def add_system_segment(self):
        index = len(self.system_segments)
        row = index + 1
        data = {"material": tk.StringVar(value="HDPE / PE"),
                "length": tk.StringVar(value=""),
                "od": tk.StringVar(value=""),
                "sdr": tk.StringVar(value="11"),
                "roughness": tk.StringVar(value="0.0015"),
                "fittings": [tk.StringVar(value="0") for _ in FITTING_CATALOG],
                "transition": tk.StringVar(value="Not installed"),
                "transition_k": tk.StringVar(value="0")}
        widgets = []
        ttk.Label(self.system_segments_frame, text=str(row)).grid(row=row, column=0)
        material = ttk.Combobox(self.system_segments_frame, textvariable=data["material"],
                                values=PIPE_TYPES, state="readonly", width=11)
        material.grid(row=row, column=1, padx=3)
        widgets.append(material)
        for col, key, width in ((2, "length", 9), (3, "od", 10)):
            entry = ttk.Entry(self.system_segments_frame, textvariable=data[key], width=width)
            entry.grid(row=row, column=col, padx=3)
            widgets.append(entry)
        sdr = ttk.Combobox(self.system_segments_frame, textvariable=data["sdr"],
                           values=SDR_OPTIONS, width=8)
        sdr.grid(row=row, column=4, padx=3)
        widgets.append(sdr)
        roughness = ttk.Entry(self.system_segments_frame, textvariable=data["roughness"],
                              state="readonly", width=11)
        roughness.grid(row=row, column=5, padx=3)
        widgets.append(roughness)
        klabel = ttk.Label(self.system_segments_frame, text="0")
        klabel.grid(row=row, column=6, padx=3)
        widgets.append(klabel)
        transition = ttk.Combobox(self.system_segments_frame, textvariable=data["transition"],
                                  values=("Not installed", "Sudden", "Gradual (manual K)"),
                                  state="readonly", width=20)
        transition.grid(row=row, column=7, padx=3)
        transition.configure(state="disabled" if index == 0 else "readonly")
        transition.bind("<<ComboboxSelected>>", lambda event, d=data: self._transition_changed(d))
        widgets.append(transition)
        data["widgets"] = widgets
        data["klabel"] = klabel
        data["row_label"] = self.system_segments_frame.grid_slaves(row=row, column=0)[0]
        data["material"].trace_add("write", lambda *_ , d=data: self._segment_material_changed(d))
        self.system_segments.append(data)
        self.system_segment_selector.configure(values=[str(i+1) for i in range(len(self.system_segments))])
        self.system_segment_selector.set(str(len(self.system_segments)))
        self._update_system_fitting_summary()
        self.system_report = None

    def remove_system_segment(self):
        """Remove the selected segment and rebuild segment rows."""
        index = self._selected_system_segment()
        if index is None:
            return
        if len(self.system_segments) == 1:
            messagebox.showwarning("System Curve", "At least one segment is required.")
            return
        removed = self.system_segments.pop(index)
        for widget in removed["widgets"] + [removed["row_label"]]:
            widget.destroy()
        for row, segment in enumerate(self.system_segments, start=1):
            segment["row_label"].configure(text=str(row))
            segment["row_label"].grid(row=row, column=0)
            for col, widget in enumerate(segment["widgets"], start=1):
                widget.grid(row=row, column=col)
            segment["widgets"][-1].configure(state="disabled" if row == 1 else "readonly")
        self.system_segment_selector.configure(
            values=[str(i + 1) for i in range(len(self.system_segments))])
        self.system_segment_selector.set(str(min(index, len(self.system_segments)-1) + 1))
        self._update_system_fitting_summary()
        self.system_report = None

    def _transition_changed(self, data):
        """One connection selector per boundary; prompt for gradual K only when needed."""
        if data["transition"].get() == "Gradual (manual K)":
            value = simpledialog.askfloat("Gradual transition",
                "Enter transition loss coefficient K (referenced to downstream velocity):",
                parent=self, initialvalue=float(data["transition_k"].get()), minvalue=0.0)
            if value is None:
                data["transition"].set("Not installed")
            else:
                data["transition_k"].set(str(value))
        self.system_report = None

    def _segment_material_changed(self, data):
        material = data["material"].get()
        data["roughness"].set(str(SYSTEM_ROUGHNESS_MM.get(material, 0.05)))
        data["widgets"][3].configure(state="normal" if material == "HDPE / PE" else "disabled")
        self.system_report = None

    def _selected_system_segment(self):
        try:
            index = int(self.system_segment_selector.get()) - 1
            if 0 <= index < len(self.system_segments):
                return index
        except ValueError:
            pass
        return None

    def _update_system_fitting_summary(self):
        index = self._selected_system_segment()
        if index is None:
            return
        data = self.system_segments[index]
        details = []
        ktotal = 0.0
        for j, var in enumerate(data["fittings"]):
            try:
                count = int(var.get())
            except ValueError:
                count = 0
            if count:
                name, coefficient = FITTING_CATALOG[j]
                details.append(f"{name} x{count}")
                ktotal += count * coefficient
        data["klabel"].configure(text=f"{ktotal:.3g}")
        self.system_fitting_summary.configure(
            text=f"Segment {index+1}: " + (", ".join(details) if details else "No fittings selected.")
                 + f" | Total K = {ktotal:.3g}")

    def _add_system_fitting(self):
        index = self._selected_system_segment()
        if index is None:
            return
        try:
            quantity = int(self.system_fitting_quantity.get())
            if not 1 <= quantity <= 999:
                raise ValueError
        except ValueError:
            messagebox.showerror("Fittings", "Enter a whole-number quantity from 1 to 999.")
            return
        name = self.system_fitting_picker.get()
        item = next((j for j, (label, _) in enumerate(FITTING_CATALOG) if label == name), None)
        if item is None:
            return
        self.system_segments[index]["fittings"][item].set(str(quantity))
        self._update_system_fitting_summary()
        self.system_report = None

    def _remove_system_fitting(self):
        index = self._selected_system_segment()
        if index is None:
            return
        name = self.system_fitting_picker.get()
        item = next((j for j, (label, _) in enumerate(FITTING_CATALOG) if label == name), None)
        if item is not None:
            self.system_segments[index]["fittings"][item].set("0")
            self._update_system_fitting_summary()
            self.system_report = None

    def _select_system_segment(self, event=None):
        self._update_system_fitting_summary()
        self.system_report = None

    def calculate_pump_selection(self):
        """Size a single pump using the latest calculated system duty point."""
        if self.pump_selection_duty is None:
            messagebox.showinfo("Pump Selection", "Calculate System H-Q Curve first.")
            return
        try:
            def efficiency(var, name):
                value = float(var.get().strip().replace(",", "."))
                if not math.isfinite(value) or not 0 < value <= 100:
                    raise ValueError(f"{name} must be greater than 0 and at most 100%.")
                return value / 100.0
            pump_eta = efficiency(self.selection_pump_eta, "Pump efficiency")
            motor_eta = efficiency(self.selection_motor_eta, "Motor efficiency")
            pump_points = []
            for q_var, h_var in self.selection_point_rows:
                q_text, h_text = q_var.get().strip(), h_var.get().strip()
                if not q_text and not h_text:
                    continue
                if not q_text or not h_text:
                    raise ValueError("Enter both Q and H for each pump point.")
                point = (float(q_text.replace(",", ".")), float(h_text.replace(",", ".")))
                if not all(math.isfinite(v) and v >= 0 for v in point):
                    raise ValueError("Q and H must be finite and nonnegative.")
                pump_points.append(point)
            if pump_points:
                rpm = float(self.selection_rpm.get().strip().replace(",", "."))
                if not math.isfinite(rpm) or rpm <= 0:
                    raise ValueError("RPM must be positive.")
                pump_points.sort()
                if len(pump_points) < 2 or any(b[0] <= a[0] for a, b in zip(pump_points, pump_points[1:])):
                    raise ValueError("Enter two or more distinct flow points.")
        except ValueError as exc:
            messagebox.showerror("Pump Selection", str(exc))
            return
        q, h, ph = self.pump_selection_duty
        shaft = ph / pump_eta
        electric = shaft / motor_eta
        self.selection_result_label.configure(
            text=f"Design-flow electrical input power: {electric:.2f} kW"
                 + ("\nOperating point: unavailable (enter pump Q-H points)." if not pump_points else ""))
        if self.pump_selection_curve is not None:
            flows, powers = self.pump_selection_curve
            heads = self.pump_selection_heads
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            fig = Figure(figsize=(7, 3.4), dpi=100)
            ax = fig.add_subplot(111)
            ax.set_xlabel("Flow rate (m3/h)")
            ax.set_ylabel("Pump / System Head (m)")
            ax.plot(flows, heads, color="tab:green", linewidth=2, label="System Q-H")
            ax2 = ax.twinx()
            ax2.plot(flows, powers, color="tab:blue", linewidth=2, label="Hydraulic power")
            ax2.plot(flows, [p / (pump_eta * motor_eta) for p in powers],
                     color="tab:red", linewidth=2, label="Electrical input power")
            ax2.set_ylabel("Hydraulic / Electrical Power (kW)")
            max_head = max(heads)
            if pump_points:
                max_head = max(max_head, *(h for _, h in pump_points))
            ax.set_ylim(bottom=0, top=max_head * 1.1 if max_head > 0 else 1)
            if pump_points:
                pq, phead = zip(*pump_points)
                ax.plot(pq, phead, color="tab:orange", marker="o",
                        linewidth=2, label="Pump Q-H")
                def interp(points, x):
                    for (x0, y0), (x1, y1) in zip(points, points[1:]):
                        if x0 <= x <= x1:
                            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
                    return None
                system_points = list(zip(flows, heads))
                low, high = max(flows[0], pq[0]), min(flows[-1], pq[-1])
                crossings = []
                if low <= high:
                    nodes = sorted(set([low, high] +
                        [x for x in flows if low < x < high] +
                        [x for x in pq if low < x < high]))
                    for left, right in zip(nodes, nodes[1:]):
                        dl = interp(pump_points, left) - interp(system_points, left)
                        dr = interp(pump_points, right) - interp(system_points, right)
                        if dl == 0:
                            crossings.append(left)
                        if dl * dr < 0 or (dr == 0 and dl != 0):
                            crossings.append(left + (right-left) * (-dl) / (dr-dl))
                if crossings:
                    crossings = sorted(set(round(x, 10) for x in crossings))
                    op_lines = []
                    for i, op_q in enumerate(crossings, 1):
                        op_h = interp(system_points, op_q)
                        op_ph = interp(list(zip(flows, powers)), op_q)
                        op_electric = op_ph / (pump_eta * motor_eta)
                        ax.scatter([op_q], [op_h], color="black", zorder=6,
                                   label="Operating point" if i == 1 else None)
                        op_lines.append(
                            f"Operating point {i}: Q={op_q:.2f} m3/h | H={op_h:.2f} m | "
                            f"Hydraulic power={op_ph:.2f} kW | "
                            f"Electrical input power={op_electric:.2f} kW")
                    self.selection_result_label.configure(text="\n".join(op_lines))
                else:
                    self.selection_result_label.configure(
                        text="No operating point within the entered pump/system curve ranges.\n"
                             f"Design-flow electrical input power: {electric:.2f} kW")
            ax.grid(True, alpha=0.3)
            l1, n1 = ax.get_legend_handles_labels()
            l2, n2 = ax2.get_legend_handles_labels()
            ax.legend(l1+l2, n1+n2, loc="best", fontsize=8)
            fig.tight_layout()
            if self.selection_canvas is not None:
                self.selection_canvas.get_tk_widget().destroy()
            self.selection_canvas = FigureCanvasTkAgg(fig, master=self.selection_plot_frame)
            self.selection_canvas.draw()
            self.selection_canvas.get_tk_widget().pack(fill="both", expand=True)


    def calculate_system_curve(self):
        try:
            us = self.system_units.get() == "US"
            def number(var, label):
                raw = var.get().strip().replace("٫", ".").replace("−", "-").replace("،", ".")
                raw = raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
                if not raw:
                    raise ValueError(f"{label} is empty. Please enter a number.")
                try:
                    value = float(raw)
                except ValueError:
                    raise ValueError(f"{label} must be numeric (received: {var.get()!r}).") from None
                if not math.isfinite(value):
                    raise ValueError(f"{label} must be finite.")
                return value
            dz = number(self.system_vars["dz"], "Elevation") * (0.3048 if us else 1)
            dp = number(self.system_vars["dp"], "Pressure") * (6.894757293168 if us else 1)
            t = number(self.system_vars["temp"], "Temperature")
            temp = (t - 32)*5/9 if us else t
            qmax = number(self.system_vars["qmax"], "Maximum flow") * (0.22712470704 if us else 1)
            n = 50  # Fixed plotting resolution
            if qmax <= 0:
                raise ValueError("Maximum flow must be positive.")
            fluid = self.system_fluid.get()
            ec = number(self.system_vars["ec"], "EC") if fluid == "seawater" else None
            props = calculate_water_properties(temperature_C=temp, water_type=fluid,
                EC_value=ec, EC_unit="mS/cm" if ec is not None else None)
            rho, nu = props["density_kg_m3"], props["kinematic_viscosity_m2_s"]
            if not rho or not nu or rho <= 0 or nu <= 0:
                raise ValueError("Fluid property calculation returned invalid density or viscosity.")
            segments = []
            for index, data in enumerate(self.system_segments, 1):
                material = data["material"].get()
                length = number(data["length"], f"Segment {index} length") * (0.3048 if us else 1)
                od = number(data["od"], f"Segment {index} diameter") * (25.4 if us else 1)
                sdr = number(data["sdr"], f"Segment {index} SDR") if material == "HDPE / PE" else None
                if sdr is not None and sdr <= 2:
                    raise ValueError(f"Segment {index} SDR must be greater than 2.")
                diameter = od * (1 - 2/sdr) if sdr is not None else od
                roughness = number(data["roughness"], f"Segment {index} roughness")
                if length < 0 or diameter <= 0 or roughness < 0:
                    raise ValueError(f"Invalid geometry for segment {index}.")
                fittings = []
                for j, var in enumerate(data["fittings"]):
                    count = number(var, f"Segment {index} fitting {j+1}")
                    if count < 0 or int(count) != count:
                        raise ValueError(f"Segment {index} fitting counts must be nonnegative integers.")
                    if count:
                        name, kref = FITTING_CATALOG[j]
                        fittings.append((name, int(count), kref))
                total_k = sum(count*kref for _,count,kref in fittings)
                transition = data["transition"].get()
                transition_k = (number(data["transition_k"], f"Segment {index} transition K")
                                if index > 1 and transition == "Gradual (manual K)" else 0.0)
                if transition_k < 0:
                    raise ValueError(f"Segment {index} transition K must be nonnegative.")
                segments.append({"index": index, "material": material, "length": length,
                                 "od": od, "sdr": sdr, "diameter": diameter/1000,
                                 "roughness": roughness, "fittings": fittings, "k": total_k,
                                 "transition": transition, "transition_k": transition_k})
        except (ValueError, TypeError, ArithmeticError, OverflowError) as exc:
            messagebox.showerror("System Curve", f"Invalid input: {exc}")
            return
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError:
            messagebox.showerror("Missing dependency", "Install matplotlib: python -m pip install matplotlib")
            return
        transition_losses = []
        for previous, current in zip(segments, segments[1:]):
            d1, d2 = previous["diameter"], current["diameter"]
            if math.isclose(d1, d2, rel_tol=1e-6):
                transition_losses.append(("Same diameter", 0.0, 0.0))
                continue
            choice = current["transition"]
            if choice == "Not installed":
                if not messagebox.askyesno("Diameter change",
                    f"Segments {previous['index']} and {current['index']} have different IDs "
                    f"({d1*1000:.1f} -> {d2*1000:.1f} mm).\n"
                    "No transition fitting is selected. Continue without its local loss?"):
                    return
                transition_losses.append(("Not modeled", 0.0, 0.0))
            elif choice == "Sudden":
                if d2 > d1:  # Borda-Carnot: (V1-V2)^2/(2g), referenced to V1
                    transition_losses.append(("Sudden expansion", (1-(d1/d2)**2)**2, 1.0))
                else:  # Approximate sharp-edged contraction, referenced to V2
                    transition_losses.append(("Sudden contraction", 0.42*(1-(d2/d1)**2), 2.0))
            else:
                transition_losses.append(("Gradual transition (user K)", current["transition_k"], 2.0))
        static_head, flows, heads, powers_kw, segment_results = compute_system_curve(
            segments, transition_losses, dz, dp, rho, nu, qmax, n)
        if self.system_canvas is not None:
            self.system_canvas.get_tk_widget().destroy()
        fig = build_system_figure(flows, heads, powers_kw, us=us)
        self.system_canvas = FigureCanvasTkAgg(fig, master=self.system_plot_frame)
        self.system_canvas.draw()
        self.system_canvas.get_tk_widget().pack(fill="both", expand=True)
        report = ["SYSTEM CURVE | MULTI-SEGMENT ENGINEERING REPORT",
                  f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
                  f"Units: {self.system_units.get()} (internal calculations in SI)",
                  f"Fluid: {fluid} | Temperature: {temp:.6g} C | In-situ EC: {ec} mS/cm",
                  f"Fluid model: {props.get('method')}",
                  f"Density: {rho:.8g} kg/m3 | Kinematic viscosity: {nu:.8g} m2/s",
                  f"Dynamic viscosity: {props.get('dynamic_viscosity_Pa_s')} Pa.s",
                  f"Elevation: {dz:.7g} m | Pressure difference: {dp:.7g} kPa",
                  f"Static head: {static_head:.7g} m",
                  f"Maximum flow: {qmax:.7g} m3/h | Plot points: {int(n)}",
                  f"At maximum flow: H={heads[-1]:.7g} m | Hydraulic power={powers_kw[-1]:.7g} kW",
                  "Fitting K values from pipe-pressure-loss-calculator/databases/fittings.json (indicative)."]
        for seg in segments:
            report += [f"", f"SEGMENT {seg['index']}",
                       f"Material: {seg['material']} | Length: {seg['length']:.7g} m",
                       f"OD / nominal bore: {seg['od']:.7g} mm | SDR: {seg['sdr']}",
                       f"Calculated internal diameter: {seg['diameter']*1000:.7g} mm",
                       f"Roughness: {seg['roughness']:.7g} mm (indicative reference)",
                       f"Total K: {seg['k']:.7g}"]
            report += [f"  {name}: count={count}, K/unit={kref:g}, K subtotal={count*kref:g}"
                       for name,count,kref in seg["fittings"]]
            if not seg["fittings"]:
                report.append("  No fittings selected.")
        report += ["", "DIAMETER TRANSITIONS (between adjacent segments)"]
        report += [f"{j+1} -> {j+2}: {kind}; K={k:.7g}; reference={'upstream' if ref == 1.0 else 'downstream' if ref == 2.0 else 'none'}"
                   for j, (kind, k, ref) in enumerate(transition_losses)]
        report += ["", "FLOW TABLE (SI)", "Q [m3/h] | Total head [m] | Hydraulic power [kW] | Segment | Velocity [m/s] | Re | Darcy f | Major [m] | Minor [m]"]
        for q,h,power,per in zip(flows,heads,powers_kw,segment_results):
            for seg, (v,re,f,major,minor) in zip(segments,per):
                report.append(f"{q:.8g} | {h:.8g} | {power:.8g} | {seg['index']} | {v:.8g} | {re:.8g} | {f:.8g} | {major:.8g} | {minor:.8g}")
        report += ["", "Water property warnings:"] + [str(x) for x in props.get("warnings", [])]
        report += ["Water property assumptions:"] + [str(x) for x in props.get("assumptions", [])]
        report += ["Assumptions: series pipe, constant flow through segments, no branches.",
                   "Transition losses included when selected; sudden contraction K is approximate.",
                   "Gradual transition K must be supplied by user; unselected changes omit transition loss.",
                   "For non-PE pipes, diameter input is the INTERNAL bore, not outside diameter.",
                   "Manufacturer fitting K and roughness should replace indicative reference values for final design."]
        self.pump_selection_duty = (qmax, heads[-1], powers_kw[-1])
        self.pump_selection_curve = (list(flows), list(powers_kw))
        self.pump_selection_heads = list(heads)
        self.selection_duty_label.configure(text=(
            f"Imported duty: Q={qmax:.4f} m3/h | H={heads[-1]:.4f} m | "
            f"Hydraulic power={powers_kw[-1]:.4f} kW"))
        self.selection_result_label.configure(text="Duty point updated. Calculate to apply efficiencies.")
        self.system_sensitivity_inputs = (segments, transition_losses, dz, dp, rho, nu, qmax)
        self.system_report = "\n".join(report) + "\n"
        qfactor = 4.402867539 if us else 1.0
        hfactor = 3.280839895 if us else 1.0
        self.system_status.configure(text=f"{len(segments)} segments | Density: {rho:.4f} kg/m3 | "
            f"Results at maximum flow")
        self.system_result_label.configure(
            text=f"Flow: {qmax*qfactor:.4f} {'US gpm' if us else 'm3/h'}  |  "
                 f"System head: {heads[-1]*hfactor:.4f} {'ft' if us else 'm'}  |  "
                 f"Hydraulic power: {powers_kw[-1]:.4f} kW "
                 f"({powers_kw[-1]*1.34102209:.4f} hp)")

    def show_system_sensitivity(self):
        """Display relative ±10% system-head sensitivities at maximum flow."""
        if self.system_sensitivity_inputs is None:
            messagebox.showinfo("Sensitivity", "Calculate System Curve first.")
            return
        try:
            result = analyze_sensitivity(*self.system_sensitivity_inputs)
        except (ValueError, ArithmeticError, OverflowError) as exc:
            messagebox.showerror("Sensitivity", str(exc))
            return
        window = tk.Toplevel(self)
        window.title("System Head Sensitivity | +/-10%")
        window.geometry("790x440")
        body = ttk.Frame(window, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=(
            f"At Q = {result['flow_m3h']:.4f} m3/h | "
            f"Baseline head = {result['baseline_head_m']:.4f} m"),
            font=("TkDefaultFont", 11, "bold")).pack(anchor="w", pady=(0, 10))
        columns = ("parameter", "minus", "plus", "delta", "elasticity")
        table = ttk.Treeview(body, columns=columns, show="headings", height=9)
        headings = ("Parameter", "H at -10% (m)", "H at +10% (m)",
                    "H(+10%) - H(-10%) (m)", "Relative sensitivity")
        widths = (140, 125, 125, 190, 145)
        for column, heading, width in zip(columns, headings, widths):
            table.heading(column, text=heading)
            table.column(column, width=width, anchor="center")
        for row in result["results"]:
            table.insert("", "end", values=(
                row["parameter"], f"{row['head_minus_m']:.4f}",
                f"{row['head_plus_m']:.4f}", f"{row['derivative_m']*0.2:.4f}",
                f"{row['elasticity']:.4f}" if row["elasticity"] is not None else "N/A"))
        table.pack(fill="both", expand=True)
        ttk.Label(body, text=(
            "Ranked by absolute head change. Each parameter is varied globally; "
            "others stay fixed.\n"
            "Diameter sensitivity assumes all segment internal diameters change together. "
            "Fixed K values are approximate."),
            wraplength=740, justify="left").pack(anchor="w", pady=(8, 0))

    def save_system_project(self):
        """Persist editable System Curve inputs, not calculated outputs."""
        project = {
            "format": "pump-energy-solver.system-curve",
            "version": 1,
            "units": self.system_units.get(),
            "fluid": self.system_fluid.get(),
            "boundary": {key: var.get() for key, var in self.system_vars.items()},
            "segments": [
                {**{key: segment[key].get() for key in
                    ("material", "length", "od", "sdr", "transition", "transition_k")},
                 "fittings": [var.get() for var in segment["fittings"]]}
                for segment in self.system_segments
            ],
        }
        path = filedialog.asksaveasfilename(
            title="Save System Curve Project", defaultextension=".json",
            filetypes=[("System Curve project", "*.json")],
            initialfile="system_curve_project.json")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as stream:
                json.dump(project, stream, indent=2, ensure_ascii=False)
            self.system_status.configure(text=f"Project saved: {path}")
        except OSError as exc:
            messagebox.showerror("Save Project", str(exc))

    def load_system_project(self):
        """Validate the whole file before changing the current project."""
        path = filedialog.askopenfilename(
            title="Open System Curve Project",
            filetypes=[("System Curve project", "*.json"), ("JSON files", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as stream:
                project = json.load(stream)
            if not isinstance(project, dict) or project.get("format") != "pump-energy-solver.system-curve" or project.get("version") != 1:
                raise ValueError("Unsupported System Curve project format/version.")
            if project.get("units") not in ("SI", "US") or project.get("fluid") not in ("seawater", "freshwater"):
                raise ValueError("Invalid units or fluid.")
            boundary = project.get("boundary")
            if not isinstance(boundary, dict) or set(boundary) != set(self.system_vars) or not all(isinstance(v, str) for v in boundary.values()):
                raise ValueError("Invalid boundary fields.")
            segments = project.get("segments")
            if not isinstance(segments, list) or not 1 <= len(segments) <= 100:
                raise ValueError("Project must contain 1 to 100 segments.")
            allowed_transitions = ("Not installed", "Sudden", "Gradual (manual K)")
            for i, segment in enumerate(segments):
                if not isinstance(segment, dict):
                    raise ValueError(f"Invalid segment {i+1}.")
                if segment.get("material") not in PIPE_TYPES or segment.get("transition") not in allowed_transitions:
                    raise ValueError(f"Invalid material or transition in segment {i+1}.")
                for key in ("length", "od", "sdr", "transition_k"):
                    if not isinstance(segment.get(key), str):
                        raise ValueError(f"Invalid {key} in segment {i+1}.")
                if not isinstance(segment.get("fittings"), list) or len(segment["fittings"]) != len(FITTING_CATALOG) or not all(isinstance(v, str) for v in segment["fittings"]):
                    raise ValueError(f"Invalid fittings in segment {i+1}.")
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            messagebox.showerror("Open Project", f"Could not load project: {exc}")
            return

        # Rebuild only after successful structural validation. Disable unit
        # conversion during restoration so saved numbers remain unchanged.
        self._system_previous_units = project["units"]
        self.system_units.set(project["units"])
        self.system_fluid.set(project["fluid"])
        for key, value in boundary.items():
            self.system_vars[key].set(value)
        for segment in self.system_segments:
            for widget in segment["widgets"] + [segment["row_label"]]:
                widget.destroy()
        self.system_segments.clear()
        for saved in segments:
            self.add_system_segment()
            current = self.system_segments[-1]
            for key in ("material", "length", "od", "sdr", "transition_k"):
                current[key].set(saved[key])
            current["transition"].set(saved["transition"])
            for var, value in zip(current["fittings"], saved["fittings"]):
                var.set(value)
            self._update_system_fitting_summary()
        self.system_segment_selector.set("1")
        self._update_system_fitting_summary()
        self.system_report = None
        self.system_status.configure(text="Project loaded. Click Calculate System Curve to refresh results.")

    def export_system_txt(self):
        if not self.system_report:
            messagebox.showwarning("System Curve", "Calculate System Curve before exporting.")
            return
        path = filedialog.asksaveasfilename(title="Export System Curve TXT",
            defaultextension=".txt", filetypes=[("Text files", "*.txt")],
            initialfile="system_curve_report.txt")
        if path:
            with open(path, "w", encoding="utf-8") as file:
                file.write(self.system_report)

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

    def calculate_pipe(self, key):
        side = "Inlet" if key == "D1" else "Outlet"
        if self.pipe_types[key].get() != "HDPE / PE":
            raw = self.entries[key].get().strip()
            try:
                diameter = float(raw)
                if not math.isfinite(diameter) or diameter <= 0:
                    raise ValueError()
            except ValueError:
                messagebox.showerror("Pipe geometry", f"{side}: enter a positive inside diameter.")
                return
            self.pipe_result_labels[key].configure(text=f"{side} | Inside diameter: {diameter:.2f} mm")
            return
        try:
            od = float(self.pipe_od[key].get())
            sdr = float(self.pipe_sdr[key].get())
            if not (math.isfinite(od) and math.isfinite(sdr) and od > 0 and sdr > 2):
                raise ValueError()
        except ValueError:
            messagebox.showerror("Pipe geometry", f"{side}: enter positive OD and SDR greater than 2.")
            return
        thickness = od / sdr
        inner = od - 2 * thickness
        grade = self.pipe_grade[key].get()
        pressure_bar = 20 * (PE_MRS_MPA[grade] / 1.25) / (sdr - 1)
        self.pipe_result_labels[key].configure(text=(
            f"Wall: {thickness:.2f} mm | ID: {inner:.2f} mm | "
            f"Reference pressure: {pressure_bar:.2f} bar (20 C, C=1.25)"
        ))

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
