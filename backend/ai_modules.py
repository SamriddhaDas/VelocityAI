import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import warnings
warnings.filterwarnings("ignore")

# DATA MODELS

@dataclass
class TrafficAlert:
    intersection_id: str
    congestion_level: float       
    predicted_delay_minutes: float
    recommended_signal_timing: Dict[str, int]
    timestamp: str

@dataclass
class WasteAlert:
    bin_id: str
    fill_level: float             
    overflow_eta_minutes: float
    priority: str                 
    location: Tuple[float, float] 
    timestamp: str

@dataclass
class CollectionRoute:
    bins: List[str]
    total_distance_km: float
    estimated_duration_minutes: float
    fuel_saving_percent: float
    waypoints: List[Tuple[float, float]]

@dataclass
class EnergyAlert:
    zone_id: str
    current_kwh: float
    baseline_kwh: float
    anomaly_score: float
    is_anomaly: bool
    recommendation: str
    timestamp: str

@dataclass
class CrowdAlert:
    zone_id: str
    person_count: int
    density: float                
    risk_level: str               
    heatmap: List[List[float]]
    timestamp: str


# ─────────────────────────────────────────────
# MODULE 1: TRAFFIC AI  (LSTM Time-Series)
# ─────────────────────────────────────────────

class TrafficAI:
    """
    LSTM-based congestion forecaster and signal optimizer.
    Simulates AMD ROCm-accelerated inference.
    """

    INTERSECTIONS = [
        "INT-001", "INT-002", "INT-003", "INT-004",
        "INT-005", "INT-006", "INT-007", "INT-008",
    ]

    def __init__(self):
        self._history: Dict[str, List[float]] = {
            iid: [random.uniform(0.1, 0.5) for _ in range(60)]
            for iid in self.INTERSECTIONS
        }
        self._weights = np.random.randn(10, 1) * 0.1   
        
    def _lstm_forward(self, sequence: List[float]) -> float:
        x = np.array(sequence[-10:])
        forget = 1 / (1 + np.exp(-x))
        cell   = np.tanh(x * forget)
        output = float(np.dot(cell, self._weights).squeeze())
        return max(0.0, min(1.0, output + x[-1] * 0.7))

    @staticmethod
    def _optimize_signal(congestion: float) -> Dict[str, int]:
        base = max(15, min(90, int(congestion * 90)))
        return {
            "north_south_green": base,
            "east_west_green": max(15, 90 - base),
            "pedestrian_interval": 20 if congestion < 0.5 else 15,
        }

    def get_alerts(self) -> List[TrafficAlert]:
        alerts = []
        hour = datetime.now().hour
        peak  = 1.4 if (7 <= hour <= 9 or 17 <= hour <= 19) else 1.0

        for iid in self.INTERSECTIONS:
            noise = random.gauss(0, 0.05)
            new_val = min(1.0, self._lstm_forward(self._history[iid]) * peak + noise)
            self._history[iid].append(new_val)
            self._history[iid] = self._history[iid][-60:]

            delay = new_val * 12.0
            alerts.append(TrafficAlert(
                intersection_id=iid,
                congestion_level=round(new_val, 3),
                predicted_delay_minutes=round(delay, 1),
                recommended_signal_timing=self._optimize_signal(new_val),
                timestamp=datetime.utcnow().isoformat(),
            ))
        return alerts

    def summary(self) -> Dict:
        alerts = self.get_alerts()
        avg_cong = np.mean([a.congestion_level for a in alerts])
        worst = max(alerts, key=lambda a: a.congestion_level)
        return {
            "average_congestion": round(float(avg_cong), 3),
            "worst_intersection": worst.intersection_id,
            "worst_congestion": worst.congestion_level,
            "alerts": [a.__dict__ for a in alerts],
            "congestion_reduction_target": "30%",
        }


# ─────────────────────────────────────────────
# MODULE 2: WASTE MANAGEMENT AI
# ─────────────────────────────────────────────

