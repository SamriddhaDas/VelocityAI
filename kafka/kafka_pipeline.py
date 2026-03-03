import json
import time
import random
import os
import threading
from datetime import datetime
from typing import Callable, Dict, Any

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

TOPIC_TRAFFIC = "velocityai.traffic.raw"
TOPIC_WASTE   = "velocityai.waste.raw"
TOPIC_ENERGY  = "velocityai.energy.raw"
TOPIC_CROWD   = "velocityai.crowd.raw"
TOPIC_ENRICHED = "velocityai.enriched"

# ─────────────────────────────────────────────
# KAFKA CLIENT WRAPPER (with graceful fallback)
# ─────────────────────────────────────────────

class KafkaClientWrapper:

    def __init__(self):
        self._available = False
        self._producer = None
        self._try_connect()

    def _try_connect(self):
        try:
            from kafka import KafkaProducer
            self._producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                request_timeout_ms=3000,
            )
            self._available = True
            print(f"✅ Kafka connected: {KAFKA_BOOTSTRAP}")
        except Exception as e:
            print(f"⚠️  Kafka unavailable ({e}). Running in no-op mode.")

    def send(self, topic: str, payload: Dict):
        if self._available and self._producer:
            try:
                self._producer.send(topic, payload)
            except Exception as e:
                print(f"Kafka send error: {e}")
        else:
            ts = payload.get("timestamp", "?")
            print(f"[KAFKA-NOOP] {topic} | {ts}")

    def close(self):
        if self._producer:
            self._producer.close()


_client = KafkaClientWrapper()


# ─────────────────────────────────────────────
# PRODUCER 1 — Traffic IoT Sensors
# ─────────────────────────────────────────────

def produce_traffic(interval_sec: float = 1.0, run_once: bool = False):
    """Publishes raw traffic sensor readings to Kafka."""
    intersections = [f"INT-{i:03d}" for i in range(1, 9)]
    iteration = 0
    while True:
        for iid in intersections:
            payload = {
                "sensor_type": "traffic",
                "intersection_id": iid,
                "vehicle_count": random.randint(0, 120),
                "avg_speed_kmh": random.uniform(5, 80),
                "occupancy_pct": random.uniform(0, 100),
                "timestamp": datetime.utcnow().isoformat(),
                "iteration": iteration,
            }
            _client.send(TOPIC_TRAFFIC, payload)
        iteration += 1
        if run_once:
            break
        time.sleep(interval_sec)


# ─────────────────────────────────────────────
# PRODUCER 2 — Waste Bin IoT Sensors
# ─────────────────────────────────────────────

def produce_waste(interval_sec: float = 5.0, run_once: bool = False):
    """Publishes raw bin fill-level readings to Kafka."""
    while True:
        for i in range(1, 21):
            payload = {
                "sensor_type": "waste",
                "bin_id": f"BIN-{i:03d}",
                "fill_level_pct": round(random.uniform(10, 100), 1),
                "weight_kg": round(random.uniform(0, 50), 1),
                "temperature_c": round(random.uniform(15, 35), 1),
                "lat": 51.505 + random.uniform(-0.05, 0.05),
                "lon": -0.09  + random.uniform(-0.05, 0.05),
                "timestamp": datetime.utcnow().isoformat(),
            }
            _client.send(TOPIC_WASTE, payload)
        if run_once:
            break
        time.sleep(interval_sec)


# ─────────────────────────────────────────────
# PRODUCER 3 — Energy Meters
# ─────────────────────────────────────────────

def produce_energy(interval_sec: float = 2.0, run_once: bool = False):
    """Publishes raw energy meter readings to Kafka."""
    zones = ["ZONE-N", "ZONE-S", "ZONE-E", "ZONE-W", "ZONE-CENTRAL"]
    while True:
        for zone in zones:
            payload = {
                "sensor_type": "energy",
                "zone_id": zone,
                "current_kwh": round(random.uniform(200, 900), 1),
                "voltage_v": round(random.uniform(220, 240), 1),
                "frequency_hz": round(random.uniform(49.9, 50.1), 2),
                "power_factor": round(random.uniform(0.85, 1.0), 3),
                "timestamp": datetime.utcnow().isoformat(),
            }
            _client.send(TOPIC_ENERGY, payload)
        if run_once:
            break
        time.sleep(interval_sec)


