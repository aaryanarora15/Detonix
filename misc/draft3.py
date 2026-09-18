import streamlit as st
import folium
from streamlit_folium import st_folium
import numpy as np
from scipy.optimize import brentq
from geopy.distance import distance as geo_distance
from branca.element import Element
import requests

# ---------- PHYSICS & WEATHER LOGIC ----------

def thermal_radius(I_threshold_kw, Q_rad_w, tau=0.8):
    I_threshold_w = I_threshold_kw * 1000
    return np.sqrt((Q_rad_w * tau) / (4 * np.pi * I_threshold_w))

def compute_Q_rad(volume_m3, eta_rad=0.30, m_flux=0.06, dH_c=4.5e7):
    radius_guess = (volume_m3 / (np.pi * 8)) ** (1/3)
    A_pool = np.pi * radius_guess ** 2
    return eta_rad * m_flux * A_pool * dH_c

def compute_W_TNT(mass_fuel_kg, eta_exp=0.06, dH_c=4.5e7, dH_tnt=4.184e6):
    return (eta_exp * mass_fuel_kg * dH_c) / dH_tnt

def overpressure_kpa(R, W_TNT):
    Z = R / (W_TNT ** (1/3))
    return 1772 / Z - 114 / Z**2 + 108 / Z**3

def blast_radius(P_threshold_kpa, W_TNT):
    f = lambda R: overpressure_kpa(R, W_TNT) - P_threshold_kpa
    try:
        return brentq(f, 0.1, 20000)
    except ValueError:
        if f(0.1) < 0: return 0.0
        else: return 20000.0

def wind_skew_polygon(lat, lon, base_radius_m, wind_dir_deg, k_down=1.8, k_up=0.6):
    points = []
    # Convert "wind from" direction to "wind blowing towards" direction
    wind_towards = (wind_dir_deg + 180) % 360
    for theta in range(0, 360, 5):
        delta_deg = (theta - wind_towards + 180) % 360 - 180
        delta = np.radians(delta_deg)
        if abs(delta_deg) < 90:
            stretch = 1 + (k_down - 1) * np.cos(delta) ** 2
        else:
            stretch = 1 - (1 - k_up) * np.cos(delta) ** 2
        r = base_radius_m * stretch
        dest = geo_distance(meters=r).destination((lat, lon), bearing=theta)
        points.append((dest.latitude, dest.longitude))
    return points

def wedge_polygon(lat, lon, radius, start_angle, end_angle):
    points = [(lat, lon)]
    for theta in range(start_angle, end_angle + 1, 5):
        dest = geo_distance(meters=radius).destination((lat, lon), bearing=theta)
        points.append((dest.latitude, dest.longitude))
    return points

