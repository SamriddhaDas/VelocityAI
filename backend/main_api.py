"""
UrbanPulse FastAPI Backend
9 REST endpoints + 1 WebSocket live stream
Run: uvicorn main_api:app --port 8000 --reload
"""

import asyncio
import json
import sys
import os
from typing import List

# Ensure ai_modules is importable regardless of working directory
sys.path.insert(0, os.path.dirname(__file__))

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:
    print("FastAPI not found. Install: pip install fastapi uvicorn")
    sys.exit(1)

from ai_modules import UrbanPulse

app = FastAPI(
    title="UrbanPulse API",
    description="Real-Time AI Smart City Dashboard — AMD ROCm Powered",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Singleton AI engine ─────────────────────────────────────────────────
pulse = UrbanPulse()

# ── WebSocket connection pool ───────────────────────────────────────────
active_connections: List[WebSocket] = []


# ═══════════════════════════════════════════════════════════════════════
# REST ENDPOINTS  (9 total)
# ═══════════════════════════════════════════════════════════════════════

@app.get("/", tags=["Health"])
async def root():
    """Health check."""
    return {"status": "online", "service": "UrbanPulse AI Dashboard", "version": "1.0.0"}


# ── 1. Full snapshot ────────────────────────────────────────────────────
@app.get("/api/snapshot", tags=["Dashboard"])
async def get_full_snapshot():
    """Returns a full snapshot of all four AI modules."""
    return pulse.full_snapshot()


# ── 2. Traffic summary ──────────────────────────────────────────────────
@app.get("/api/traffic", tags=["Traffic"])
async def get_traffic():
    """Traffic congestion levels and signal recommendations."""
    return pulse.traffic.summary()


# ── 3. Traffic alerts list ──────────────────────────────────────────────
@app.get("/api/traffic/alerts", tags=["Traffic"])
async def get_traffic_alerts():
    """Detailed per-intersection congestion alerts."""
    alerts = pulse.traffic.get_alerts()
    return {"alerts": [a.__dict__ for a in alerts], "count": len(alerts)}


# ── 4. Waste summary ────────────────────────────────────────────────────
@app.get("/api/waste", tags=["Waste"])
async def get_waste():
    """Bin fill levels and optimised collection route."""
    return pulse.waste.summary()


# ── 5. Waste route only ─────────────────────────────────────────────────
@app.get("/api/waste/route", tags=["Waste"])
async def get_waste_route():
    """Haversine-optimised collection route for urgent bins."""
    route = pulse.waste.get_optimised_route()
    return route.__dict__


# ── 6. Energy summary ───────────────────────────────────────────────────
@app.get("/api/energy", tags=["Energy"])
async def get_energy():
    """Energy consumption and anomaly detection results."""
    return pulse.energy.summary()


# ── 7. Energy zone detail ───────────────────────────────────────────────
@app.get("/api/energy/{zone_id}", tags=["Energy"])
async def get_energy_zone(zone_id: str):
    """Isolation Forest anomaly details for a specific zone."""
    alerts = pulse.energy.get_zone_alerts()
    zone = next((a.__dict__ for a in alerts if a.zone_id.upper() == zone_id.upper()), None)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found.")
    return zone


# ── 8. Crowd summary ────────────────────────────────────────────────────
@app.get("/api/crowd", tags=["Crowd"])
async def get_crowd():
    """Crowd density, heatmaps, and stampede risk alerts."""
    return pulse.crowd.summary()


# ── 9. Crowd zone heatmap ───────────────────────────────────────────────
@app.get("/api/crowd/{zone_id}", tags=["Crowd"])
async def get_crowd_zone(zone_id: str):
    """YOLOv8 density heatmap for a specific public zone."""
    alerts = pulse.crowd.get_zone_alerts()
    zone = next((a.__dict__ for a in alerts if a.zone_id.upper() == zone_id.upper()), None)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found.")
    return zone


# ═══════════════════════════════════════════════════════════════════════
# WEBSOCKET  /ws  — live stream every 5 seconds
# ═══════════════════════════════════════════════════════════════════════

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            snapshot = pulse.full_snapshot()
            await websocket.send_text(json.dumps(snapshot, default=str))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception as exc:
        print(f"WebSocket error: {exc}")
        if websocket in active_connections:
            active_connections.remove(websocket)


# ═══════════════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    print("🏙️  UrbanPulse API online — AMD ROCm inference active")
    print("📡  WebSocket live stream available at ws://localhost:8000/ws")
    print("📖  Swagger docs: http://localhost:8000/docs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_api:app", host="0.0.0.0", port=8000, reload=True)
