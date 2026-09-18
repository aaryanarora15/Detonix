import streamlit as st
import folium
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

# Map is drawn AFTER computations
with col2:
    m = folium.Map(location=[lat, lon], zoom_start=13)
    folium.Marker([lat, lon], tooltip="Facility").add_to(m)

    for band, threshold in thermal_bands.items():
        r = thermal_radius(threshold, Q_rad)
        poly = wind_skew_polygon(lat, lon, r, wind_dir, k_down, k_up)
        folium.Polygon(poly, color=colors[band], fill=True, fill_opacity=0.15,
                       tooltip=f"Thermal {band}: {threshold} kW/m² boundary").add_to(m)

    for band, threshold in blast_bands.items():
        r = blast_radius(threshold, W_TNT)      
        poly = wind_skew_polygon(lat, lon, r, wind_dir, k_down, k_up)
        folium.Polygon(poly, color=colors[band], fill=False, dash_array="5,5",
                       tooltip=f"Blast {band}: {threshold} kPa boundary").add_to(m)

    st_folium(m, width=900, height=600)

with col1:
    st.subheader("Computed Radii")
    for band, threshold in thermal_bands.items():
        st.write(f"Thermal {band}: {thermal_radius(threshold, Q_rad):.0f} m")
    for band, threshold in blast_bands.items():
        st.write(f"Blast {band}: {blast_radius(threshold, W_TNT):.0f} m")