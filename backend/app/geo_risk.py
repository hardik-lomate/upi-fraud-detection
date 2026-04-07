"""
Geolocation Risk Scoring — Coordinate-based risk analysis for India.

Uses lat/lon fields to add city-level risk scoring without requiring
MaxMind GeoLite2 database. Flags VPN-like patterns and impossible travel.
"""

import math
from typing import Optional

# High-fraud-rate cities/regions (based on public NPCI fraud report data)
HIGH_FRAUD_REGIONS = [
    {"name": "Delhi NCR", "lat": 28.6139, "lon": 77.2090, "radius_km": 50, "risk_multiplier": 1.3},
    {"name": "Mumbai", "lat": 19.0760, "lon": 72.8777, "radius_km": 40, "risk_multiplier": 1.2},
    {"name": "Hyderabad", "lat": 17.3850, "lon": 78.4867, "radius_km": 35, "risk_multiplier": 1.15},
    {"name": "Kolkata", "lat": 22.5726, "lon": 88.3639, "radius_km": 30, "risk_multiplier": 1.1},
    {"name": "Jharkhand", "lat": 23.6102, "lon": 85.2799, "radius_km": 80, "risk_multiplier": 1.4},
    {"name": "Rajasthan (Bharatpur)", "lat": 27.2152, "lon": 77.4890, "radius_km": 40, "risk_multiplier": 1.35},
]

# India bounding box
INDIA_LAT_MIN, INDIA_LAT_MAX = 6.5, 37.5
INDIA_LON_MIN, INDIA_LON_MAX = 68.0, 97.5

# Speed thresholds for impossible travel (km/h)
MAX_PLAUSIBLE_SPEED_KMH = 900  # Max flight speed
SUSPICIOUS_SPEED_KMH = 500  # Flagged but not impossible


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in km using Haversine formula."""
    R = 6371  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def score_location(lat: Optional[float], lon: Optional[float]) -> dict:
    """Score a transaction location for fraud risk."""
    if lat is None or lon is None:
        return {
            "risk_score": 0.0,
            "risk_level": "UNKNOWN",
            "region": "Unknown",
            "flags": [],
        }

    flags = []
    risk_score = 0.0

    # Check if outside India bounds
    if not (INDIA_LAT_MIN <= lat <= INDIA_LAT_MAX and INDIA_LON_MIN <= lon <= INDIA_LON_MAX):
        risk_score += 0.3
        flags.append({
            "type": "OUTSIDE_INDIA",
            "severity": "HIGH",
            "detail": f"Location ({lat:.2f}, {lon:.2f}) is outside India bounds",
        })

    # Check high-fraud regions
    nearest_region = None
    min_distance = float("inf")

    for region in HIGH_FRAUD_REGIONS:
        dist = haversine_km(lat, lon, region["lat"], region["lon"])
        if dist < min_distance:
            min_distance = dist
            nearest_region = region

        if dist <= region["radius_km"]:
            risk_adjustment = (region["risk_multiplier"] - 1.0) * 0.5
            risk_score += risk_adjustment
            flags.append({
                "type": "HIGH_FRAUD_REGION",
                "severity": "MEDIUM",
                "detail": f"Transaction from {region['name']} (fraud multiplier: {region['risk_multiplier']}x)",
            })

    # Check for coordinate anomalies (0,0 or perfectly round numbers suggesting spoofing)
    if abs(lat) < 0.01 and abs(lon) < 0.01:
        risk_score += 0.4
        flags.append({
            "type": "NULL_ISLAND",
            "severity": "HIGH",
            "detail": "Coordinates (0,0) suggest GPS spoofing or missing data",
        })

    if lat == round(lat) and lon == round(lon):
        risk_score += 0.1
        flags.append({
            "type": "ROUND_COORDINATES",
            "severity": "LOW",
            "detail": "Perfectly round coordinates may indicate approximate/spoofed location",
        })

    risk_score = min(risk_score, 1.0)

    return {
        "risk_score": round(risk_score, 3),
        "risk_level": "HIGH" if risk_score >= 0.4 else ("MEDIUM" if risk_score >= 0.15 else "LOW"),
        "region": nearest_region["name"] if nearest_region else "Unknown",
        "nearest_region_km": round(min_distance, 1) if nearest_region else None,
        "coordinates": {"lat": lat, "lon": lon},
        "flags": flags,
    }


def check_impossible_travel(
    lat1: float, lon1: float, time1_iso: str,
    lat2: float, lon2: float, time2_iso: str,
) -> dict:
    """Check for impossible travel between two transaction locations."""
    from datetime import datetime

    try:
        t1 = datetime.fromisoformat(time1_iso.replace("Z", "+00:00"))
        t2 = datetime.fromisoformat(time2_iso.replace("Z", "+00:00"))
    except Exception:
        return {"is_impossible": False, "speed_kmh": 0, "distance_km": 0}

    distance = haversine_km(lat1, lon1, lat2, lon2)
    time_diff_hours = abs((t2 - t1).total_seconds()) / 3600

    if time_diff_hours < 0.001:
        speed = float("inf") if distance > 1 else 0
    else:
        speed = distance / time_diff_hours

    is_impossible = speed > MAX_PLAUSIBLE_SPEED_KMH and distance > 50
    is_suspicious = speed > SUSPICIOUS_SPEED_KMH and distance > 50

    return {
        "is_impossible": is_impossible,
        "is_suspicious": is_suspicious,
        "speed_kmh": round(speed, 1),
        "distance_km": round(distance, 1),
        "time_diff_minutes": round(time_diff_hours * 60, 1),
        "detail": (
            f"Traveled {distance:.0f}km in {time_diff_hours * 60:.0f}min ({speed:.0f}km/h)"
            if is_suspicious else ""
        ),
    }


def calculate_travel_impossibility(lat1, lon1, ts1, lat2, lon2, ts2) -> dict:
    """
    Compute distance/speed based travel impossibility as a reusable first-class feature.
    Returns a normalized verdict payload consumed by serving features and rules.
    """
    try:
        result = check_impossible_travel(
            float(lat1), float(lon1), str(ts1),
            float(lat2), float(lon2), str(ts2),
        )
    except Exception:
        return {
            "is_impossible": False,
            "distance_km": 0.0,
            "required_speed_kmh": 0.0,
            "time_diff_minutes": -1.0,
            "verdict_reason": "Travel check unavailable",
        }

    impossible = bool(result.get("is_impossible", False))
    suspicious = bool(result.get("is_suspicious", False))
    distance_km = float(result.get("distance_km", 0.0))
    speed_kmh = float(result.get("speed_kmh", 0.0))
    time_diff_minutes = float(result.get("time_diff_minutes", -1.0))

    if impossible:
        verdict_reason = (
            f"Location jump of {distance_km:.1f}km in {time_diff_minutes:.1f} minutes is physically impossible"
        )
    elif suspicious:
        verdict_reason = (
            f"Rapid travel detected: {distance_km:.1f}km in {time_diff_minutes:.1f} minutes"
        )
    else:
        verdict_reason = "Location change is plausible"

    return {
        "is_impossible": impossible,
        "distance_km": distance_km,
        "required_speed_kmh": speed_kmh,
        "time_diff_minutes": time_diff_minutes,
        "verdict_reason": verdict_reason,
    }
