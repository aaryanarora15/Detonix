from __future__ import annotations
from flask import Flask, render_template, jsonify, request
import numpy as np
import math
import threading
import time
import requests
from collections import deque
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, Tuple, List

app = Flask(__name__)

# ==============================================================================
# RIGOROUS CHEMICAL FIRE HAZARD MODEL
# ==============================================================================

@dataclass(frozen=True)
class FuelProperties:
    name: str
    density_kg_m3: float
    heat_of_combustion_MJ_kg: float
    mass_burn_flux_kg_m2_s: float
    combustion_efficiency: float 
    radiative_fraction: float 
    flame_temperature_K: float 
    smoke_yield_kg_per_kg: float 
    soot_yield_kg_per_kg: float
    co_yield_kg_per_kg: float
    toxic_index: float
    flash_point_C: Optional[float]
    autoignition_C: Optional[float]
    lel_vol_pct: Optional[float]
    uel_vol_pct: Optional[float]
    explosion_hazard: float      
    confinement_sensitivity: float  
    volatility: float            
    wind_sensitivity: float      

FUEL_DATABASE: Dict[str, FuelProperties] = {
    "petrol": FuelProperties(name="petrol", density_kg_m3=740, heat_of_combustion_MJ_kg=43.4, mass_burn_flux_kg_m2_s=0.055, combustion_efficiency=0.75, radiative_fraction=0.30, flame_temperature_K=1500, smoke_yield_kg_per_kg=0.08, soot_yield_kg_per_kg=0.015, co_yield_kg_per_kg=0.015, toxic_index=1.2, flash_point_C=-43, autoignition_C=280, lel_vol_pct=1.4, uel_vol_pct=7.6, explosion_hazard=0.75, confinement_sensitivity=0.9, volatility=0.95, wind_sensitivity=0.75),
    "diesel": FuelProperties(name="diesel", density_kg_m3=830, heat_of_combustion_MJ_kg=42.6, mass_burn_flux_kg_m2_s=0.039, combustion_efficiency=0.80, radiative_fraction=0.30, flame_temperature_K=1350, smoke_yield_kg_per_kg=0.06, soot_yield_kg_per_kg=0.02, co_yield_kg_per_kg=0.012, toxic_index=1.1, flash_point_C=52, autoignition_C=210, lel_vol_pct=0.6, uel_vol_pct=7.5, explosion_hazard=0.40, confinement_sensitivity=0.75, volatility=0.45, wind_sensitivity=0.60),
    "kerosene": FuelProperties(name="kerosene", density_kg_m3=810, heat_of_combustion_MJ_kg=43.2, mass_burn_flux_kg_m2_s=0.039, combustion_efficiency=0.78, radiative_fraction=0.30, flame_temperature_K=1400, smoke_yield_kg_per_kg=0.07, soot_yield_kg_per_kg=0.018, co_yield_kg_per_kg=0.014, toxic_index=1.1, flash_point_C=38, autoignition_C=220, lel_vol_pct=0.7, uel_vol_pct=5.0, explosion_hazard=0.45, confinement_sensitivity=0.75, volatility=0.55, wind_sensitivity=0.60),
    "ethanol": FuelProperties(name="ethanol", density_kg_m3=789, heat_of_combustion_MJ_kg=26.8, mass_burn_flux_kg_m2_s=0.015, combustion_efficiency=0.85, radiative_fraction=0.20, flame_temperature_K=1300, smoke_yield_kg_per_kg=0.015, soot_yield_kg_per_kg=0.002, co_yield_kg_per_kg=0.006, toxic_index=0.8, flash_point_C=13, autoignition_C=363, lel_vol_pct=3.3, uel_vol_pct=19.0, explosion_hazard=0.55, confinement_sensitivity=0.85, volatility=0.80, wind_sensitivity=0.70),
    "lpg": FuelProperties(name="LPG", density_kg_m3=500, heat_of_combustion_MJ_kg=46.0, mass_burn_flux_kg_m2_s=0.080, combustion_efficiency=0.85, radiative_fraction=0.30, flame_temperature_K=1950, smoke_yield_kg_per_kg=0.03, soot_yield_kg_per_kg=0.006, co_yield_kg_per_kg=0.008, toxic_index=1.0, flash_point_C=-74, autoignition_C=470, lel_vol_pct=1.8, uel_vol_pct=9.5, explosion_hazard=0.95, confinement_sensitivity=1.0, volatility=1.0, wind_sensitivity=0.95),
    "methane": FuelProperties(name="methane", density_kg_m3=422, heat_of_combustion_MJ_kg=50.0, mass_burn_flux_kg_m2_s=0.060, combustion_efficiency=0.90, radiative_fraction=0.20, flame_temperature_K=1950, smoke_yield_kg_per_kg=0.01, soot_yield_kg_per_kg=0.001, co_yield_kg_per_kg=0.006, toxic_index=0.7, flash_point_C=-188, autoignition_C=540, lel_vol_pct=5.0, uel_vol_pct=15.0, explosion_hazard=0.95, confinement_sensitivity=1.0, volatility=1.0, wind_sensitivity=0.95),
    "hydrogen": FuelProperties(name="hydrogen", density_kg_m3=71, heat_of_combustion_MJ_kg=120.0, mass_burn_flux_kg_m2_s=0.040, combustion_efficiency=0.95, radiative_fraction=0.10, flame_temperature_K=2400, smoke_yield_kg_per_kg=0.001, soot_yield_kg_per_kg=0.0, co_yield_kg_per_kg=0.0, toxic_index=0.2, flash_point_C=-253, autoignition_C=500, lel_vol_pct=4.0, uel_vol_pct=75.0, explosion_hazard=1.0, confinement_sensitivity=1.0, volatility=1.0, wind_sensitivity=1.0),
    "wood": FuelProperties(name="wood", density_kg_m3=500, heat_of_combustion_MJ_kg=18.0, mass_burn_flux_kg_m2_s=0.012, combustion_efficiency=0.70, radiative_fraction=0.30, flame_temperature_K=1100, smoke_yield_kg_per_kg=0.12, soot_yield_kg_per_kg=0.02, co_yield_kg_per_kg=0.03, toxic_index=1.0, flash_point_C=None, autoignition_C=None, lel_vol_pct=None, uel_vol_pct=None, explosion_hazard=0.05, confinement_sensitivity=0.35, volatility=0.05, wind_sensitivity=0.85),
    "plastic": FuelProperties(name="plastic", density_kg_m3=950, heat_of_combustion_MJ_kg=30.0, mass_burn_flux_kg_m2_s=0.022, combustion_efficiency=0.75, radiative_fraction=0.28, flame_temperature_K=1250, smoke_yield_kg_per_kg=0.18, soot_yield_kg_per_kg=0.04, co_yield_kg_per_kg=0.025, toxic_index=1.8, flash_point_C=None, autoignition_C=None, lel_vol_pct=None, uel_vol_pct=None, explosion_hazard=0.15, confinement_sensitivity=0.50, volatility=0.30, wind_sensitivity=0.70),
    "rubber": FuelProperties(name="rubber", density_kg_m3=1100, heat_of_combustion_MJ_kg=32.0, mass_burn_flux_kg_m2_s=0.025, combustion_efficiency=0.72, radiative_fraction=0.32, flame_temperature_K=1250, smoke_yield_kg_per_kg=0.25, soot_yield_kg_per_kg=0.08, co_yield_kg_per_kg=0.05, toxic_index=2.5, flash_point_C=None, autoignition_C=None, lel_vol_pct=None, uel_vol_pct=None, explosion_hazard=0.10, confinement_sensitivity=0.50, volatility=0.10, wind_sensitivity=0.65),
}

