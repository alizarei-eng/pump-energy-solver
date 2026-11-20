"""Pure SI hydraulic calculations for serial pipeline system curves."""
import math

G = 9.80665


def calculate_system_curve(segments, transition_losses, dz, dp, rho, nu, qmax, n=50):
    """Return head, hydraulic power, and per-segment results across flow points.

    dp is kPa, qmax is m3/h, diameters are metres and roughness is mm.
    """
    if not segments or n < 2 or qmax <= 0 or rho <= 0 or nu <= 0:
        raise ValueError("Invalid system curve inputs.")
    static_head = dz + dp*1000/(rho*G)
    flows = [qmax*i/(int(n)-1) for i in range(int(n))]
    heads = []
    segment_results = []
    for q in flows:
        total_loss = 0.0
        per_segment = []
        for seg in segments:
            d = seg["diameter"]
            v = (q/3600)/(math.pi*d*d/4)
            re = v*d/nu
            if re == 0:
                f = 0.0
            elif re < 2300:
                f = 64/re
            else:
                f = 0.25/math.log10(seg["roughness"]/1000/d/3.7+5.74/re**0.9)**2
            major = f*seg["length"]/d*v*v/(2*G)
            minor = seg["k"]*v*v/(2*G)
            total_loss += major+minor
            per_segment.append((v,re,f,major,minor))
        for j, (kind, k_transition, reference) in enumerate(transition_losses):
            if reference:
                ref_d = segments[j if reference == 1.0 else j+1]["diameter"]
                ref_v = (q/3600)/(math.pi*ref_d**2/4)
                total_loss += k_transition*ref_v**2/(2*G)
        heads.append(static_head+total_loss)
        segment_results.append(per_segment)
    powers_kw = [rho * G * (q / 3600) * h / 1000 for q, h in zip(flows, heads)]
    return static_head, flows, heads, powers_kw, segment_results