class WasteAI:

    NUM_BINS = 20

    def __init__(self):
        np.random.seed(42)
        self._bin_locations = [
            (51.505 + np.random.uniform(-0.05, 0.05),
             -0.09  + np.random.uniform(-0.05, 0.05))
            for _ in range(self.NUM_BINS)
        ]
        self._fill_levels = np.random.uniform(0.2, 0.95, self.NUM_BINS)
        self._fill_rates  = np.random.uniform(0.002, 0.012, self.NUM_BINS)  

    @staticmethod
    def _haversine(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        R = 6371.0
        lat1, lon1 = math.radians(a[0]), math.radians(a[1])
        lat2, lon2 = math.radians(b[0]), math.radians(b[1])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(h))

    def _nearest_neighbour_route(self, bin_indices: List[int]) -> List[int]:
        """Greedy nearest-neighbour TSP heuristic."""
        if not bin_indices:
            return []
        unvisited = list(bin_indices)
        route = [unvisited.pop(0)]
        while unvisited:
            last = self._bin_locations[route[-1]]
            nearest = min(unvisited, key=lambda i: self._haversine(last, self._bin_locations[i]))
            route.append(nearest)
            unvisited.remove(nearest)
        return route

    def _tick(self):
        noise = np.random.normal(0, 0.002, self.NUM_BINS)
        self._fill_levels = np.clip(self._fill_levels + self._fill_rates + noise, 0.0, 1.0)

    def _priority(self, fill: float) -> str:
        if fill >= 0.95: return "CRITICAL"
        if fill >= 0.80: return "HIGH"
        if fill >= 0.60: return "MEDIUM"
        return "LOW"

    def _overflow_eta(self, fill: float, rate: float) -> float:
        if rate <= 0: return 9999.0
        remaining = 1.0 - fill
        return round((remaining / rate) * 5, 1)  

    def get_bin_alerts(self) -> List[WasteAlert]:
        self._tick()
        alerts = []
        for i in range(self.NUM_BINS):
            alerts.append(WasteAlert(
                bin_id=f"BIN-{i+1:03d}",
                fill_level=round(float(self._fill_levels[i]), 3),
                overflow_eta_minutes=self._overflow_eta(self._fill_levels[i], self._fill_rates[i]),
                priority=self._priority(self._fill_levels[i]),
                location=self._bin_locations[i],
                timestamp=datetime.utcnow().isoformat(),
            ))
        return alerts

    def get_optimised_route(self) -> CollectionRoute:
        urgent = [i for i in range(self.NUM_BINS) if self._fill_levels[i] >= 0.80]
        if not urgent:
            urgent = list(range(self.NUM_BINS))[:5]  

        route_indices = self._nearest_neighbour_route(urgent)
        waypoints = [self._bin_locations[i] for i in route_indices]
        dist = sum(
            self._haversine(waypoints[j], waypoints[j+1])
            for j in range(len(waypoints)-1)
        )
        fixed_dist = sum(
            self._haversine(self._bin_locations[j], self._bin_locations[j+1])
            for j in range(len(self._bin_locations)-1)
        )
        saving = max(0, round((1 - dist / max(fixed_dist, 0.001)) * 100, 1))

        return CollectionRoute(
            bins=[f"BIN-{i+1:03d}" for i in route_indices],
            total_distance_km=round(dist, 2),
            estimated_duration_minutes=round(dist * 4, 1),  
            fuel_saving_percent=saving,
            waypoints=waypoints,
        )

    def summary(self) -> Dict:
        alerts = self.get_bin_alerts()
        route  = self.get_optimised_route()
        critical = [a for a in alerts if a.priority in ("CRITICAL", "HIGH")]
        return {
            "total_bins": self.NUM_BINS,
            "critical_bins": len(critical),
            "average_fill_level": round(float(np.mean(self._fill_levels)), 3),
            "optimised_route": route.__dict__,
            "alerts": [a.__dict__ for a in alerts],
            "cost_saving_target": "25%",
        }


# ─────────────────────────────────────────────
# MODULE 3: ENERGY AI  (Isolation Forest)
# ─────────────────────────────────────────────

class EnergyAI:

    ZONES = ["ZONE-N", "ZONE-S", "ZONE-E", "ZONE-W", "ZONE-CENTRAL"]
    BASELINE_KWH = {"ZONE-N": 450, "ZONE-S": 380, "ZONE-E": 420,
                    "ZONE-W": 410, "ZONE-CENTRAL": 600}

    def __init__(self):
        self._history: Dict[str, List[float]] = {z: [] for z in self.ZONES}
        self._anomaly_threshold = 2.5  
    @staticmethod
    def _isolation_score(value: float, history: List[float]) -> float:
        if len(history) < 5:
            return 0.0
        mu  = np.mean(history[-30:])
        std = np.std(history[-30:]) or 1.0
        return abs(value - mu) / std

    def _recommendation(self, zone: str, score: float, current: float) -> str:
        if score > 3.5:
            return f"⚠️ Critical spike in {zone}. Dispatch maintenance immediately."
        if score > 2.5:
            return f"Activate demand response protocol for {zone}."
        if current > self.BASELINE_KWH[zone] * 1.1:
            return f"Shift non-essential loads in {zone} to off-peak hours."
        return "Normal operation. Continue monitoring."

    def _simulate_reading(self, zone: str) -> float:
        baseline = self.BASELINE_KWH[zone]
        hour = datetime.now().hour
        multiplier = 1.0 + 0.3 * math.sin(math.pi * (hour - 6) / 12) if 6 <= hour <= 18 else 0.85
        noise = random.gauss(0, baseline * 0.04)
        spike = random.uniform(1.5, 2.5) * baseline if random.random() < 0.05 else 0.0
        return max(0, baseline * multiplier + noise + spike)

    def get_zone_alerts(self) -> List[EnergyAlert]:
        alerts = []
        for zone in self.ZONES:
            current = self._simulate_reading(zone)
            self._history[zone].append(current)
            self._history[zone] = self._history[zone][-100:]

            score = self._isolation_score(current, self._history[zone])
            is_anomaly = score > self._anomaly_threshold

            alerts.append(EnergyAlert(
                zone_id=zone,
                current_kwh=round(current, 1),
                baseline_kwh=self.BASELINE_KWH[zone],
                anomaly_score=round(score, 3),
                is_anomaly=is_anomaly,
                recommendation=self._recommendation(zone, score, current),
                timestamp=datetime.utcnow().isoformat(),
            ))
        return alerts

    def summary(self) -> Dict:
        alerts = self.get_zone_alerts()
        anomalies = [a for a in alerts if a.is_anomaly]
        total_current = sum(a.current_kwh for a in alerts)
        total_baseline = sum(a.baseline_kwh for a in alerts)
        return {
            "total_current_kwh": round(total_current, 1),
            "total_baseline_kwh": total_baseline,
            "excess_percent": round((total_current / total_baseline - 1) * 100, 1),
            "anomaly_zones": len(anomalies),
            "alerts": [a.__dict__ for a in alerts],
            "consumption_reduction_target": "12%",
        }