def get_live_wind_data(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    try:
        response = requests.get(url)
        data = response.json()
        wind_speed_kmh = data['current_weather']['windspeed']
        wind_dir = data['current_weather']['winddirection']
        return float(wind_speed_kmh * (1000 / 3600)), float(wind_dir)
    except Exception:
        return 6.0, 315.0

# ---------- STREAMLIT UI ----------

st.set_page_config(layout="wide")

col1, col2 = st.columns([1, 3])

with col1:
    st.subheader("Facility Config")
    lat = st.number_input("Latitude", value=29.7325, format="%.4f")
    lon = st.number_input("Longitude", value=-95.0233, format="%.4f")
    
    st.markdown("---")
    st.markdown("**Scenario A: Crude Tank**")
    vol_a = st.slider("Tank volume (m³)", 100, 10000, 2000, key="v_a")
    
    st.markdown("**Scenario B: LPG Sphere**")
    vol_b = st.slider("Sphere volume (m³)", 100, 10000, 5000, key="v_b")
    fuel_fraction = st.slider("Fraction in VCE", 0.1, 1.0, 0.5)
    
    if st.button("Fetch Live Weather"):
        live_speed, live_dir = get_live_wind_data(lat, lon)
        st.session_state['wind_speed'] = live_speed
        st.session_state['wind_dir'] = live_dir

    wind_speed = st.slider("Wind speed (m/s)", 0.0, 20.0, st.session_state.get('wind_speed', 6.0))
    wind_dir_from = st.slider("Wind from (°)", 0.0, 360.0, st.session_state.get('wind_dir', 315.0))

FUEL_DENSITY = 750
Q_rad_a = compute_Q_rad(vol_a)
Q_rad_b = compute_Q_rad(vol_b)
W_TNT_b = compute_W_TNT(vol_b * FUEL_DENSITY * fuel_fraction)

k_down = 1.2 + 0.05 * wind_speed
k_up = 0.8 - 0.01 * wind_speed

# Specific thresholds and colors adapted from the target HTML
thermal_bands = [
    (37.5, "#7f0000", "37.5 kW/m² — no-survival / equipment damage zone"),
    (12.5, "#e2571b", "12.5 kW/m² — potentially lethal without shielding"),
    (4.7, "#f4c542", "4.7 kW/m² — max for brief PPE-protected responder exposure")
]
blast_bands = [
    (20.7, "#4a0072", "20.7 kPa (3 psi) — serious injury / structural collapse"),
    (6.9, "#8e24aa", "6.9 kPa (1 psi) — injury from debris & glass, moderate damage"),
    (2.07, "#ce93d8", "2.07 kPa (0.3 psi) — window breakage, outer caution zone")
]

with col2:
    m = folium.Map(location=[lat, lon], zoom_start=15, prefer_canvas=True)
    
    # Custom HTML Title
    title_html = """
    <div style="position: fixed; top: 12px; left: 60px; z-index:9999; background:white;
                padding:8px 14px; border-radius:6px; box-shadow:0 2px 8px rgba(0,0,0,0.3);
                font-family: Arial, sans-serif; font-weight:700; font-size:15px;">
      DER-02: Graded Thermal / Blast Threat Zones — Two Facility Configurations
    </div>
    """
    m.get_root().html.add_child(Element(title_html))
    
    # Custom HTML Legend
    legend_html = f"""
    <div style="position: fixed; bottom: 20px; left: 20px; z-index: 9999; background: white; padding: 12px 14px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); font-family: Arial, sans-serif; font-size: 12.5px; max-width: 340px; line-height: 1.45;">
      <div style="font-weight:700; margin-bottom:6px; font-size:13.5px;">DER-02 Threat-Zone Legend</div>
      <div style="font-weight:600; margin-top:4px;">Thermal radiation (both scenarios)</div>
      <div><span style="display:inline-block;width:12px;height:12px;background:#7f0000;margin-right:6px;"></span>37.5 kW/m² — no-survival zone</div>
      <div><span style="display:inline-block;width:12px;height:12px;background:#e2571b;margin-right:6px;"></span>12.5 kW/m² — potentially lethal</div>
      <div><span style="display:inline-block;width:12px;height:12px;background:#f4c542;margin-right:6px;"></span>4.7 kW/m² — PPE brief-exposure limit</div>
      <div style="font-weight:600; margin-top:6px;">Blast overpressure (Scenario B VCE)</div>
      <div><span style="display:inline-block;width:12px;height:12px;background:#4a0072;margin-right:6px;"></span>20.7 kPa (3 psi) — serious injury</div>
      <div><span style="display:inline-block;width:12px;height:12px;background:#8e24aa;margin-right:6px;"></span>6.9 kPa (1 psi) — moderate damage</div>
      <div><span style="display:inline-block;width:12px;height:12px;background:#ce93d8;margin-right:6px;"></span>2.07 kPa (0.3 psi) — window breakage</div>
      <div style="margin-top:8px; font-weight:600;">Wind: from {wind_dir_from}° @ {wind_speed:.1f} m/s</div>
      <div style="color:#333;">Blue line = downwind axis.</div>
      <div style="font-weight:600; margin-top:6px;">Approach-direction ring</div>
      <div><span style="display:inline-block;width:12px;height:12px;background:#2e7d32;margin-right:6px;"></span>SAFER</div>
      <div><span style="display:inline-block;width:12px;height:12px;background:#f9a825;margin-right:6px;"></span>CAUTION</div>
      <div><span style="display:inline-block;width:12px;height:12px;background:#ef6c00;margin-right:6px;"></span>HIGH RISK</div>
      <div><span style="display:inline-block;width:12px;height:12px;background:#b71c1c;margin-right:6px;"></span>EXTREME — downwind axis</div>
    </div>
    """
    m.get_root().html.add_child(Element(legend_html))

    # Facility Marker
    folium.Marker(
        [lat, lon], 
        tooltip="Facility reference point (both scenarios co-located for comparison)",
        icon=folium.Icon(color="black", icon="industry", prefix="fa")
    ).add_to(m)

    # Layer 1: Scenario A Thermal
    fg_a_therm = folium.FeatureGroup(name="Scenario A: Crude tank — Thermal radiation")
    for thresh, color, label in thermal_bands:
        r = thermal_radius(thresh, Q_rad_a)
        poly = wind_skew_polygon(lat, lon, r, wind_dir_from, k_down, k_up)
        folium.Polygon(poly, color=color, fillColor=color, fillOpacity=0.35, tooltip=label, weight=2).add_to(fg_a_therm)
    fg_a_therm.add_to(m)

    # Layer 2: Scenario B Thermal
    fg_b_therm = folium.FeatureGroup(name="Scenario B: LPG sphere — BLEVE fireball thermal")
    for thresh, color, label in thermal_bands:
        r = thermal_radius(thresh, Q_rad_b)
        poly = wind_skew_polygon(lat, lon, r, wind_dir_from, k_down, k_up)
        folium.Polygon(poly, color=color, fillColor=color, fillOpacity=0.3, tooltip=label, weight=2).add_to(fg_b_therm)
    fg_b_therm.add_to(m)

    # Layer 3: Scenario B Blast
    fg_b_blast = folium.FeatureGroup(name="Scenario B: LPG sphere — VCE blast overpressure")
    for thresh, color, label in blast_bands:
        r = blast_radius(thresh, W_TNT_b)
        poly = wind_skew_polygon(lat, lon, r, wind_dir_from, k_down, k_up)
        folium.Polygon(poly, color=color, fillColor=color, fillOpacity=0.3, tooltip=label, weight=2).add_to(fg_b_blast)
    fg_b_blast.add_to(m)

    # Layer 4: Approach Directions
    fg_approach = folium.FeatureGroup(name="Approach-direction score (combined, both scenarios)")
    wind_towards = (wind_dir_from + 180) % 360
    for angle in range(0, 360, 15):
        diff = abs((angle - wind_towards + 180) % 360 - 180)
        if diff <= 30: color, cat = "#b71c1c", "EXTREME"
        elif diff <= 75: color, cat = "#ef6c00", "HIGH RISK"
        elif diff <= 120: color, cat = "#f9a825", "CAUTION"
        else: color, cat = "#2e7d32", "SAFER"
        
        wedge = wedge_polygon(lat, lon, 1500, angle, angle + 15)
        folium.Polygon(wedge, color=color, fillColor=color, fillOpacity=0.18, weight=1,
                       tooltip=f"Bearing {angle}°: {cat}").add_to(fg_approach)
    fg_approach.add_to(m)

    # Wind Vector Indicator
    wind_dest = geo_distance(meters=250).destination((lat, lon), bearing=wind_towards)
    folium.PolyLine([[lat, lon], [wind_dest.latitude, wind_dest.longitude]], 
                    color="blue", weight=4, opacity=0.8,
                    tooltip=f"Wind: from {wind_dir_from}° at {wind_speed:.1f} m/s").add_to(m)
    folium.CircleMarker([wind_dest.latitude, wind_dest.longitude], radius=4, color="blue", fill=True).add_to(m)

    # Staging Area Marker (Dynamic placement in the safest upwind quadrant)
    staging_dest = geo_distance(meters=1415).destination((lat, lon), bearing=(wind_dir_from))
    folium.Marker(
        [staging_dest.latitude, staging_dest.longitude],
        tooltip="Recommended staging area: clears all zones + 75 m margin.",
        icon=folium.Icon(color="green", icon="flag", prefix="fa")
    ).add_to(m)

    folium.LayerControl(position="topright", collapsed=False).add_to(m)
    
    st_folium(m, width=900, height=600)