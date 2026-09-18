"""
drone_simulator.py
Beginner-friendly mock drone telemetry generator for hazard-mapping hackathon demo.
Simulates a circular orbit flight, ground-truth wind, and realistically noisy
IMU/GPS/anemometer readings — so the sensor-fusion pipeline has something to prove
itself against.
"""

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------
# 1. SCENARIO CONFIG
# ----------------------------------------------------------------------------
HAZARD_CENTER = np.array([0.0, 0.0])   # local ENU meters, hazard site at origin
ORBIT_RADIUS_M = 150.0                  # standoff distance for the orbit
ORBIT_ALTITUDE_M = 60.0
ORBIT_PERIOD_S = 90.0                   # one full lap
SIM_DURATION_S = 270.0                  # three laps
DT = 0.5                                # telemetry sample interval (s)

TRUE_WIND_MEAN = np.array([4.0, 1.5])   # steady wind, m/s, Earth-frame (Wx, Wy)
GUST_AMPLITUDE = 1.2                    # m/s
GUST_FREQS_HZ = [0.05, 0.13, 0.31]      # a few superposed gust frequencies

THERMAL_UPDRAFT_PEAK = 3.5              # m/s, vertical, strongest near the hazard
THERMAL_UPDRAFT_DECAY_M = 80.0          # e-folding distance of the plume influence

# Sensor noise standard deviations (physically-motivated, tune as needed)
GPS_POS_NOISE_M = 0.8
IMU_ANGLE_NOISE_RAD = np.deg2rad(0.6)
ANEMOMETER_NOISE_MS = 0.35

rng = np.random.default_rng(seed=42)


# ----------------------------------------------------------------------------
# 2. GROUND-TRUTH WIND FIELD (what we're TRYING to recover downstream)
# ----------------------------------------------------------------------------
def true_wind_at(t: float, pos_xy: np.ndarray) -> np.ndarray:
    """Returns true 3D wind vector (Wx, Wy, Wz) in Earth (ENU) frame at time t
    and horizontal position pos_xy. Includes steady wind + multi-frequency gusts
    + a hazard-centered thermal updraft in the vertical channel."""
    gust = sum(
        GUST_AMPLITUDE * np.sin(2 * np.pi * f * t + phase)
        for f, phase in zip(GUST_FREQS_HZ, [0.0, 1.7, 3.4])
    )
    horizontal = TRUE_WIND_MEAN + gust * np.array([1.0, 0.6])  # gust mostly along-mean

    dist_to_hazard = np.linalg.norm(pos_xy - HAZARD_CENTER)
    updraft = THERMAL_UPDRAFT_PEAK * np.exp(-dist_to_hazard / THERMAL_UPDRAFT_DECAY_M)

    return np.array([horizontal[0], horizontal[1], updraft])


# ----------------------------------------------------------------------------
# 3. ROTATION MATRICES (mirrors Phase 2 math — Body <-> Earth/NED-style, here ENU)
# ----------------------------------------------------------------------------
def body_to_earth(phi, theta, psi):
    """DCM: rotates a vector FROM body frame TO earth frame (ZYX Euler convention)."""
    cphi, sphi = np.cos(phi), np.sin(phi)
    cth, sth = np.cos(theta), np.sin(theta)
    cpsi, spsi = np.cos(psi), np.sin(psi)

    R = np.array([
        [cth * cpsi, sphi * sth * cpsi - cphi * spsi, cphi * sth * cpsi + sphi * spsi],
        [cth * spsi, sphi * sth * spsi + cphi * cpsi, cphi * sth * spsi - sphi * cpsi],
        [-sth,       sphi * cth,                       cphi * cth],
    ])
    return R


# ----------------------------------------------------------------------------
# 4. FLIGHT PATH + ATTITUDE (circular orbit, physically-derived bank/pitch)
# ----------------------------------------------------------------------------
def orbit_state(t: float):
    omega = 2 * np.pi / ORBIT_PERIOD_S
    alpha = omega * t

    pos = HAZARD_CENTER + ORBIT_RADIUS_M * np.array([np.cos(alpha), np.sin(alpha)])
    pos_3d = np.array([pos[0], pos[1], ORBIT_ALTITUDE_M])

    speed = omega * ORBIT_RADIUS_M                      # tangential ground speed
    heading = alpha + np.pi / 2                          # velocity direction (tangent)
    vel = speed * np.array([np.cos(heading), np.sin(heading), 0.0])

    # Physically-derived attitude: bank angle from centripetal accel,
    # small forward pitch proportional to speed (simple, not aero-exact, but consistent).
    centripetal_accel = speed ** 2 / ORBIT_RADIUS_M
    g = 9.81
    roll = np.arctan2(centripetal_accel, g)              # bank into the turn
    pitch = -0.03 * speed                                 # nose-down-ish for fwd flight
    yaw = heading

    return pos_3d, vel, roll, pitch, yaw


# ----------------------------------------------------------------------------
# 5. MAIN SIMULATION LOOP
# ----------------------------------------------------------------------------
def simulate():
    rows = []
    t = 0.0
    while t <= SIM_DURATION_S:
        pos_3d, vel_earth, roll, pitch, yaw = orbit_state(t)

        w_true = true_wind_at(t, pos_3d[:2])              # Earth-frame true wind

        # Apparent wind (Earth frame) = true wind - drone velocity
        w_apparent_earth = w_true - vel_earth

        # Rotate INTO body frame (what the anemometer actually feels):
        # body_to_earth is Body->Earth, so Earth->Body is its transpose.
        R_be = body_to_earth(roll, pitch, yaw)
        w_apparent_body = R_be.T @ w_apparent_earth

        # ---- Inject sensor noise ----
        gps_noisy = pos_3d + rng.normal(0, GPS_POS_NOISE_M, size=3)
        roll_noisy = roll + rng.normal(0, IMU_ANGLE_NOISE_RAD)
        pitch_noisy = pitch + rng.normal(0, IMU_ANGLE_NOISE_RAD)
        yaw_noisy = yaw + rng.normal(0, IMU_ANGLE_NOISE_RAD)
        anemo_noisy = w_apparent_body + rng.normal(0, ANEMOMETER_NOISE_MS, size=3)
        speed_noisy = np.linalg.norm(vel_earth[:2]) + rng.normal(0, 0.15)

        rows.append({
            "t_s": t,
            "gps_x_m": gps_noisy[0], "gps_y_m": gps_noisy[1], "gps_alt_m": gps_noisy[2],
            "ground_speed_ms": speed_noisy,
            "roll_rad": roll_noisy, "pitch_rad": pitch_noisy, "yaw_rad": yaw_noisy,
            "anemo_body_x_ms": anemo_noisy[0],
            "anemo_body_y_ms": anemo_noisy[1],
            "anemo_body_z_ms": anemo_noisy[2],
            # Ground-truth columns kept ONLY for validating the recovery pipeline —
            # a real drone would never have these; strip before "live" demo mode.
            "_true_wind_x": w_true[0], "_true_wind_y": w_true[1], "_true_wind_z": w_true[2],
        })
        t += DT

    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = simulate()
    df.to_csv("mock_drone_telemetry.csv", index=False)
    print(f"Generated {len(df)} telemetry samples -> mock_drone_telemetry.csv")
    print(df.head())
            