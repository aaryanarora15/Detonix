import streamlit as st
import folium
from folium import Element
from streamlit_folium import st_folium
import numpy as np
from scipy.optimize import brentq
from geopy.distance import distance as geo_distance
import requests

# ---------- PHYSICS & WEATHER LOGIC ----------

def thermal_radius(I_threshold_kw, Q_rad_w, tau=0.8):
    I_threshold_w = I_threshold_kw * 1000
    return np.sqrt((Q_rad_w * tau) / (4 * np.pi * I_threshold_w))

def compute_Q_rad(volume_m3, eta_rad=0.30, m_flux=0.06, dH_c=4.5e7):
    # crude cylindrical tank cross-section from volume (assume aspect ratio)
    radius_guess = (volume_m3 / (np.pi * 8)) ** (1/3)  # rough h≈8r tank
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
        # We also expand the upper search limit from 5,000 to 20,000 meters
        return brentq(f, 0.1, 20000)
    except ValueError:
        # If the explosion is too small to reach the threshold even at 0.1 meters
        if f(0.1) < 0:
            return 0.0
        # If the explosion is massive and exceeds the threshold beyond 20,000 meters
        else:
            return 20000.0

def wind_skew_polygon(lat, lon, base_radius_m, wind_dir_deg, k_down=1.8, k_up=0.6):
    points = []
    for theta in range(0, 360, 10):
        delta_deg = (theta - wind_dir_deg + 180) % 360 - 180  # angle to downwind, -180..180
        delta = np.radians(delta_deg)
        if abs(delta_deg) < 90:
            stretch = 1 + (k_down - 1) * np.cos(delta) ** 2
        else:
            stretch = 1 - (1 - k_up) * np.cos(delta) ** 2
        r = base_radius_m * stretch
        dest = geo_distance(meters=r).destination((lat, lon), bearing=theta)
        points.append((dest.latitude, dest.longitude))
    return points