@dataclass
class FireInputs:
    fuel_mass_kg: float = 5000.0
    burning_area_m2: float = 50.0
    ambient_temperature_C: float = 30.0
    wind_speed_m_s: float = 2.0
    relative_humidity_pct: float = 50.0
    terrain_slope_deg: float = 0.0
    confinement: float = 0.0  
    elapsed_time_s: float = 0.0
    consumed_fuel_kg: float = 0.0

@dataclass
class FireResult:
    hrr_MW: float
    mass_burning_rate_kg_s: float
    flame_temperature_C: float
    smoke_generation_kg_s: float
    soot_generation_kg_s: float
    co_generation_kg_s: float
    thermal_hazard_index: float
    smoke_hazard_index: float
    explosion_hazard_index: float
    spread_rate_m_s: float
    predicted_fire_radius_m: float
    recommended_safety_radius_m: float
    max_blast_radius_m: float       
    burnout_time_s: float
    effective_burning_area_m2: float
    effective_combustion_efficiency: float
    confidence_score: float
    tactical_warnings: List[str]
    def as_dict(self) -> dict: return asdict(self)

def get_fuel(name: str) -> FuelProperties:
    return FUEL_DATABASE.get(name.strip().lower(), FUEL_DATABASE["petrol"])

def simulate_fire(fuel_name: str, inputs: FireInputs) -> FireResult:
    fuel = get_fuel(fuel_name)
    wind_factor = 1.0 + 0.08 * fuel.wind_sensitivity * min(inputs.wind_speed_m_s, 20.0)
    confinement_factor = 1.0 - 0.25 * fuel.confinement_sensitivity * inputs.confinement
    
    smoke_retention = fuel.smoke_yield_kg_per_kg / max(0.5, inputs.wind_speed_m_s)
    choke_factor = max(0.15, 1.0 - (smoke_retention * (inputs.elapsed_time_s / 120.0)))
    eff_combustion = fuel.combustion_efficiency * choke_factor
    
    progress = inputs.consumed_fuel_kg / inputs.fuel_mass_kg if inputs.fuel_mass_kg > 0 else 1.0
    
    if progress >= 1.0:
        spread_factor = 0.0
    elif progress < 0.15: 
        growth = progress / 0.15
        spread_factor = 0.1 + 0.9 * math.pow(growth, 1.0 / max(0.1, fuel.volatility))
    elif progress <= 0.70:
        spread_factor = 1.0 * choke_factor
    else: 
        decay = max(0.0, (1.0 - progress) / 0.30)
        spread_factor = choke_factor * math.pow(decay, 1.5)
        
    eff_area = inputs.burning_area_m2 * spread_factor
    nominal_m_dot = max(0.001, fuel.mass_burn_flux_kg_m2_s * wind_factor * confinement_factor * eff_area)
    total_burnout_time_s = inputs.fuel_mass_kg / max(0.001, fuel.mass_burn_flux_kg_m2_s * inputs.burning_area_m2)
    
    m_dot = nominal_m_dot * (eff_combustion / fuel.combustion_efficiency)
    hrr_MW = (m_dot * fuel.heat_of_combustion_MJ_kg * eff_combustion) / 1000.0
    
    slope_factor = 1.0 + 0.03 * max(inputs.terrain_slope_deg, 0.0)
    humidity_factor = 1.0 - 0.002 * min(max(inputs.relative_humidity_pct - 20.0, 0.0), 70.0)
    
    fire_radius = math.sqrt(max(eff_area, 0.0) / math.pi) * slope_factor
    spread_rate = (fire_radius / max(1.0, inputs.elapsed_time_s)) if progress < 0.15 else 0.0
    
    smoke_rate = m_dot * fuel.smoke_yield_kg_per_kg
    soot_rate = m_dot * fuel.soot_yield_kg_per_kg
    co_rate = m_dot * fuel.co_yield_kg_per_kg

    thermal_power_W = fuel.radiative_fraction * hrr_MW * 1_000_000.0
    thermal_radius = math.sqrt(thermal_power_W / (4.0 * math.pi * 5.0 * 1000.0)) if hrr_MW > 0 else 0.0
    
    accumulated_smoke_vol = smoke_rate * inputs.elapsed_time_s
    smoke_radius_expansion = math.sqrt(accumulated_smoke_vol) * wind_factor * 1.5
    
    safety_radius = min(max(15.0, thermal_radius + smoke_radius_expansion) * (1.0 + 0.04 * fuel.wind_sensitivity * min(inputs.wind_speed_m_s, 25.0)), 5000.0)
    
    thermal_idx = min(100.0, 22.0 * math.log10(1.0 + max(hrr_MW, 0.0)) * 10.0) * (0.8 + 0.2 * fuel.radiative_fraction)
    smoke_idx = min(100.0, 30.0 * smoke_rate + (smoke_retention * 50.0)) * min(2.0, fuel.toxic_index) * (1.0 + 0.35 * inputs.confinement)
    explosion_idx = 100.0 * fuel.explosion_hazard * (0.4 + 0.6 * inputs.confinement)
    
    blast_energy_MJ = inputs.fuel_mass_kg * fuel.heat_of_combustion_MJ_kg * (fuel.explosion_hazard * 0.1)
    max_blast_radius_m = (max(blast_energy_MJ, 1.0) ** (1.0 / 3.0)) * 60.0 
    
    warnings = []
    if choke_factor < 0.6 and m_dot > 0:
        warnings.append(f"OXYGEN STARVATION: Intense smoke from {fuel.name.upper()} is physically choking the fire. Burning area is actively decreasing.")
    if (fuel.toxic_index >= 1.5 or smoke_idx > 60) and m_dot > 0:
        warnings.append(f"CRITICAL TOXICITY: {fuel.name.upper()} generates highly poisonous fumes (Dense Soot/CO). Immediate respiratory protection required downwind.")
    elif fuel.toxic_index >= 1.0 and m_dot > 0:
        warnings.append(f"MODERATE TOXICITY: Avoid smoke plume inhalation. CO generation rate at {co_rate:.2f} kg/s.")
        
    if explosion_idx > 70: warnings.append(f"BLAST HAZARD: High volatility/confinement detected. Maintain absolute exclusion perimeter.")
    if inputs.wind_speed_m_s > 8.0 and m_dot > 0: warnings.append(f"WIND SPREAD: High winds driving downwind flame tilt and aggressive toxic plume advection.")

    confidence = max(0.4, 0.95 - (1.0 - choke_factor)) if m_dot > 0 else 1.0

    return FireResult(
        hrr_MW=hrr_MW, mass_burning_rate_kg_s=m_dot, flame_temperature_C=fuel.flame_temperature_K - 273.15, 
        smoke_generation_kg_s=smoke_rate, soot_generation_kg_s=soot_rate, co_generation_kg_s=co_rate,
        thermal_hazard_index=thermal_idx, smoke_hazard_index=smoke_idx, explosion_hazard_index=explosion_idx,
        spread_rate_m_s=spread_rate, predicted_fire_radius_m=fire_radius, recommended_safety_radius_m=safety_radius,
        max_blast_radius_m=max_blast_radius_m, burnout_time_s=total_burnout_time_s,
        effective_burning_area_m2=eff_area, effective_combustion_efficiency=eff_combustion,
        confidence_score=confidence, tactical_warnings=warnings
    )

