# -*- coding: utf-8 -*-
"""
Created on Tue Sep  1 11:22:32 2026

@author: Aaryan
"""

import streamlit as st
import folium
from streamlit_folium import st_folium
import numpy as np
from scipy.optimize import brentq
from geopy.distance import distance as geo_distance
import requests

# =========================================================
# PHYSICS & WEATHER LOGIC  (unchanged from the model teammate)
# =========================================================

def thermal_radius(I_threshold_kw, Q_rad_w, tau=0.8):
    I_threshold_w = I_threshold_kw * 1000
    return np.sqrt((Q_rad_w * tau) / (4 * np.pi * I_threshold_w))

def compute_Q_rad(volume_m3, eta_rad=0.30, m_flux=0.06, dH_c=4.5e7):
    radius_guess = (volume_m3 / (np.pi * 8)) ** (1 / 3)
    A_pool = np.pi * radius_guess ** 2
    return eta_rad * m_flux * A_pool * dH_c

def compute_W_TNT(mass_fuel_kg, eta_exp=0.06, dH_c=4.5e7, dH_tnt=4.184e6):
    return (eta_exp * mass_fuel_kg * dH_c) / dH_tnt

def overpressure_kpa(R, W_TNT):
    Z = R / (W_TNT ** (1 / 3))
    return 1772 / Z - 114 / Z ** 2 + 108 / Z ** 3

def blast_radius(P_threshold_kpa, W_TNT):
    f = lambda R: overpressure_kpa(R, W_TNT) - P_threshold_kpa
    return brentq(f, 0.1, 5000)

def wind_skew_polygon(lat, lon, base_radius_m, wind_dir_deg, k_down=1.8, k_up=0.6):
    points = []
    for theta in range(0, 360, 10):
        delta_deg = (theta - wind_dir_deg + 180) % 360 - 180
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
        response = requests.get(url, timeout=6)
        data = response.json()
        wind_speed_kmh = data['current_weather']['windspeed']
        wind_dir = data['current_weather']['winddirection']
        wind_speed_ms = wind_speed_kmh * (1000 / 3600)
        return float(wind_speed_ms), float(wind_dir), True
    except Exception:
        return 5.0, 90.0, False

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Threat-Zone Estimation",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================
# DESIGN SYSTEM — a control-room look, not a SaaS-card look.
# Deep charcoal-navy base, one hazard-orange signature accent,
# a technical display face for headings, monospace for readouts.
# =========================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap');

:root {
    --bg: #0A0E13;
    --panel: #121820;
    --panel-border: #232E38;
    --text: #E7EDF3;
    --text-muted: #85949E;
    --accent: #FF6A39;
    --red: #E5484D;
    --orange: #F2994A;
    --yellow: #E0B93A;
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: var(--text); }
.stApp { background: var(--bg); }

h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; letter-spacing: -0.01em; }

/* ---------- top masthead ---------- */
.masthead {
    display: flex; align-items: baseline; justify-content: space-between;
    border-bottom: 1px solid var(--panel-border);
    padding-bottom: 14px; margin-bottom: 22px;
}
.masthead h1 { font-size: 1.65rem; font-weight: 700; margin: 0; color: var(--text); }
.masthead .tagline { color: var(--text-muted); font-size: 0.92rem; margin-top: 2px; }
.masthead .badge {
    font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem; color: var(--text-muted);
    border: 1px solid var(--panel-border); border-radius: 5px; padding: 5px 10px; white-space: nowrap;
}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] { background: var(--panel); border-right: 1px solid var(--panel-border); }
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { font-size: 1.05rem; }
[data-testid="stSidebar"] label { color: var(--text-muted) !important; font-size: 0.85rem; }

/* ---------- hero danger banner ---------- */
.hero {
    background: linear-gradient(135deg, rgba(229,72,77,0.14), rgba(229,72,77,0.02));
    border: 1px solid rgba(229,72,77,0.35);
    border-radius: 10px;
    padding: 22px 26px;
    margin-bottom: 22px;
    display: flex; gap: 48px; flex-wrap: wrap; align-items: center;
}
.hero .stat-label { color: var(--text-muted); font-size: 0.82rem; margin-bottom: 4px; }
.hero .stat-value {
    font-family: 'IBM Plex Mono', monospace; font-size: 2.3rem; font-weight: 600;
    color: var(--red); line-height: 1;
}
.hero .stat-unit { font-size: 1rem; color: var(--text-muted); margin-left: 4px; }
.hero .divider { width: 1px; align-self: stretch; background: var(--panel-border); }
.hero .note { color: var(--text-muted); font-size: 0.85rem; max-width: 240px; }