def get_live_wind_data(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    try:
        response = requests.get(url)
        data = response.json()
        wind_speed_kmh = data['current_weather']['windspeed']
        wind_dir = data['current_weather']['winddirection']
        wind_speed_ms = wind_speed_kmh * (1000 / 3600)
        return float(wind_speed_ms), float(wind_dir)
    except Exception as e:
        st.warning("Could not fetch live weather. Using default values.")
        return 5.0, 90.0

# ---------- STREAMLIT UI ----------

st.set_page_config(layout="wide")
st.title("Threat-Zone Estimation — Fire & Explosion Response")

col1, col2 = st.columns([1, 3])

with col1:
    st.subheader("Facility Config")
    # Coordinates default to Melakottaiyur
    lat = st.number_input("Latitude", value=12.8406, format="%.4f")
    lon = st.number_input("Longitude", value=80.1534, format="%.4f")
    volume = st.slider("Tank volume (m³)", 100, 10000, 2000)
    fuel_fraction = st.slider("Fraction of tank contents in explosion", 0.1, 1.0, 0.5)

    # Live Weather Button Integration
    if st.button("Fetch Live Weather"):
        live_speed, live_dir = get_live_wind_data(lat, lon)
        st.session_state['wind_speed'] = live_speed
        st.session_state['wind_dir'] = live_dir

    # Sliders pull from session_state if the button was clicked
    wind_speed = st.slider("Wind speed (m/s)", 0.0, 20.0, st.session_state.get('wind_speed', 5.0))
    wind_dir = st.slider("Wind direction (° from N)", 0.0, 360.0, st.session_state.get('wind_dir', 90.0))

# Density assumption to get mass from volume
FUEL_DENSITY = 750  # kg/m3, typical hydrocarbon
mass_total = volume * FUEL_DENSITY
mass_fuel = mass_total * fuel_fraction

# Computations run AFTER sliders are defined
Q_rad = compute_Q_rad(volume)
W_TNT = compute_W_TNT(mass_fuel)

thermal_bands = {"Red": 12.5, "Orange": 4.0, "Yellow": 1.4}
blast_bands = {"Red": 70, "Orange": 20, "Yellow": 3}
colors = {"Red": "red", "Orange": "orange", "Yellow": "gold"}

k_down = 1.2 + 0.05 * wind_speed
k_up = 0.8 - 0.01 * wind_speed

# ---------- STYLING TO MATCH der02_threat_zones.html ----------
# The uploaded template renders a title chip (top-left), a legend card
# (bottom-left), an "industry" AwesomeMarkers facility icon, a blue
# downwind axis line + circle marker, and a collapsible top-right
# LayerControl toggling named feature groups. Reproduced here so this
# script's folium output matches that look.

TITLE_HTML = """
<div style="position: fixed; top: 12px; left: 60px; z-index:9999; background:white;
            padding:8px 14px; border-radius:6px; box-shadow:0 2px 8px rgba(0,0,0,0.3);
            font-family: Arial, sans-serif; font-weight:700; font-size:15px;">
  Threat-Zone Estimation — Fire &amp; Explosion Response
</div>
"""

def build_legend_html(wind_dir, wind_speed):
    return f"""
    <div style="position: fixed; bottom: 20px; left: 20px; z-index: 9999;
                background: white; padding: 12px 14px; border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.3); font-family: Arial, sans-serif;
                font-size: 12.5px; max-width: 320px; line-height: 1.45;">
      <div style="font-weight:700; margin-bottom:6px; font-size:13.5px;">Threat-Zone Legend</div>
      <div style="font-weight:600; margin-top:4px;">Thermal radiation (filled)</div>
      <div><span style="display:inline-block;width:12px;height:12px;background:red;margin-right:6px;"></span>12.5 kW/m² — potentially lethal</div>
      <div><span style="display:inline-block;width:12px;height:12px;background:orange;margin-right:6px;"></span>4.0 kW/m² — PPE brief-exposure limit</div>
      <div><span style="display:inline-block;width:12px;height:12px;background:gold;margin-right:6px;"></span>1.4 kW/m² — pain threshold</div>
      <div style="font-weight:600; margin-top:6px;">Blast overpressure (dashed outline)</div>
      <div><span style="display:inline-block;width:12px;height:12px;background:red;margin-right:6px;"></span>70 kPa — near-total destruction</div>
      <div><span style="display:inline-block;width:12px;height:12px;background:orange;margin-right:6px;"></span>20 kPa — serious structural damage</div>
      <div><span style="display:inline-block;width:12px;height:12px;background:gold;margin-right:6px;"></span>3 kPa — window breakage</div>
      <div style="margin-top:8px; font-weight:600;">Wind: from {wind_dir:.0f}° @ {wind_speed:.1f} m/s</div>
      <div style="color:#333;">Blue line = downwind axis.</div>
      <div style="margin-top:6px; font-size:11px; color:#555;">Zones elongate downwind &amp; compress upwind via a
      wind-displaced effective source — not a fixed-radius circle. Toggle layers top-right to compare thermal vs blast.</div>
    </div>
    """

# Map is drawn AFTER computations
with col2:
    m = folium.Map(location=[lat, lon], zoom_start=13)

    # Title + legend chips, matching the uploaded template's fixed panels
    m.get_root().html.add_child(Element(TITLE_HTML))
    m.get_root().html.add_child(Element(build_legend_html(wind_dir, wind_speed)))

    # Facility marker, styled like the template's black "industry" icon
    facility_icon = folium.Icon(color="black", icon="industry", prefix="fa")
    folium.Marker(
        [lat, lon],
        tooltip="Facility",
        popup="Facility reference point",
        icon=facility_icon,
    ).add_to(m)

    thermal_group = folium.FeatureGroup(name="Thermal radiation zones")
    blast_group = folium.FeatureGroup(name="Blast overpressure zones")

    max_radius = 0.0
    for band, threshold in thermal_bands.items():
        r = thermal_radius(threshold, Q_rad)
        max_radius = max(max_radius, r)
        poly = wind_skew_polygon(lat, lon, r, wind_dir, k_down, k_up)
        folium.Polygon(
            poly, color=colors[band], fill=True, fill_opacity=0.15,
            tooltip=f"Thermal {band}: {threshold} kW/m² boundary",
        ).add_to(thermal_group)

    for band, threshold in blast_bands.items():
        r = blast_radius(threshold, W_TNT)
        max_radius = max(max_radius, r)
        poly = wind_skew_polygon(lat, lon, r, wind_dir, k_down, k_up)
        folium.Polygon(
            poly, color=colors[band], fill=False, dash_array="5,5",
            tooltip=f"Blast {band}: {threshold} kPa boundary",
        ).add_to(blast_group)

    thermal_group.add_to(m)
    blast_group.add_to(m)

    # Blue downwind axis line + circle marker, matching the template
    axis_dist = max(max_radius * 0.6, 100)
    downwind_pt = geo_distance(meters=axis_dist).destination((lat, lon), bearing=wind_dir)
    folium.PolyLine(
        [[lat, lon], [downwind_pt.latitude, downwind_pt.longitude]],
        color="blue", weight=4,
        tooltip=f"Wind: from {wind_dir:.0f}° at {wind_speed:.1f} m/s",
    ).add_to(m)
    folium.CircleMarker(
        [downwind_pt.latitude, downwind_pt.longitude],
        radius=4, color="blue", fill=True, fill_color="blue", fill_opacity=0.2, weight=3,
        tooltip="Downwind direction",
    ).add_to(m)

    # Collapsed-off, top-right layer control toggling the two feature groups
    folium.LayerControl(position="topright", collapsed=False).add_to(m)

    st_folium(m, width=900, height=600)

with col1:
    st.subheader("Computed Radii")
    for band, threshold in thermal_bands.items():
        st.write(f"Thermal {band}: {thermal_radius(threshold, Q_rad):.0f} m")
    for band, threshold in blast_bands.items():
        st.write(f"Blast {band}: {blast_radius(threshold, W_TNT):.0f} m")