# ==============================================================================
# SYSTEM STATE & SENSOR FUSION
# ==============================================================================

incident_state = {
    "lat": 12.8406, "lon": 80.1534,
    "fuel_type": "petrol", "fuel_mass_kg": 15000.0, "burning_area_m2": 150.0, 
    "ambient_temperature_C": 30.0,
    "wind_speed_m_s": 2.5, "wind_direction_deg": 90.0,
    "relative_humidity_pct": 50.0, "terrain_slope_deg": 0.0,
    "confinement": 0.0,
    "use_api_weather": False,
    
    "hazard_mode": "POOL_BURN", 
    "burnout_time_s": 0.0,
    "sim_time_s": 0.0, 
    "consumed_fuel_kg": 0.0,
    "is_playing": True, 
    "last_tick": time.time()
}

drone_state = {
    "lat": 12.8406, "lon": 80.1534,
    "mode": "ORBIT", "altitude": 35.0, "orbit_radius": 120.0,
    "waypoint_queue": [], "current_wp_index": 0,
    "thermocouple_temp": 30.0, "ir_radiant_flux": 0.0, "smoke_density": 0.0,
    "anemometer_3D": [0.0, 0.0, 0.0]
}

weather_api_state = {
    "temperature_2m": 30.0,
    "relative_humidity_2m": 50.0,
    "wind_speed_10m": 2.5,
    "wind_direction_10m": 90.0,
    "last_fetch_time": 0.0,
    "status": "INITIALIZING"
}

