"""Catalog-driven pipe sizing. Indicative rows require source verification before procurement."""
import math

CATALOGS = {
 "HDPE / PE": {"ISO 4427": {"mode":"sdr","sizes":[63,75,90,110,125,140,160,180,200,225,250,280,315,355,400,450,500,560,630,710,800,900,1000],"series":["9","11","13.6","17","21","26"]}},
 "Carbon Steel": {"ASME B36.10M": {"mode":"schedule","sizes":[("2",60.3),("3",88.9),("4",114.3),("6",168.3),("8",219.1),("10",273.1),("12",323.9),("14",355.6),("16",406.4),("18",457.2),("20",508.0),("24",609.6)],"series":["40","80"]}},
 "Stainless Steel": {"ASME B36.19M": {"mode":"schedule","sizes":[("2",60.3),("3",88.9),("4",114.3),("6",168.3),("8",219.1),("10",273.1),("12",323.9),("16",406.4)],"series":["10S","40S"]}},
 "PVC-U": {"ISO 1452": {"mode":"sdr","sizes":[63,75,90,110,125,140,160,180,200,225,250,280,315,355,400,450,500,630],"series":["13.6","17","21","26","33","41"]}},
 "CPVC": {"ASTM F442": {"mode":"sdr","sizes":[60.3,88.9,114.3,168.3,219.1,273.1],"series":["11","13.5","17","21"]}},
 "GRP / FRP": {"AWWA C950": {"mode":"manufacturer","sizes":[],"series":[]}},
 "Ductile Iron": {"EN 545": {"mode":"manufacturer","sizes":[],"series":[]}},
}
# Representative dimensional examples only; steel schedules must be verified against the licensed ASME tables.
STEEL_WALL = {"40":{60.3:3.91,88.9:5.49,114.3:6.02,168.3:7.11,219.1:8.18,273.1:9.27,323.9:10.31,355.6:11.13,406.4:12.7,457.2:14.27,508.0:15.09,609.6:17.48},
"80":{60.3:5.54,88.9:7.62,114.3:8.56,168.3:10.97,219.1:12.7,273.1:15.09,323.9:17.48,355.6:19.05,406.4:21.44,457.2:23.83,508.0:26.19,609.6:30.96},
"10S":{60.3:2.77,88.9:3.05,114.3:3.05,168.3:3.4,219.1:3.76,273.1:4.19,323.9:4.57,406.4:4.78},
"40S":{60.3:3.91,88.9:5.49,114.3:6.02,168.3:7.11,219.1:8.18,273.1:9.27,323.9:9.53,406.4:9.53}}

def candidates(material, standard, series):
    spec = CATALOGS[material][standard]
    result=[]
    for item in spec["sizes"]:
        designation,od = (item if isinstance(item,tuple) else (str(item),float(item)))
        if spec["mode"]=="sdr":
            wall=od/float(series)
        elif spec["mode"]=="schedule":
            wall=STEEL_WALL.get(series,{}).get(od)
        else:
            continue
        if wall is None or od<=2*wall: continue
        result.append({"designation":designation,"od_mm":od,"wall_mm":wall,"id_mm":od-2*wall,"series":series})
    return result

def size_pipes(material,standard,series,flow_m3h,target_velocity,pipe_length_m,roughness_mm,minor_k,nu_m2s=1e-6):
    vals=(flow_m3h,target_velocity,pipe_length_m,roughness_mm,minor_k,nu_m2s)
    if any(not math.isfinite(x) for x in vals) or flow_m3h<=0 or target_velocity<=0 or pipe_length_m<0 or roughness_mm<0 or minor_k<0 or nu_m2s<=0:
        raise ValueError("Check flow, velocity, length, roughness, fittings K and viscosity.")
    q=flow_m3h/3600
    required=math.sqrt(4*q/(math.pi*target_velocity))*1000
    results=[]
    for row in candidates(material,standard,series):
        d=row["id_mm"]/1000
        v=4*q/(math.pi*d*d)
        re=v*d/nu_m2s
        f=64/re if re<2300 else (-1.8*math.log10(((roughness_mm/1000)/d/3.7)**1.11+6.9/re))**-2
        loss=(f*pipe_length_m/d+minor_k)*v*v/(2*9.80665)
        results.append({**row,"velocity_m_s":v,"reynolds":re,"friction_factor":f,"head_loss_m":loss,"meets_velocity":v<=target_velocity})
    return required,sorted(results,key=lambda x:x["id_mm"])
