"""Matplotlib system head and hydraulic power chart (no Tkinter dependency)."""
from matplotlib.figure import Figure


def build_system_figure(flows, heads, powers_kw, us=False):
    fig = Figure(figsize=(5.2, 3.2), dpi=100)
    ax = fig.add_subplot(111)
    qfactor = 4.402867539 if us else 1
    hfactor = 3.280839895 if us else 1
    flow_axis = [q*qfactor for q in flows]
    head_line, = ax.plot(flow_axis, [h*hfactor for h in heads], linewidth=2, label="System head")
    ax.set_xlabel("Flow Q (US gpm)" if us else "Flow Q (m3/h)")
    ax.set_ylabel("Required head H (ft)" if us else "Required head H (m)", color=head_line.get_color())
    power_ax = ax.twinx()
    power_line, = power_ax.plot(flow_axis, powers_kw, color="red", linewidth=2,
                                label="Hydraulic power")
    power_ax.set_ylabel("Hydraulic power (kW)", color="red")
    power_ax.tick_params(axis="y", labelcolor="red")
    ax.legend([head_line, power_line], ["System head", "Hydraulic power"], loc="upper left")
    ax.set_title("System head and hydraulic power vs flow")
    ax.grid(True, alpha=0.35)
    fig.tight_layout()
    return fig