drone_wind_history = deque(maxlen=600)
current_fire_result = None
predicted_wind_5min = {"speed": 2.5, "direction": 90.0}

def fetch_open_meteo(lat, lon):
    global weather_api_state
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m&wind_speed_unit=ms"
        res = requests.get(url, timeout=5).json()
        if "current" in res:
            curr = res["current"]
            weather_api_state["temperature_2m"] = float(curr.get("temperature_2m", weather_api_state["temperature_2m"]))
            weather_api_state["relative_humidity_2m"] = float(curr.get("relative_humidity_2m", weather_api_state["relative_humidity_2m"]))
            weather_api_state["wind_speed_10m"] = float(curr.get("wind_speed_10m", weather_api_state["wind_speed_10m"]))
            weather_api_state["wind_direction_10m"] = float(curr.get("wind_direction_10m", weather_api_state["wind_direction_10m"]))
            weather_api_state["status"] = "OK"
    except Exception:
        weather_api_state["status"] = "ERROR"

def generate_wind_distorted_contour(center_lat, center_lon, base_radius_m, wind_speed, wind_angle_rad, time_offset_sec=0):
    if base_radius_m <= 0.1: return [] 
    meters_to_deg = 1.0 / 111320.0
    num_points = 90
    polygon_coords = []
    phase = (time.time() + time_offset_sec) * 2.5 
    downwind_shift = base_radius_m * 0.4 * (wind_speed / 3.0) + (time_offset_sec * 0.1)

    for i in range(num_points):
        angle = (i / num_points) * (2 * math.pi)
        turbulence = math.sin(4 * angle + phase) * (base_radius_m * 0.1) + math.cos(7 * angle - phase*0.5) * (base_radius_m * 0.05)
        r = base_radius_m + turbulence
        
        alignment = math.cos(angle - wind_angle_rad)
        wind_stretch_factor = 1.0 + (0.8 * (wind_speed / 3.0) * alignment)
        r *= max(0.4, wind_stretch_factor)

        dx = (r * math.cos(angle)) + (downwind_shift * math.cos(wind_angle_rad))
        dy = (r * math.sin(angle)) + (downwind_shift * math.sin(wind_angle_rad))

        p_lat = center_lat + (dx * meters_to_deg)
        p_lon = center_lon + (dy * meters_to_deg) / math.cos(math.radians(center_lat))
        
        polygon_coords.append([p_lon, p_lat])
        
    polygon_coords.append(polygon_coords[0])
    return [polygon_coords]

