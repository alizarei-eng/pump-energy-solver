"""Launch the existing Pump Energy Solver with two integrated NPSH tabs."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
from gui import PumpEnergyApp
from hydraulics.npsh import calculate_npsh

FIELDS = [
 ("water_type","Water type","seawater"),
 ("temperature_C","Temperature [C]","30"),
 ("ec_ms_cm","In-situ EC [mS/cm]","58"),
 ("flow_m3h","Flow [m3/h]","150"),
 ("inside_diameter_mm","Suction internal diameter [mm]","200"),
 ("length_m","Suction length [m]","10"),
 ("roughness_mm","Roughness [mm]","0.0015"),
 ("fittings_k","Total fittings K","1"),
 ("static_height_m","Surface elevation - pump inlet [m]","7"),
 ("surface_pressure_bar_abs","Surface pressure [bar ABS]","1.01325"),
 ("npshr_m","Pump NPSHr [m]","4"),
 ("known_loss_m","Known suction loss [m] (optional)",""),
]

def add_npsh_tabs(app):
    calc = ttk.Frame(app.tabs, padding=12)
    analysis = ttk.Frame(app.tabs, padding=12)
    app.tabs.add(calc, text="NPSH Calculator")
    app.tabs.add(analysis, text="NPSH Analysis")
    vars = {}
    grid = ttk.Frame(calc)
    grid.pack(anchor="nw", fill="x")
    for i,(key,label,default) in enumerate(FIELDS):
        ttk.Label(grid,text=label).grid(row=i//2,column=(i%2)*2,sticky="w",padx=5,pady=5)
        var=tk.StringVar(value=default); vars[key]=var
        if key=="water_type":
            ttk.Combobox(grid,textvariable=var,values=["freshwater","seawater"],
                         state="readonly",width=17).grid(row=i//2,column=(i%2)*2+1,padx=5)
        else:
            ttk.Entry(grid,textvariable=var,width=18).grid(row=i//2,column=(i%2)*2+1,padx=5)
    report=tk.Text(calc,height=13,wrap="word")
    report.pack(fill="both",expand=True,pady=8)
    def inputs():
        d={k:(v.get() if k=="water_type" else (None if k=="known_loss_m" and not v.get().strip() else float(v.get())))
           for k,v in vars.items()}
        return d
    def calc_result():
        try:
            r=calculate_npsh(**inputs())
            report.delete("1.0","end")
            report.insert("end","NPSHa = (P_surface,abs - Pv)/(rho*g) + (z_surface - z_pump) - h_loss\n")
            report.insert("end","h_loss = (f*L/D + sum K)*V^2/(2*g)\n\n")
            for k,v in r.items():
                report.insert("end",f"{k}: {v}\n")
            return r
        except Exception as exc:
            messagebox.showerror("NPSH calculation",str(exc))
    bar=ttk.Frame(calc);bar.pack(fill="x")
    ttk.Button(bar,text="Calculate NPSH",command=calc_result).pack(side="left",padx=5)
    def export():
        r=calc_result()
        if r is None:return
        path=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("JSON","*.json")])
        if path:
            with open(path,"w",encoding="utf-8") as f:
                json.dump({"inputs":inputs(),"results":r},f,indent=2,ensure_ascii=False)
    ttk.Button(bar,text="Export JSON",command=export).pack(side="left",padx=5)
    ttk.Label(analysis,text="NPSHa vs flow | NPSHr is constant unless a manufacturer curve is provided.").pack(anchor="w")
    row=ttk.Frame(analysis);row.pack(fill="x",pady=8)
    ttk.Label(row,text="Max flow [m3/h]").pack(side="left")
    qmax=tk.StringVar(value="500")
    ttk.Entry(row,textvariable=qmax,width=12).pack(side="left",padx=8)
    chart=ttk.Frame(analysis);chart.pack(fill="both",expand=True)
    def plot():
        try:
            import numpy as np
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            d=inputs(); top=float(qmax.get())
            if top<=0:raise ValueError("Maximum flow must be positive.")
            qs=np.linspace(0,top,81)
            a=[calculate_npsh(**dict(d,flow_m3h=float(q)))["npsha_m"] for q in qs]
            for child in chart.winfo_children():child.destroy()
            fig=Figure(figsize=(8,5),dpi=100)
            ax=fig.add_subplot(111)
            ax.plot(qs,a,label="NPSHa")
            ax.axhline(d["npshr_m"],linestyle="--",label="NPSHr (constant assumption)")
            ax.set(xlabel="Flow [m3/h]",ylabel="NPSH [m]",title="Available NPSH vs flow")
            ax.grid(True);ax.legend()
            canvas=FigureCanvasTkAgg(fig,master=chart);canvas.draw()
            canvas.get_tk_widget().pack(fill="both",expand=True)
        except Exception as exc:messagebox.showerror("NPSH analysis",str(exc))
    ttk.Button(row,text="Plot NPSH",command=plot).pack(side="left")
    return vars

if __name__=="__main__":
    app=PumpEnergyApp()
    add_npsh_tabs(app)
    app.mainloop()
