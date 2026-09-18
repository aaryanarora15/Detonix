# -*- coding: utf-8 -*-
"""
Created on Tue Sep  1 15:33:54 2026

@author: Aaryan
"""

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import time

# Incorporating configurations from config.toml and external modules[cite: 1]
st.set_page_config(
    page_title="FIRE-OPS | Threat Alert System",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS inspired by image_b7d8ae.png
st.markdown("""
<style>
    .stApp {
        background-color: #050505;
        color: #ffffff;
        font-family: 'Inter', sans-serif;
    }
    
    h1, h2, h3 {
        color: #ffffff;
    }
    
    .highlight {
        color: #FF4500; /* Vibrant Orange/Red */
        font-weight: 800;
    }
    
    .metric-container {
        background-color: #111111;
        border-left: 4px solid #FF4500;
        padding: 20px;
        border-radius: 4px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    }
    
    .stButton>button {
        background-color: #FF4500;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 10px 24px;
        font-weight: bold;
        transition: 0.3s;
    }
    
    .stButton>button:hover {
        background-color: #cc3700;
    }
</style>
""", unsafe_allow_html=True)

# Main Header
st.markdown("<h1><span class='highlight'>FIRE-OPS</span> Command Center</h1>", unsafe_allow_html=True)
st.markdown("Advanced Threat Detection & Autonomous Drone Reconnaissance", unsafe_allow_html=True)
st.markdown("---")

# Metrics Dashboard
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown("<div class='metric-container'><h3>Threat Level</h3><h2 class='highlight'>CRITICAL</h2></div>", unsafe_allow_html=True)
with col2:
    st.markdown("<div class='metric-container'><h3>Active Hotspots</h3><h2>14</h2></div>", unsafe_allow_html=True)
with col3:
    st.markdown("<div class='metric-container'><h3>Drones Deployed</h3><h2>3</h2></div>", unsafe_allow_html=True)
with col4:
    st.markdown("<div class='metric-container'><h3>Wind Speed</h3><h2>24 km/h NE</h2></div>", unsafe_allow_html=True)

st.markdown("<br><br>", unsafe_allow_html=True)

# Drone Simulation Module Integration[cite: 1]
st.markdown("<h2>Live <span class='highlight'>Drone Simulator</span> Telemetry</h2>", unsafe_allow_html=True)

# Synthetic data generation for drone_simulator.py equivalent[cite: 1]
grid_size = 50
x_grid, y_grid = np.meshgrid(np.linspace(0, 100, grid_size), np.linspace(0, 100, grid_size))
# Generate a heat map representing fire threat
fire_intensity = 20 + 80 * np.exp(-((x_grid - 60)**2 + (y_grid - 50)**2) / 200)

# Drone flight path calculation
t = np.linspace(0, 4 * np.pi, 150)
drone_x = 60 + 30 * np.cos(t)
drone_y = 50 + 30 * np.sin(t)

# Visualizing the simulation
fig = go.Figure()

# Heatmap Layer
fig.add_trace(go.Heatmap(
    z=fire_intensity,
    x=np.linspace(0, 100, grid_size),
    y=np.linspace(0, 100, grid_size),
    colorscale=[
        [0.0, '#050505'],
        [0.4, '#330000'],
        [0.7, '#FF4500'],
        [1.0, '#FFD700']
    ],
    showscale=False,
    name="Thermal Data"
))

# Drone Trajectory Layer
fig.add_trace(go.Scatter(
    x=drone_x,
    y=drone_y,
    mode='lines+markers',
    name='UAV Path',
    line=dict(color='#FFFFFF', width=2, dash='dot'),
    marker=dict(size=4, color='#FF4500')
))

# Current Drone Position
fig.add_trace(go.Scatter(
    x=[drone_x[-1]],
    y=[drone_y[-1]],
    mode='markers+text',
    name='Active Drone',
    marker=dict(symbol='cross', size=14, color='#FFFFFF'),
    text=["UAV-01"],
    textposition="top right",
    textfont=dict(color="#FF4500", size=14, family="Inter")
))

fig.update_layout(
    paper_bgcolor='#111111',
    plot_bgcolor='#111111',
    margin=dict(l=0, r=0, t=0, b=0),
    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    height=500
)

st.plotly_chart(fig, use_container_width=True)

# Control Panel based on requirements.txt and config environments[cite: 1]
st.markdown("### Tactical Operations")
c1, c2 = st.columns(2)
with c1:
    st.button("Deploy Backup Drones")
with c2:
    st.button("Initiate Suppression Protocol")