def generate_perfect_circle(center_lat, center_lon, radius_m):
    meters_to_deg = 1.0 / 111320.0
    num_points = 90
    polygon_coords = []
    for i in range(num_points):
        angle = (i / num_points) * (2 * math.pi)
        dx = radius_m * math.cos(angle)
        dy = radius_m * math.sin(angle)
        p_lat = center_lat + (dx * meters_to_deg)
        p_lon = center_lon + (dy * meters_to_deg) / math.cos(math.radians(center_lat))
        polygon_coords.append([p_lon, p_lat])
    polygon_coords.append(polygon_coords[0])
    return [polygon_coords]

def background_drone_simulation():
    global drone_state, incident_state, current_fire_result, weather_api_state, drone_wind_history, predicted_wind_5min
    orbit_angle = 0.0

    while True:
        time.sleep(0.1)  
        now = time.time()
        dt = now - incident_state["last_tick"]
        incident_state["last_tick"] = now

        if incident_state["is_playing"]:
            if incident_state["consumed_fuel_kg"] < incident_state["fuel_mass_kg"]:
                incident_state["sim_time_s"] += dt * 2.0 

        if incident_state["use_api_weather"]:
            if now - weather_api_state["last_fetch_time"] > 60.0:
                threading.Thread(target=fetch_open_meteo, args=(incident_state["lat"], incident_state["lon"]), daemon=True).start()
                weather_api_state["last_fetch_time"] = now
            base_ws = weather_api_state["wind_speed_10m"]
            base_wd = weather_api_state["wind_direction_10m"]
            base_temp = weather_api_state["temperature_2m"]
            base_rh = weather_api_state["relative_humidity_2m"]
        else:
            base_ws = incident_state["wind_speed_m_s"]
            base_wd = incident_state["wind_direction_deg"]
            base_temp = incident_state["ambient_temperature_C"]
            base_rh = incident_state["relative_humidity_pct"]

        noise_ws = math.sin(now * 0.8) * (base_ws * 0.2) + np.random.normal(0, 0.15)
        noise_wd = math.cos(now * 0.5) * 10.0 + np.random.normal(0, 1.5)
        
        live_ws = max(0.1, base_ws + noise_ws)
        live_wd = (base_wd + noise_wd) % 360
        live_wd_rad = math.radians(live_wd)

        drone_state["anemometer_3D"] = [
            round(live_ws * math.cos(live_wd_rad), 2),
            round(live_ws * math.sin(live_wd_rad), 2),
            0.0
        ]
        drone_wind_history.append((now, live_wd))

        fused_ws = (0.3 * base_ws) + (0.7 * live_ws)

        rate_deg_per_sec = 0.0
        if len(drone_wind_history) > 20:
            old_t, old_wd = drone_wind_history[0]
            recent_t, recent_wd = drone_wind_history[-1]
            diff = (recent_wd - old_wd + 180) % 360 - 180 
            time_span = max(0.1, recent_t - old_t)
            rate_deg_per_sec = diff / time_span

        projected_drone_wd = (live_wd + rate_deg_per_sec * 300) % 360
        x_blend = 0.6 * math.cos(math.radians(projected_drone_wd)) + 0.4 * math.cos(math.radians(base_wd))
        y_blend = 0.6 * math.sin(math.radians(projected_drone_wd)) + 0.4 * math.sin(math.radians(base_wd))
        pred_wd_5min = (math.degrees(math.atan2(y_blend, x_blend)) + 360) % 360

        predicted_wind_5min["speed"] = round(fused_ws, 1)
        predicted_wind_5min["direction"] = round(pred_wd_5min, 1)

        f_inputs = FireInputs(
            fuel_mass_kg=incident_state["fuel_mass_kg"], 
            burning_area_m2=incident_state["burning_area_m2"],
            ambient_temperature_C=base_temp,
            wind_speed_m_s=fused_ws, 
            relative_humidity_pct=base_rh,
            terrain_slope_deg=incident_state["terrain_slope_deg"],
            confinement=incident_state["confinement"], 
            elapsed_time_s=incident_state["sim_time_s"],
            consumed_fuel_kg=incident_state["consumed_fuel_kg"]
        )
        
        current_fire_result = simulate_fire(incident_state["fuel_type"], f_inputs)
        incident_state["burnout_time_s"] = current_fire_result.burnout_time_s

        if incident_state["is_playing"]:
            incident_state["consumed_fuel_kg"] += current_fire_result.mass_burning_rate_kg_s * (dt * 2.0)
            if incident_state["consumed_fuel_kg"] > incident_state["fuel_mass_kg"]:
                incident_state["consumed_fuel_kg"] = incident_state["fuel_mass_kg"]

        fire_center = (incident_state["lat"], incident_state["lon"])

        if drone_state["mode"] == "ORBIT":
            orbit_angle += 0.03
            orbit_radius_deg = drone_state["orbit_radius"] / 111320.0
            drone_state["lat"] += ((fire_center[0] + (orbit_radius_deg * math.cos(orbit_angle))) - drone_state["lat"]) * 0.2
            drone_state["lon"] += ((fire_center[1] + (orbit_radius_deg * math.sin(orbit_angle)) / math.cos(math.radians(fire_center[0]))) - drone_state["lon"]) * 0.2

        elif drone_state["mode"] == "WAYPOINT_SEQUENCE" and drone_state["waypoint_queue"]:
            target = drone_state["waypoint_queue"][drone_state["current_wp_index"]]
            if math.sqrt(((target["lat"] - drone_state["lat"]) * 111320)**2 + ((target["lon"] - drone_state["lon"]) * 111320)**2) < 15.0:
                drone_state["current_wp_index"] += 1
                if drone_state["current_wp_index"] >= len(drone_state["waypoint_queue"]): drone_state["mode"] = "ORBIT"
            else:
                drone_state["lat"] += (target["lat"] - drone_state["lat"]) * 0.1
                drone_state["lon"] += (target["lon"] - drone_state["lon"]) * 0.1

        d_lat = drone_state["lat"] - fire_center[0]
        d_lon = drone_state["lon"] - fire_center[1]
        ground_dist_m = math.sqrt((d_lat * 111320)**2 + (d_lon * 111320 * math.cos(math.radians(fire_center[0])))**2)
        altitude_m = drone_state["altitude"]
        dist_3d_m = math.sqrt(ground_dist_m**2 + altitude_m**2)

        fuel_obj = get_fuel(incident_state["fuel_type"])
        calc_flux = 0.0
        if current_fire_result.hrr_MW > 0:
            q_W_m2 = (fuel_obj.radiative_fraction * current_fire_result.hrr_MW * 1_000_000.0) / (4.0 * math.pi * max(dist_3d_m, 1.0)**2)
            calc_flux = q_W_m2 / 1000.0

        flux_noise = np.random.normal(0, max(0.01, calc_flux * 0.05)) if calc_flux > 0 else 0.0
        temp_noise = np.random.normal(0, 0.5) if calc_flux > 0 else 0.0
        base_smoke = (current_fire_result.smoke_generation_kg_s * 1000) / (1.0 + (dist_3d_m/20)**1.5)
        smoke_noise = np.random.normal(0, max(0.01, base_smoke * 0.08)) if base_smoke > 0 else 0.0

        drone_state["ir_radiant_flux"] = round(max(0.0, calc_flux + flux_noise), 2)
        drone_state["thermocouple_temp"] = round(base_temp + min(900.0, calc_flux * 4.5) + temp_noise, 1)
        drone_state["smoke_density"] = round(max(0.0, base_smoke + smoke_noise), 2)