/* ---------- zone cards ---------- */
.zone-card {
    background: var(--panel);
    border: 1px solid var(--panel-border);
    border-left: 3px solid var(--chip-color, var(--accent));
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 10px;
}
.zone-card .zone-name { font-size: 0.82rem; color: var(--text-muted); }
.zone-card .zone-value {
    font-family: 'IBM Plex Mono', monospace; font-size: 1.35rem; font-weight: 600; color: var(--text);
}

/* ---------- section labels ---------- */
.section-label {
    font-family: 'Space Grotesk', sans-serif; font-weight: 600; font-size: 1rem;
    margin: 4px 0 10px 0; color: var(--text);
}

/* ---------- legend ---------- */
.legend-row { display: flex; align-items: center; gap: 8px; font-size: 0.83rem; color: var(--text-muted); margin-bottom: 6px; }
.swatch { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }

/* ---------- weather chip ---------- */
.chip {
    display: inline-flex; align-items: center; gap: 6px;
    font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem;
    background: var(--panel); border: 1px solid var(--panel-border);
    border-radius: 20px; padding: 5px 12px; color: var(--text-muted);
}
.chip .dot { width: 7px; height: 7px; border-radius: 50%; background: #3FB950; }

/* buttons */
.stButton>button {
    background: var(--accent); color: #14100D; border: none; font-weight: 600;
    border-radius: 7px;
}
.stButton>button:hover { background: #FF7F52; color: #14100D; }

/* sliders accent */
[data-testid="stSlider"] [role="slider"] { background-color: var(--accent) !important; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# MASTHEAD
# =========================================================

st.markdown("""
<div class="masthead">
    <div>
        <h1>Threat-Zone Estimation</h1>
        <div class="tagline">Fire &amp; explosion response modeling for industrial facilities</div>
    </div>
    <div class="badge">MODEL — POOL FIRE / VAPOR CLOUD, v1</div>
</div>
""", unsafe_allow_html=True)

# =========================================================
# SIDEBAR — INPUTS
# =========================================================

with st.sidebar:
    st.markdown('<div class="section-label">Facility</div>', unsafe_allow_html=True)
    lat = st.number_input("Latitude", value=12.8406, format="%.4f")
    lon = st.number_input("Longitude", value=80.1534, format="%.4f")
    volume = st.slider("Tank volume (m³)", 100, 10000, 2000)
    fuel_fraction = st.slider("Fraction of contents involved", 0.1, 1.0, 0.5)

    st.markdown('<div class="section-label">Wind</div>', unsafe_allow_html=True)

    if st.button("📡  Fetch live weather", use_container_width=True):
        live_speed, live_dir, ok = get_live_wind_data(lat, lon)
        st.session_state['wind_speed'] = live_speed
        st.session_state['wind_dir'] = live_dir
        st.session_state['weather_ok'] = ok

    weather_ok = st.session_state.get('weather_ok')
    if weather_ok is True:
        st.markdown('<span class="chip"><span class="dot"></span>live data applied</span>', unsafe_allow_html=True)
    elif weather_ok is False:
        st.markdown('<span class="chip">⚠ live fetch failed — using manual values</span>', unsafe_allow_html=True)

    wind_speed = st.slider("Wind speed (m/s)", 0.0, 20.0, st.session_state.get('wind_speed', 5.0))
    wind_dir = st.slider("Wind direction (° from N)", 0.0, 360.0, st.session_state.get('wind_dir', 90.0))

    st.markdown('<div class="section-label">Map legend</div>', unsafe_allow_html=True)
    st.markdown("""
        <div class="legend-row"><span class="swatch" style="background:#E5484D"></span> Red — highest severity</div>
        <div class="legend-row"><span class="swatch" style="background:#F2994A"></span> Orange — moderate severity</div>
        <div class="legend-row"><span class="swatch" style="background:#E0B93A"></span> Yellow — lowest severity</div>
        <div class="legend-row">Filled = thermal &nbsp;·&nbsp; dashed = blast overpressure</div>
    """, unsafe_allow_html=True)

# =========================================================
# COMPUTE
# =========================================================

FUEL_DENSITY = 750  # kg/m3
mass_total = volume * FUEL_DENSITY
mass_fuel = mass_total * fuel_fraction

Q_rad = compute_Q_rad(volume)
W_TNT = compute_W_TNT(mass_fuel)

thermal_bands = {"Red": 12.5, "Orange": 4.0, "Yellow": 1.4}
blast_bands = {"Red": 70, "Orange": 20, "Yellow": 3}
colors = {"Red": "#E5484D", "Orange": "#F2994A", "Yellow": "#E0B93A"}

k_down = 1.2 + 0.05 * wind_speed
k_up = 0.8 - 0.01 * wind_speed

thermal_radii = {b: thermal_radius(t, Q_rad) for b, t in thermal_bands.items()}
blast_radii = {b: blast_radius(t, W_TNT) for b, t in blast_bands.items()}

# =========================================================
# HERO — the number a first responder actually needs
# =========================================================

st.markdown(f"""
<div class="hero">
    <div>
        <div class="stat-label">Thermal danger radius (Red)</div>
        <div class="stat-value">{thermal_radii['Red']:.0f}<span class="stat-unit">m</span></div>
    </div>
    <div class="divider"></div>
    <div>
        <div class="stat-label">Blast danger radius (Red)</div>
        <div class="stat-value">{blast_radii['Red']:.0f}<span class="stat-unit">m</span></div>
    </div>
    <div class="divider"></div>
    <div class="note">Distances from the facility marker within which the modeled thermal
    flux or overpressure exceeds the highest-severity threshold. Zones are stretched
    downwind based on current wind speed and direction.</div>
</div>
""", unsafe_allow_html=True)

# =========================================================
# MAP
# =========================================================

m = folium.Map(location=[lat, lon], zoom_start=13, tiles="CartoDB dark_matter")
folium.Marker([lat, lon], tooltip="Facility",
              icon=folium.Icon(color="orange", icon="fire", prefix="fa")).add_to(m)

for band, threshold in thermal_bands.items():
    r = thermal_radii[band]
    poly = wind_skew_polygon(lat, lon, r, wind_dir, k_down, k_up)
    folium.Polygon(poly, color=colors[band], fill=True, fill_opacity=0.15, weight=2,
                    tooltip=f"Thermal {band}: {threshold} kW/m² boundary — {r:.0f} m").add_to(m)

for band, threshold in blast_bands.items():
    r = blast_radii[band]
    poly = wind_skew_polygon(lat, lon, r, wind_dir, k_down, k_up)
    folium.Polygon(poly, color=colors[band], fill=False, dash_array="6,6", weight=2,
                    tooltip=f"Blast {band}: {threshold} kPa boundary — {r:.0f} m").add_to(m)

st_folium(m, width=None, height=560, use_container_width=True)

# =========================================================
# ZONE BREAKDOWN
# =========================================================

col_a, col_b = st.columns(2)

with col_a:
    st.markdown('<div class="section-label">Thermal radiation zones</div>', unsafe_allow_html=True)
    for band, threshold in thermal_bands.items():
        st.markdown(f"""
        <div class="zone-card" style="--chip-color:{colors[band]}">
            <div class="zone-name">{band} &nbsp;·&nbsp; {threshold} kW/m²</div>
            <div class="zone-value">{thermal_radii[band]:.0f} m</div>
        </div>
        """, unsafe_allow_html=True)

with col_b:
    st.markdown('<div class="section-label">Blast overpressure zones</div>', unsafe_allow_html=True)
    for band, threshold in blast_bands.items():
        st.markdown(f"""
        <div class="zone-card" style="--chip-color:{colors[band]}">
            <div class="zone-name">{band} &nbsp;·&nbsp; {threshold} kPa</div>
            <div class="zone-value">{blast_radii[band]:.0f} m</div>
        </div>
        """, unsafe_allow_html=True)