# ─────────────────────────────────────────────
# PRODUCER 4 — Crowd Cameras
# ─────────────────────────────────────────────

def produce_crowd(interval_sec: float = 1.0, run_once: bool = False):
    """Publishes raw crowd camera frames to Kafka (simulated person counts)."""
    zones = ["PLAZA-MAIN", "STATION-NORTH", "MARKET-EAST", "PARK-WEST", "ARENA"]
    while True:
        for zone in zones:
            payload = {
                "sensor_type": "crowd",
                "zone_id": zone,
                "raw_person_count": random.randint(0, 500),
                "camera_id": f"CAM-{zone}-01",
                "frame_id": random.randint(1000, 9999),
                "confidence": round(random.uniform(0.85, 0.99), 3),
                "yolov8_inference_ms": round(random.uniform(28, 35), 1),
                "timestamp": datetime.utcnow().isoformat(),
            }
            _client.send(TOPIC_CROWD, payload)
        if run_once:
            break
        time.sleep(interval_sec)


# ─────────────────────────────────────────────
# CONSUMER — AI Enrichment Pipeline
# ─────────────────────────────────────────────

def ai_enrichment_consumer(handler: Callable[[str, Dict], Any] = None):
    try:
        from kafka import KafkaConsumer, KafkaProducer
        consumer = KafkaConsumer(
            TOPIC_TRAFFIC, TOPIC_WASTE, TOPIC_ENERGY, TOPIC_CROWD,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            group_id="urbanpulse-enrichment",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        )
        print("🔄 AI Enrichment Consumer started — listening on all raw topics")
        for message in consumer:
            raw = message.value
            enriched = _enrich(message.topic, raw)
            producer.send(TOPIC_ENRICHED, enriched)
            if handler:
                handler(message.topic, enriched)

    except ImportError:
        print("kafka-python not installed. Consumer unavailable.")
    except Exception as e:
        print(f"Consumer error: {e}")


def _enrich(topic: str, raw: Dict) -> Dict:
    enriched = dict(raw)
    enriched["enriched_at"] = datetime.utcnow().isoformat()
    enriched["source_topic"] = topic

    if topic == TOPIC_TRAFFIC:
        count = raw.get("vehicle_count", 0)
        speed = raw.get("avg_speed_kmh", 50)
        enriched["congestion_score"] = round(min(1.0, count / 120 * (1 - speed / 80)), 3)
        enriched["alert"] = enriched["congestion_score"] > 0.7

    elif topic == TOPIC_WASTE:
        fill = raw.get("fill_level_pct", 0) / 100
        enriched["overflow_risk"] = fill > 0.85
        enriched["priority"] = "CRITICAL" if fill > 0.95 else "HIGH" if fill > 0.80 else "NORMAL"

    elif topic == TOPIC_ENERGY:
        kwh = raw.get("current_kwh", 0)
        enriched["anomaly_flag"] = kwh > 750
        enriched["excess_kwh"] = max(0, kwh - 500)

    elif topic == TOPIC_CROWD:
        count = raw.get("raw_person_count", 0)
        enriched["density"] = round(count / 500, 3)
        enriched["stampede_risk"] = count > 400

    return enriched


# ─────────────────────────────────────────────
# ORCHESTRATOR — run all producers in threads
# ─────────────────────────────────────────────

def start_all_producers():
    producers = [
        threading.Thread(target=produce_traffic, kwargs={"interval_sec": 1.0},  daemon=True, name="Producer-Traffic"),
        threading.Thread(target=produce_waste,   kwargs={"interval_sec": 5.0},  daemon=True, name="Producer-Waste"),
        threading.Thread(target=produce_energy,  kwargs={"interval_sec": 2.0},  daemon=True, name="Producer-Energy"),
        threading.Thread(target=produce_crowd,   kwargs={"interval_sec": 1.0},  daemon=True, name="Producer-Crowd"),
    ]
    for p in producers:
        p.start()
        print(f"🚀 Started {p.name}")
    return producers


if __name__ == "__main__":
    print("🏭 Starting UrbanPulse Kafka Pipeline")
    threads = start_all_producers()

    consumer_thread = threading.Thread(target=ai_enrichment_consumer, daemon=True, name="AI-Enrichment-Consumer")
    consumer_thread.start()

    print("✅ All producers and enrichment consumer running. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping pipeline...")
        _client.close()