# ==============================================================================
# FLASK ROUTES
# ==============================================================================

@app.route('/')
def index(): return render_template('index.html')

@app.route('/api/command', methods=['POST'])
def control_command():
    global drone_state, incident_state
    data = request.json or {}
    cmd = data.get('command')
    
    if cmd == 'UPDATE_INCIDENT':
        for k in data.get('config', {}):
            if k in incident_state: incident_state[k] = data['config'][k]
        incident_state["sim_time_s"] = 0.0
        incident_state["consumed_fuel_kg"] = 0.0
        
    elif cmd == 'SET_LOCATION':
        incident_state["lat"] = float(data.get('lat', incident_state["lat"]))
        incident_state["lon"] = float(data.get('lon', incident_state["lon"]))
        incident_state["consumed_fuel_kg"] = 0.0
        incident_state["sim_time_s"] = 0.0
        if incident_state["use_api_weather"]:
            threading.Thread(target=fetch_open_meteo, args=(incident_state["lat"], incident_state["lon"]), daemon=True).start()
    elif cmd == 'SET_WEATHER_MODE':
        incident_state["use_api_weather"] = bool(data.get("use_api", False))
        if incident_state["use_api_weather"]:
            threading.Thread(target=fetch_open_meteo, args=(incident_state["lat"], incident_state["lon"]), daemon=True).start()
    elif cmd == 'SET_HAZARD_MODE': 
        incident_state["hazard_mode"] = data.get('mode', 'POOL_BURN')
        incident_state["sim_time_s"] = 0.0
        incident_state["consumed_fuel_kg"] = 0.0
    elif cmd == 'PLAY_PAUSE': 
        incident_state["is_playing"] = not incident_state["is_playing"]
    elif cmd == 'RESET_TIME': 
        incident_state["sim_time_s"] = 0.0
        incident_state["consumed_fuel_kg"] = 0.0
    elif cmd == 'SCRUB_TIME': 
        incident_state["sim_time_s"] = float(data.get('time_s', 0.0))
    elif cmd == 'STEP_TIME':
        direction = float(data.get('step', 0.0))
        incident_state["sim_time_s"] = max(0.0, incident_state["sim_time_s"] + direction)
    elif cmd == 'SET_DRONE_MODE': 
        drone_state["mode"] = data.get('mode', 'ORBIT')
    elif cmd == 'UAV_CMD':
        ucmd = data.get('uav_command')
        if ucmd == 'ORBIT': drone_state["mode"] = "ORBIT"; drone_state["waypoint_queue"] = []
        elif ucmd == 'START_MISSION': drone_state["mode"] = "WAYPOINT_SEQUENCE"; drone_state["current_wp_index"] = 0
        elif ucmd == 'CLEAR_WAYPOINTS': drone_state["waypoint_queue"] = []; drone_state["mode"] = "ORBIT"
        elif ucmd == 'ADD_WAYPOINT': drone_state["waypoint_queue"].append({"lat": data['lat'], "lon": data['lon']})
    elif cmd == 'UPDATE_DRONE':    
        if 'orbit_radius' in data: drone_state["orbit_radius"] = float(data['orbit_radius'])
        if 'altitude' in data: drone_state["altitude"] = float(data['altitude'])

    return jsonify({"status": "SUCCESS"})

