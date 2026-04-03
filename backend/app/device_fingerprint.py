"""
Device Fingerprinting — Detect impossible travel, SIM swaps, and device anomalies.
"""

import math
from datetime import datetime, timedelta


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two GPS coordinates in kilometers."""
    R = 6371  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def check_impossible_travel(
    current_lat: float,
    current_lon: float,
    current_time: datetime,
    last_lat: float,
    last_lon: float,
    last_time: datetime,
    max_speed_kmh: float = 900,  # Max commercial flight speed
) -> dict:
    """
    Detect if a user could physically travel between two locations in the given time.
    Returns anomaly details.
    """
    distance_km = haversine_km(last_lat, last_lon, current_lat, current_lon)
    time_diff = (current_time - last_time).total_seconds() / 3600  # hours

    if time_diff <= 0:
        time_diff = 0.001  # Avoid division by zero

    required_speed = distance_km / time_diff

    is_impossible = required_speed > max_speed_kmh

    return {
        "is_impossible_travel": is_impossible,
        "distance_km": round(distance_km, 1),
        "time_hours": round(time_diff, 2),
        "required_speed_kmh": round(required_speed, 0),
        "max_speed_kmh": max_speed_kmh,
        "risk_label": "IMPOSSIBLE_TRAVEL" if is_impossible else "OK",
    }


def check_device_anomalies(txn: dict, sender_history: dict) -> list[dict]:
    """
    Analyze device-related anomalies for a transaction.
    Returns a list of detected anomalies.
    """
    anomalies = []
    sender = txn.get("sender_upi", "")

    if sender not in sender_history:
        return anomalies

    hist = sender_history[sender]

    # 1. New device detection (already in features, but add detail)
    device = txn.get("sender_device_id", "")
    if device and device not in hist.get("devices", set()):
        anomalies.append({
            "type": "NEW_DEVICE",
            "severity": "MEDIUM",
            "detail": f"First time seeing device {device} for {sender}",
            "known_devices": len(hist.get("devices", set())),
        })

    # 2. IP address change (different subnet)
    current_ip = txn.get("sender_ip", "")
    if current_ip and hist.get("last_ip"):
        current_subnet = ".".join(current_ip.split(".")[:2])
        last_subnet = ".".join(hist["last_ip"].split(".")[:2])
        if current_subnet != last_subnet:
            anomalies.append({
                "type": "IP_SUBNET_CHANGE",
                "severity": "LOW",
                "detail": f"IP changed from {last_subnet}.*.* to {current_subnet}.*.*",
            })

    # 3. Impossible travel (if GPS data available)
    current_lat = txn.get("sender_location_lat")
    current_lon = txn.get("sender_location_lon")
    if current_lat and current_lon and hist.get("last_location"):
        last_loc = hist["last_location"]
        last_time = hist.get("last_timestamp")
        if last_time:
            try:
                current_time = datetime.fromisoformat(txn.get("timestamp", datetime.now().isoformat()))
                if isinstance(last_time, str):
                    last_time = datetime.fromisoformat(last_time)
                travel = check_impossible_travel(
                    current_lat, current_lon, current_time,
                    last_loc["lat"], last_loc["lon"], last_time
                )
                if travel["is_impossible_travel"]:
                    anomalies.append({
                        "type": "IMPOSSIBLE_TRAVEL",
                        "severity": "HIGH",
                        "detail": f"{travel['distance_km']}km in {travel['time_hours']}h "
                                  f"(requires {travel['required_speed_kmh']}km/h)",
                    })
            except (ValueError, TypeError):
                pass

    return anomalies


def update_device_history(txn: dict, sender_history: dict):
    """Update sender history with device/location info for future checks."""
    sender = txn.get("sender_upi", "")
    if sender not in sender_history:
        return

    hist = sender_history[sender]
    hist["last_ip"] = txn.get("sender_ip", "")

    lat = txn.get("sender_location_lat")
    lon = txn.get("sender_location_lon")
    if lat and lon:
        hist["last_location"] = {"lat": lat, "lon": lon}

    try:
        hist["last_timestamp"] = txn.get("timestamp", datetime.now().isoformat())
    except (ValueError, TypeError):
        pass
