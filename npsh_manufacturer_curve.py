"""NPSH analysis: manual manufacturer Q-NPSHr points and hydraulic NPSHa curve."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import math
from gui import PumpEnergyApp
from water_properties import calculate_water_properties
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

G = 9.80665

def npsha(q, d, length, k, roughness, dz, pressure_bar_abs, rho, nu, vapor_pa):
    diameter = d / 1000
    velocity = q / 3600 / (math.pi * diameter**2 / 4)
    re = velocity * diameter / nu
    if re == 0: f = 0
    elif re < 2300: f = 64 / re
    else:
        a = (2.457 * math.log(1 / ((7 / re)**0.9 + 0.27 * roughness / 1000 / diameter)))**16
        b = (37530 / re)**16
        f = 8 * ((8 / re)**12 + (a+b)**(-1.5))**(1/12)
    loss = (f * length / diameter + k) * velocity**2 / (2 * G)
    return (pressure_bar_abs * 1e5 - vapor_pa) / (rho * G) + dz - loss

def install(app):
    tab = ttk.Frame(app.tabs, padding=10)
    app.tabs.add(tab, text="NPSH Analysis")
    left = ttk.Frame(tab)
    left.pack(side="left", fill="y", padx=(0,10))
    right = ttk.Frame(tab)
    right.pack(side="left", fill="both", expand=True)
    defaults = [
        ("water_type","Water","seawater"),
        ("temperature","Temperature [C]","30"),
        ("ec","In-situ EC [mS/cm]","58"),
        ("d","Suction ID [mm]","200"),
        ("length","Suction length [m]","10"),
        ("k","Total K","1"),
        ("roughness","Roughness [mm]","0.0015"),
        ("dz","Water surface - pump inlet [m]","7"),
        ("p","Surface pressure [bar ABS]","1.01325"),
        ("qmax","Maximum Q [m3/h]","500"),
    ]
    fields={}
    box=ttk.LabelFrame(left,text="Suction conditions",padding=8)
    box.pack(fill="x")
    for i,(key,label,default) in enumerate(defaults):
        ttk.Label(box,text=label).grid(row=i,column=0,sticky="w",pady=3)
        v=tk.StringVar(value=default);fields[key]=v
        if key=="water_type":
            w=ttk.Combobox(box,textvariable=v,values=["seawater","freshwater"],state="readonly",width=14)
        else:w=ttk.Entry(box,textvariable=v,width=16)
        w.grid(row=i,column=1,padx=5,pady=3)
    curve_box=ttk.LabelFrame(left,text="Manufacturer NPSHr curve (Q, NPSHr)",padding=8)
    curve_box.pack(fill="x",pady=8)
    ttk.Label(curve_box,text="Flow [m3/h]").grid(row=0,column=0)
    ttk.Label(curve_box,text="NPSHr [m]").grid(row=0,column=1)
    rows=[]
    def add_point(q="",h=""):
        i=len(rows)+1
        qv=tk.StringVar(value=str(q));hv=tk.StringVar(value=str(h))
        qw=ttk.Entry(curve_box,textvariable=qv,width=12)
        hw=ttk.Entry(curve_box,textvariable=hv,width=12)
        qw.grid(row=i,column=0,pady=2,padx=2)
        hw.grid(row=i,column=1,pady=2,padx=2)
        rows.append((qv,hv,qw,hw))
    def remove_point():
        if len(rows)<=2:return
        _,_,qw,hw=rows.pop()
        qw.destroy();hw.destroy()
    def points():
        pts=[]
        for q,h,_,_ in rows:
            if not q.get().strip() and not h.get().strip():continue
            x=float(q.get());y=float(h.get())
            if not math.isfinite(x) or not math.isfinite(y) or x<0 or y<0:
                raise ValueError("Manufacturer curve points must be finite and nonnegative.")
            pts.append((x,y))
        pts.sort()
        if len(pts)<2 or len({q for q,_ in pts})!=len(pts):
            raise ValueError("Enter at least two distinct flow points.")
        return pts
    for _ in range(3):add_point()
    actions=ttk.Frame(left);actions.pack(fill="x")
    ttk.Button(actions,text="Add Point",command=add_point).pack(side="left")
    ttk.Button(actions,text="Remove",command=remove_point).pack(side="left")
    def save():
        try:
            p=points()
            path=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("JSON","*.json")])
            if path:
                with open(path,"w",encoding="utf-8") as f:json.dump({"manufacturer_npshr":p},f,indent=2)
        except Exception as e:messagebox.showerror("Curve",str(e))
    def load():
        path=filedialog.askopenfilename(filetypes=[("JSON","*.json")])
        if not path:return
        try:
            with open(path,encoding="utf-8") as f:pts=json.load(f)["manufacturer_npshr"]
            for _,_,qw,hw in rows:qw.destroy();hw.destroy()
            rows.clear()
            for q,h in pts:add_point(q,h)
        except Exception as e:messagebox.showerror("Curve",str(e))
    ttk.Button(actions,text="Save",command=save).pack(side="left")
    ttk.Button(actions,text="Load",command=load).pack(side="left")
    chart_frame=ttk.Frame(right);chart_frame.pack(fill="both",expand=True)
    result=ttk.Label(right,text="Enter manufacturer points, then plot.",wraplength=700)
    result.pack(fill="x")
    def plot():
        try:
            p=points()
            kind=fields["water_type"].get()
            temperature=float(fields["temperature"].get())
            pressure=float(fields["p"].get())
            if pressure<=0:raise ValueError("Absolute pressure must be positive.")
            kw=dict(water_type=kind,temperature_C=temperature,pressure_MPa_abs=pressure*0.1)
            if kind=="seawater":
                kw.update(EC_value=float(fields["ec"].get()),EC_unit="mS/cm",conductivity_temperature_mode="in_situ")
            fluid=calculate_water_properties(**kw)
            rho=fluid["density_kg_m3"];nu=fluid["kinematic_viscosity_m2_s"]
            vapor=fluid["vapor_pressure_MPa"]*1e6
            d=float(fields["d"].get());length=float(fields["length"].get())
            k=float(fields["k"].get());roughness=float(fields["roughness"].get())
            dz=float(fields["dz"].get());qmax=float(fields["qmax"].get())
            if d<=0 or qmax<=0 or min(length,k,roughness)<0:
                raise ValueError("Diameter and Qmax must be positive; losses nonnegative.")
            import numpy as np
            q=np.linspace(0,qmax,201)
            available=np.array([npsha(x,d,length,k,roughness,dz,pressure,rho,nu,vapor) for x in q])
            qpts=np.array([x for x,_ in p]);hpts=np.array([y for _,y in p])
            # No extrapolation beyond manufacturer-supplied Q range.
            valid=(q>=qpts[0])&(q<=qpts[-1])
            required=np.interp(q[valid],qpts,hpts)
            margin=available[valid]-required
            for child in chart_frame.winfo_children():child.destroy()
            fig=Figure(figsize=(7.2,5),dpi=100)
            ax=fig.add_subplot(111)
            ax.plot(q,available,label="NPSHa (system)")
            ax.plot(q[valid],required,label="NPSHr (manufacturer, linear interpolation)")
            ax.scatter(qpts,hpts,label="Manufacturer points",zorder=3)
            ax.fill_between(q[valid],available[valid],required,where=margin<0,alpha=.18,label="NPSHa < NPSHr")
            ax.set(xlabel="Flow [m3/h]",ylabel="NPSH [m]")
            ax.grid(True);ax.legend()
            canvas=FigureCanvasTkAgg(fig,master=chart_frame)
            canvas.draw();canvas.get_tk_widget().pack(fill="both",expand=True)
            result.configure(text=f"Comparison only within manufacturer range: {qpts[0]:g} to {qpts[-1]:g} m3/h. "
                                  "Positive margin does not itself establish the manufacturer's required safety margin.")
        except Exception as e:messagebox.showerror("NPSH plot",str(e))
    ttk.Button(left,text="Plot NPSHa and manufacturer NPSHr",command=plot).pack(fill="x",pady=8)

if __name__=="__main__":
    app=PumpEnergyApp()
    install(app)
    app.mainloop()
