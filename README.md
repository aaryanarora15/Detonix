Detonix — Fire Hazard & Drone Operations Center

Team Purple Haze — Hacktronics 2026 (Edition 2)

A real-time fire hazard simulation and tactical operations dashboard. Detonix models how a fire spreads and behaves based on fuel type and environmental conditions, fuses live (simulated) drone telemetry and weather data, and renders hazard zones on an interactive map for emergency-response planning.

Features
🔥 Fire hazard modeling — simulates heat release rate, flame temperature, spread rate, and smoke/soot/CO generation for different fuel types (petrol, diesel, LPG, hydrogen, wood, etc.)
🛰️ Drone telemetry fusion — ingests simulated drone GPS, orbit position, and wind-sensor data to cross-check the fire's location and drift
🌬️ Weather-aware forecasting — factors in live wind speed/direction and projects a 5-minute-ahead hazard plume shift
🗺️ Interactive hazard map — Leaflet-based dashboard showing color-coded safety zones (safe boundary, ignition zone, lethal core) and forecasted plume drift as GeoJSON overlays
💥 BLEVE blast modeling — optional shockwave/overpressure radius simulation for tank/vessel explosion scenarios
📡 Live dashboard — auto-refreshing stats (burn rate, soot, CO output) and a "propagation engine" timeline scrubber
Requirements
Python 3.9+
Flask, NumPy, Requests (see requirements.txt)
Setup
bash
git clone https://github.com/<your-username>/detonix.git
cd detonix
pip install -r requirements.txt
python app.py

Then open http://localhost:5000 in your browser.

Project Structure
detonix/
├── app.py                # Flask backend: fire physics model, drone sim, API endpoints
├── templates/
│   └── index.html        # Operations Center dashboard (Leaflet map + live stats)
├── requirements.txt
└── README.md
How It Works
Pick a fuel type and set fire parameters (fuel mass, burning area, wind, confinement) from the dashboard.
The backend runs a physics-based fire model (simulate_fire) each tick to compute heat release rate, spread rate, and hazard indices.
A background thread simulates a drone orbiting the incident site, streaming mock GPS/wind telemetry.
The frontend polls the API and renders wind-distorted hazard contours (green/yellow/red zones) plus a 5-minute forecast shift on the map.
Note

This is a simulation/visualization tool built for a hackathon demo — the fire and drone data are modeled/synthetic, not connected to real sensors. It's intended for tactical training, planning demos, and educational use around fire dynamics and disaster response, not for real-world emergency decision-making without validation from qualified fire-safety professionals.