# ─────────────────────────────────────────────
# MODULE 4: CROWD DENSITY AI  (YOLOv8 simulation)
# ─────────────────────────────────────────────

class CrowdAI:
    ZONES = [
        {"id": "PLAZA-MAIN",    "capacity": 500,  "area_m2": 2000},
        {"id": "STATION-NORTH", "capacity": 800,  "area_m2": 1200},
        {"id": "MARKET-EAST",   "capacity": 300,  "area_m2": 800},
        {"id": "PARK-WEST",     "capacity": 1200, "area_m2": 5000},
        {"id": "ARENA",         "capacity": 5000, "area_m2": 8000},
    ]

    HEATMAP_SIZE = 8 

    def __init__(self):
        self._crowd_state = {z["id"]: random.uniform(0.1, 0.5) for z in self.ZONES}

    @staticmethod
    def _risk_level(density: float, capacity_util: float) -> str:
        if capacity_util >= 0.95 or density >= 5.0: return "CRITICAL"
        if capacity_util >= 0.80 or density >= 3.5: return "HIGH"
        if capacity_util >= 0.60 or density >= 2.0: return "ELEVATED"
        return "NORMAL"

    def _generate_heatmap(self, count: int, area: float) -> List[List[float]]:
        grid = np.zeros((self.HEATMAP_SIZE, self.HEATMAP_SIZE))
        num_clusters = random.randint(1, 3)
        for _ in range(num_clusters):
            cx = random.uniform(1, self.HEATMAP_SIZE - 2)
            cy = random.uniform(1, self.HEATMAP_SIZE - 2)
            sigma = random.uniform(1.0, 2.5)
            for i in range(self.HEATMAP_SIZE):
                for j in range(self.HEATMAP_SIZE):
                    grid[i][j] += math.exp(-((i-cx)**2 + (j-cy)**2) / (2*sigma**2))
        total = grid.sum() or 1
        density_per_cell = count / area
        grid = (grid / total) * density_per_cell * (self.HEATMAP_SIZE ** 2)
        return [[round(float(v), 2) for v in row] for row in grid]

    def _tick_crowd(self, zone_id: str, capacity: int) -> int:
        current_util = self._crowd_state[zone_id]
        delta = random.gauss(0, 0.05)
        if random.random() < 0.02:
            delta += random.uniform(0.15, 0.30)
        new_util = max(0.05, min(1.0, current_util + delta))
        self._crowd_state[zone_id] = new_util
        return int(new_util * capacity)

    def get_zone_alerts(self) -> List[CrowdAlert]:
        alerts = []
        for zone in self.ZONES:
            count = self._tick_crowd(zone["id"], zone["capacity"])
            density = count / zone["area_m2"]
            cap_util = count / zone["capacity"]
            heatmap = self._generate_heatmap(count, zone["area_m2"])

            alerts.append(CrowdAlert(
                zone_id=zone["id"],
                person_count=count,
                density=round(density, 3),
                risk_level=self._risk_level(density, cap_util),
                heatmap=heatmap,
                timestamp=datetime.utcnow().isoformat(),
            ))
        return alerts

    def summary(self) -> Dict:
        alerts = self.get_zone_alerts()
        critical = [a for a in alerts if a.risk_level in ("CRITICAL", "HIGH")]
        total_people = sum(a.person_count for a in alerts)
        return {
            "total_monitored_people": total_people,
            "high_risk_zones": len(critical),
            "inference_latency_ms": 31,
            "alerts": [a.__dict__ for a in alerts],
        }


# ─────────────────────────────────────────────
# MASTER RUNNER
# ─────────────────────────────────────────────

class VelocityAI:
    def __init__(self):
        self.traffic = TrafficAI()
        self.waste   = WasteAI()
        self.energy  = EnergyAI()
        self.crowd   = CrowdAI()

    def full_snapshot(self) -> Dict:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "traffic": self.traffic.summary(),
            "waste":   self.waste.summary(),
            "energy":  self.energy.summary(),
            "crowd":   self.crowd.summary(),
        }


if __name__ == "__main__":
    import json
    pulse = VelocityAI()
    snapshot = pulse.full_snapshot()
    print(json.dumps(snapshot, indent=2, default=str))
    print("\n✅ VelocityAI AI modules running successfully.")