@app.route('/api/state', methods=['GET'])
def get_state():
    if not current_fire_result: return jsonify({"status": "WAITING"})

    fire_center = (incident_state["lat"], incident_state["lon"])
    u, v = drone_state["anemometer_3D"][0], drone_state["anemometer_3D"][1]
    live_wind_speed = math.sqrt(u**2 + v**2)
    live_wind_angle = math.atan2(v, u)
    live_wind_deg = (math.degrees(live_wind_angle) + 360) % 360

    pred_angle = math.radians(predicted_wind_5min["direction"])
    pred_speed = predicted_wind_5min["speed"]

    fuel = get_fuel(incident_state["fuel_type"])
    features = []

    def radius_for_flux(q_target):
        if current_fire_result.hrr_MW <= 0: return 0.0
        val = (fuel.radiative_fraction * current_fire_result.hrr_MW * 1e6) / (4.0 * math.pi * q_target * 1000.0)
        return math.sqrt(val) if val > 0 else 0.0

    r_red = max(current_fire_result.predicted_fire_radius_m + 5.0, radius_for_flux(37.5))
    r_yellow = max(r_red + 20.0, radius_for_flux(12.5))
    r_green = max(r_yellow + 40.0, current_fire_result.recommended_safety_radius_m)

    if current_fire_result.predicted_fire_radius_m > 0:
        red_poly = generate_wind_distorted_contour(fire_center[0], fire_center[1], r_red, live_wind_speed, live_wind_angle)
        yellow_poly = generate_wind_distorted_contour(fire_center[0], fire_center[1], r_yellow, live_wind_speed, live_wind_angle)
        green_poly = generate_wind_distorted_contour(fire_center[0], fire_center[1], r_green, live_wind_speed, live_wind_angle)
        forecast_5m = generate_wind_distorted_contour(fire_center[0], fire_center[1], r_yellow, pred_speed, pred_angle, 300)

        features.extend([
            {
                "type": "Feature", 
                "properties": {
                    "severity": "Safe Boundary (Green)", 
                    "color": "#27ae60", 
                    "radius": r_green,
                    "temp_C": round(incident_state["ambient_temperature_C"] + 4.5, 1),
                    "flux_kW": 1.4,
                    "danger_level": "SAFE EXCLUSION / STAGING",
                    "tactical_desc": "Boundary limit for public safety and emergency staging. Wear standard PPE."
                }, 
                "geometry": {"type": "Polygon", "coordinates": green_poly}
            },
            {
                "type": "Feature", 
                "properties": {
                    "severity": "Ignition Zone (Yellow)", 
                    "color": "#f39c12", 
                    "radius": r_yellow,
                    "temp_C": round(current_fire_result.flame_temperature_C * 0.45, 1),
                    "flux_kW": 12.5,
                    "danger_level": "SEVERE BURN / STRUCTURAL IGNITION",
                    "tactical_desc": "2nd-degree blistering burns in < 10s. Flammable materials ignite rapidly without cooling."
                }, 
                "geometry": {"type": "Polygon", "coordinates": yellow_poly}
            },
            {
                "type": "Feature", 
                "properties": {
                    "severity": "Lethal Core (Red)", 
                    "color": "#c0392b", 
                    "radius": r_red,
                    "temp_C": round(current_fire_result.flame_temperature_C, 1),
                    "flux_kW": 37.5,
                    "danger_level": "EXTREME THERMAL LETHALITY (100%)",
                    "tactical_desc": "Fatal in < 15 seconds. Rapid flashover and continuous steel compromise zone."
                }, 
                "geometry": {"type": "Polygon", "coordinates": red_poly}
            },
            {
                "type": "Feature", 
                "properties": {
                    "severity": "Forecast [+5M Shift]", 
                    "color": "#8b5cf6", 
                    "radius": r_yellow,
                    "temp_C": round(current_fire_result.flame_temperature_C * 0.35, 1),
                    "flux_kW": 10.0,
                    "danger_level": "PROJECTED PLUME SPREAD",
                    "tactical_desc": "Estimated flame tilt and toxic cloud drift corridor based on drone sensor history."
                }, 
                "geometry": {"type": "Polygon", "coordinates": forecast_5m}
            }
        ])

    if incident_state["hazard_mode"] == "BLEVE_BLAST":
        raw_radius = incident_state["sim_time_s"] * 343.0
        max_blast = current_fire_result.max_blast_radius_m
        if raw_radius <= max_blast + (343.0 * 2.0): 
            display_radius = min(raw_radius, max_blast)
            blast_poly = generate_perfect_circle(fire_center[0], fire_center[1], display_radius)
            features.append({
                "type": "Feature", 
                "properties": {
                    "severity": "BLEVE Shockwave", 
                    "color": "#06b6d4", 
                    "radius": display_radius, 
                    "is_blast": True,
                    "temp_C": 450.0,
                    "flux_kW": 50.0,
                    "danger_level": "SUPERSONIC OVERPRESSURE WAVE",
                    "tactical_desc": "Structural collapse and severe shrapnel blast radius."
                }, 
                "geometry": {"type": "Polygon", "coordinates": blast_poly}
            })

    geojson = {"type": "FeatureCollection", "features": features}

    base_m_dot = current_fire_result.mass_burning_rate_kg_s
    if base_m_dot > 0.001:
        live_outputs = {
            "burn_rate": max(0.0, base_m_dot + np.random.normal(0, base_m_dot * 0.02)),
            "soot": max(0.0, current_fire_result.soot_generation_kg_s + np.random.normal(0, current_fire_result.soot_generation_kg_s * 0.05)),
            "co": max(0.0, current_fire_result.co_generation_kg_s + np.random.normal(0, current_fire_result.co_generation_kg_s * 0.05))
        }
    else:
        live_outputs = {"burn_rate": 0.0, "soot": 0.0, "co": 0.0}

    # Drone GPS Crosscheck
    d_lat = drone_state["lat"] - fire_center[0]
    d_lon = drone_state["lon"] - fire_center[1]
    dist_2d = math.sqrt((d_lat * 111320)**2 + (d_lon * 111320 * math.cos(math.radians(fire_center[0])))**2)
    bearing_drone = (math.degrees(math.atan2(d_lon, d_lat)) + 360) % 360

    gps_crosscheck = {
        "incident_gps": [round(incident_state["lat"], 5), round(incident_state["lon"], 5)],
        "drone_gps": [round(drone_state["lat"], 5), round(drone_state["lon"], 5)],
        "range_m": round(dist_2d, 1),
        "bearing_deg": round(bearing_drone, 1),
        "status": "LOCKED & VERIFIED" if dist_2d < (drone_state["orbit_radius"] * 1.5) else "TARGET ACQUIRED"
    }

    return jsonify({
        "drone": drone_state,
        "incident": incident_state,
        "gps_crosscheck": gps_crosscheck,
        "weather_api": weather_api_state,
        "predicted_5min_wind": predicted_wind_5min,
        "fire_dynamics": current_fire_result.as_dict(),
        "fuel_properties": asdict(fuel),
        "live_outputs": live_outputs,
        "live_wind": {"speed": round(live_wind_speed, 1), "angle": round(live_wind_deg, 1)},
        "zones": geojson
    })

if __name__ == '__main__':
    sim_thread = threading.Thread(target=background_drone_simulation, daemon=True)
    sim_thread.start()
    app.run(debug=True, port=5000, use_reloader=False)