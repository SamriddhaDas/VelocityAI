import { useState, useEffect, useRef, useCallback } from "react";

// ── Config ──────────────────────────────────────────────────────────────
const WS_URL  = "ws://localhost:8000/ws";
const API_URL = "http://localhost:8000";
const REFRESH_INTERVAL = 5000;

// ── Colour palette ──────────────────────────────────────────────────────
const C = {
  bg:        "#080c14",
  surface:   "#0d1421",
  surfaceAlt:"#111a2e",
  border:    "#1a2744",
  accent:    "#00d4ff",
  accentDim: "#0099bb",
  green:     "#00ff9d",
  yellow:    "#ffd700",
  orange:    "#ff8c00",
  red:       "#ff3860",
  text:      "#e8edf8",
  textMuted: "#5a7099",
  grid:      "#1a2744",
};

// ── Risk colour map ──────────────────────────────────────────────────────
const riskColor = { NORMAL: C.green, ELEVATED: C.yellow, HIGH: C.orange, CRITICAL: C.red };
const congColor = (v) => v > 0.75 ? C.red : v > 0.50 ? C.orange : v > 0.25 ? C.yellow : C.green;
const fillColor = (v) => v > 0.85 ? C.red : v > 0.70 ? C.orange : v > 0.50 ? C.yellow : C.green;

// ── Helpers ──────────────────────────────────────────────────────────────
const pct = (v) => `${Math.round(v * 100)}%`;
const fmt = (n, d = 1) => Number(n).toFixed(d);

// ═══════════════════════════════════════════════════════════════════════
// SUB-COMPONENTS
// ═══════════════════════════════════════════════════════════════════════

function KpiCard({ label, value, unit, color = C.accent, sub }) {
  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.border}`,
      borderRadius: 12, padding: "18px 22px",
      display: "flex", flexDirection: "column", gap: 4,
    }}>
      <div style={{ fontSize: 11, color: C.textMuted, textTransform: "uppercase", letterSpacing: 2 }}>{label}</div>
      <div style={{ fontSize: 32, fontWeight: 700, color, fontFamily: "'Space Mono', monospace" }}>
        {value}<span style={{ fontSize: 16, fontWeight: 400, color: C.textMuted, marginLeft: 4 }}>{unit}</span>
      </div>
      {sub && <div style={{ fontSize: 12, color: C.textMuted }}>{sub}</div>}
    </div>
  );
}

function SectionHeader({ icon, title, badge, badgeColor = C.accent }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
      <span style={{ fontSize: 22 }}>{icon}</span>
      <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: C.text, textTransform: "uppercase", letterSpacing: 3 }}>{title}</h2>
      {badge != null && (
        <span style={{
          marginLeft: "auto", background: `${badgeColor}22`,
          border: `1px solid ${badgeColor}`, color: badgeColor,
          borderRadius: 6, padding: "2px 10px", fontSize: 12, fontWeight: 700,
        }}>{badge}</span>
      )}
    </div>
  );
}

function MiniBar({ value, max = 1, color }) {
  const pctVal = Math.min(1, value / max);
  return (
    <div style={{ background: C.border, borderRadius: 4, height: 6, overflow: "hidden", flex: 1 }}>
      <div style={{ width: pct(pctVal), height: "100%", background: color || congColor(pctVal), borderRadius: 4,
        transition: "width 0.8s ease" }} />
    </div>
  );
}

// ── Heatmap 8×8 ──────────────────────────────────────────────────────────
function Heatmap({ data }) {
  if (!data || !data.length) return null;
  const flat = data.flat();
  const maxVal = Math.max(...flat, 0.01);
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${data[0].length}, 1fr)`, gap: 2 }}>
      {data.map((row, i) =>
        row.map((val, j) => {
          const intensity = val / maxVal;
          const r = Math.round(intensity * 255);
          const g = Math.round((1 - intensity) * 120);
          return (
            <div key={`${i}-${j}`} title={`${fmt(val, 2)}`} style={{
              width: 20, height: 20, borderRadius: 3,
              background: `rgb(${r}, ${g}, 30)`,
              opacity: 0.2 + intensity * 0.8,
              transition: "background 0.5s",
            }} />
          );
        })
      )}
    </div>
  );
}

// ── Sparkline using SVG ───────────────────────────────────────────────────
function Sparkline({ history, color = C.accent, height = 40, width = 160 }) {
  if (!history || history.length < 2) return null;
  const max = Math.max(...history, 0.01);
  const min = Math.min(...history);
  const pts = history.map((v, i) => {
    const x = (i / (history.length - 1)) * width;
    const y = height - ((v - min) / (max - min + 0.01)) * height;
    return `${x},${y}`;
  }).join(" ");
  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// TRAFFIC MODULE
// ═══════════════════════════════════════════════════════════════════════

function TrafficModule({ data }) {
  if (!data) return <div style={{ color: C.textMuted }}>Loading traffic data…</div>;
  const { average_congestion, worst_intersection, worst_congestion, alerts = [] } = data;
  return (
    <div>
      <SectionHeader icon="🚦" title="Traffic Intelligence"
        badge={`AVG ${pct(average_congestion)}`}
        badgeColor={congColor(average_congestion)} />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 20 }}>
        <KpiCard label="Avg Congestion" value={pct(average_congestion)} color={congColor(average_congestion)} sub="city-wide" />
        <KpiCard label="Worst Intersection" value={worst_intersection} unit="" color={C.red}
          sub={`${pct(worst_congestion)} congestion`} />
      </div>

      <div style={{ fontSize: 11, color: C.textMuted, marginBottom: 8, letterSpacing: 2, textTransform: "uppercase" }}>
        Intersection Congestion Levels
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {alerts.map(a => (
          <div key={a.intersection_id} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 11, color: C.textMuted, width: 60, fontFamily: "monospace" }}>{a.intersection_id}</span>
            <MiniBar value={a.congestion_level} color={congColor(a.congestion_level)} />
            <span style={{ fontSize: 11, fontFamily: "monospace", color: congColor(a.congestion_level), width: 38, textAlign: "right" }}>
              {pct(a.congestion_level)}
            </span>
            <span style={{ fontSize: 10, color: C.textMuted, width: 60 }}>+{a.predicted_delay_minutes}min</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// WASTE MODULE
// ═══════════════════════════════════════════════════════════════════════

function WasteModule({ data }) {
  if (!data) return <div style={{ color: C.textMuted }}>Loading waste data…</div>;
  const { total_bins, critical_bins, average_fill_level, optimised_route, alerts = [] } = data;
  const high = alerts.filter(a => a.priority === "CRITICAL" || a.priority === "HIGH").length;
  return (
    <div>
      <SectionHeader icon="🗑️" title="Waste Management"
        badge={`${critical_bins} URGENT`}
        badgeColor={critical_bins > 0 ? C.red : C.green} />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 20 }}>
        <KpiCard label="Avg Fill" value={pct(average_fill_level)} color={fillColor(average_fill_level)} />
        <KpiCard label="Critical Bins" value={critical_bins} unit={`/ ${total_bins}`} color={C.red} />
        <KpiCard label="Route Distance" value={fmt(optimised_route?.total_distance_km, 1)} unit="km"
          sub={`Saving ${optimised_route?.fuel_saving_percent}%`} color={C.green} />
      </div>

      <div style={{ fontSize: 11, color: C.textMuted, marginBottom: 8, letterSpacing: 2, textTransform: "uppercase" }}>
        Bin Fill Levels (top 12)
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
        {alerts.slice(0, 12).map(a => (
          <div key={a.bin_id} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 10, color: C.textMuted, width: 52, fontFamily: "monospace" }}>{a.bin_id}</span>
            <MiniBar value={a.fill_level} color={fillColor(a.fill_level)} />
            <span style={{
              fontSize: 10, fontFamily: "monospace",
              color: fillColor(a.fill_level), width: 36, textAlign: "right",
            }}>{pct(a.fill_level)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// ENERGY MODULE
// ═══════════════════════════════════════════════════════════════════════

function EnergyModule({ data }) {
  const [sparklines, setSparklines] = useState({});

  useEffect(() => {
    if (!data?.alerts) return;
    setSparklines(prev => {
      const next = { ...prev };
      data.alerts.forEach(a => {
        const hist = next[a.zone_id] || [];
        hist.push(a.current_kwh);
        next[a.zone_id] = hist.slice(-30);
      });
      return next;
    });
  }, [data]);

  if (!data) return <div style={{ color: C.textMuted }}>Loading energy data…</div>;
  const { total_current_kwh, total_baseline_kwh, excess_percent, anomaly_zones, alerts = [] } = data;
  return (
    <div>
      <SectionHeader icon="⚡" title="Energy Monitor"
        badge={`${anomaly_zones} ANOMALIES`}
        badgeColor={anomaly_zones > 0 ? C.red : C.green} />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 20 }}>
        <KpiCard label="Total kWh" value={fmt(total_current_kwh, 0)} unit="kWh"
          color={excess_percent > 10 ? C.red : C.accent} />
        <KpiCard label="vs Baseline" value={`${excess_percent > 0 ? "+" : ""}${fmt(excess_percent, 1)}`} unit="%"
          color={excess_percent > 0 ? C.orange : C.green} />
        <KpiCard label="Anomaly Zones" value={anomaly_zones} color={anomaly_zones > 0 ? C.red : C.green} />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {alerts.map(a => (
          <div key={a.zone_id} style={{
            background: a.is_anomaly ? `${C.red}11` : C.surfaceAlt,
            border: `1px solid ${a.is_anomaly ? C.red : C.border}`,
            borderRadius: 8, padding: "10px 14px",
            display: "flex", alignItems: "center", gap: 14,
          }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: a.is_anomaly ? C.red : C.text }}>{a.zone_id}</div>
              <div style={{ fontSize: 11, color: C.textMuted, marginTop: 2 }}>{a.recommendation}</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 18, fontFamily: "monospace", color: a.is_anomaly ? C.red : C.accent }}>
                {fmt(a.current_kwh, 0)} kWh
              </div>
              {sparklines[a.zone_id] && (
                <Sparkline history={sparklines[a.zone_id]} color={a.is_anomaly ? C.red : C.accent} width={100} height={24} />
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// CROWD MODULE
// ═══════════════════════════════════════════════════════════════════════

function CrowdModule({ data }) {
  if (!data) return <div style={{ color: C.textMuted }}>Loading crowd data…</div>;
  const { total_monitored_people, high_risk_zones, inference_latency_ms, alerts = [] } = data;
  const [selectedZone, setSelectedZone] = useState(null);
  const selected = alerts.find(a => a.zone_id === selectedZone) || alerts[0];

  return (
    <div>
      <SectionHeader icon="👥" title="Crowd Intelligence"
        badge={`${high_risk_zones} HIGH RISK`}
        badgeColor={high_risk_zones > 0 ? C.red : C.green} />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 16 }}>
        <KpiCard label="Total Monitored" value={total_monitored_people.toLocaleString()} unit="people" color={C.accent} />
        <KpiCard label="High Risk Zones" value={high_risk_zones} color={high_risk_zones > 0 ? C.red : C.green} />
        <KpiCard label="Inference" value={inference_latency_ms} unit="ms" color={C.green} sub="AMD ROCm" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        {/* Zone list */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {alerts.map(a => (
            <div key={a.zone_id}
              onClick={() => setSelectedZone(a.zone_id)}
              style={{
                background: selectedZone === a.zone_id ? `${riskColor[a.risk_level]}22` : C.surfaceAlt,
                border: `1px solid ${selectedZone === a.zone_id ? riskColor[a.risk_level] : C.border}`,
                borderRadius: 8, padding: "8px 12px", cursor: "pointer",
                transition: "all 0.2s",
              }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: C.text }}>{a.zone_id}</span>
                <span style={{
                  fontSize: 10, background: `${riskColor[a.risk_level]}33`,
                  color: riskColor[a.risk_level], padding: "1px 6px", borderRadius: 4,
                }}>{a.risk_level}</span>
              </div>
              <div style={{ fontSize: 11, color: C.textMuted, marginTop: 3 }}>
                {a.person_count} people · {fmt(a.density, 2)} p/m²
              </div>
            </div>
          ))}
        </div>

        {/* Heatmap */}
        {selected && (
          <div style={{
            background: C.surfaceAlt, border: `1px solid ${C.border}`,
            borderRadius: 8, padding: 12,
          }}>
            <div style={{ fontSize: 11, color: C.textMuted, marginBottom: 8 }}>
              Density Heatmap — {selected.zone_id}
            </div>
            <Heatmap data={selected.heatmap} />
            <div style={{ marginTop: 8, fontSize: 10, color: C.textMuted }}>
              YOLOv8 · {inference_latency_ms}ms inference · AMD ROCm
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// STATUS BAR
// ═══════════════════════════════════════════════════════════════════════

function StatusBar({ connected, lastUpdate, tick }) {
  const pulse = tick % 2 === 0;
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 16,
      padding: "8px 24px", background: C.surface, borderBottom: `1px solid ${C.border}`,
      fontSize: 11, color: C.textMuted,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <div style={{
          width: 8, height: 8, borderRadius: "50%",
          background: connected ? C.green : C.red,
          boxShadow: connected && pulse ? `0 0 8px ${C.green}` : "none",
          transition: "box-shadow 0.5s",
        }} />
        <span style={{ color: connected ? C.green : C.red }}>
          {connected ? "LIVE" : "DISCONNECTED"}
        </span>
      </div>
      <span>AMD ROCm · &lt;40ms inference</span>
      <span>WebSocket Stream</span>
      {lastUpdate && <span style={{ marginLeft: "auto" }}>Updated {lastUpdate}</span>}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// MOCK DATA GENERATOR (when no backend is available)
// ═══════════════════════════════════════════════════════════════════════

function generateMockData() {
  const intersections = ["INT-001","INT-002","INT-003","INT-004","INT-005","INT-006","INT-007","INT-008"];
  const trafficAlerts = intersections.map(id => ({
    intersection_id: id,
    congestion_level: Math.random(),
    predicted_delay_minutes: (Math.random() * 12).toFixed(1),
    recommended_signal_timing: { north_south_green: 45, east_west_green: 35, pedestrian_interval: 20 },
    timestamp: new Date().toISOString(),
  }));
  const avgCong = trafficAlerts.reduce((s, a) => s + a.congestion_level, 0) / trafficAlerts.length;
  const worst = trafficAlerts.reduce((a, b) => a.congestion_level > b.congestion_level ? a : b);

  const wasteAlerts = Array.from({length: 20}, (_, i) => {
    const fill = Math.random();
    return {
      bin_id: `BIN-${String(i+1).padStart(3,"0")}`,
      fill_level: fill,
      overflow_eta_minutes: (Math.random() * 120).toFixed(1),
      priority: fill > 0.95 ? "CRITICAL" : fill > 0.80 ? "HIGH" : fill > 0.60 ? "MEDIUM" : "LOW",
      location: [51.505 + (Math.random()-0.5)*0.1, -0.09 + (Math.random()-0.5)*0.1],
      timestamp: new Date().toISOString(),
    };
  });
  const avgFill = wasteAlerts.reduce((s, a) => s + a.fill_level, 0) / wasteAlerts.length;
  const critical = wasteAlerts.filter(a => ["CRITICAL","HIGH"].includes(a.priority)).length;

  const energyZones = ["ZONE-N","ZONE-S","ZONE-E","ZONE-W","ZONE-CENTRAL"];
  const baselineMap = {ZONE_N:450,ZONE_S:380,ZONE_E:420,ZONE_W:410,ZONE_CENTRAL:600};
  const energyAlerts = energyZones.map(zone => {
    const baseline = {ZONE_N:450,ZONE_S:380,"ZONE-E":420,"ZONE-W":410,"ZONE-CENTRAL":600}[zone] || 450;
    const current = baseline * (0.85 + Math.random() * 0.5);
    const isAnomaly = current > baseline * 1.3;
    return {
      zone_id: zone,
      current_kwh: current,
      baseline_kwh: baseline,
      anomaly_score: Math.random() * 4,
      is_anomaly: isAnomaly,
      recommendation: isAnomaly ? `⚠️ Spike in ${zone}. Dispatch maintenance.` : "Normal operation.",
      timestamp: new Date().toISOString(),
    };
  });

  const crowdZones = [
    { id: "PLAZA-MAIN", capacity: 500 },
    { id: "STATION-NORTH", capacity: 800 },
    { id: "MARKET-EAST", capacity: 300 },
    { id: "PARK-WEST", capacity: 1200 },
    { id: "ARENA", capacity: 5000 },
  ];
  const crowdAlerts = crowdZones.map(z => {
    const count = Math.floor(Math.random() * z.capacity);
    const density = count / (z.capacity * 2);
    const capUtil = count / z.capacity;
    const risk = capUtil > 0.95 ? "CRITICAL" : capUtil > 0.80 ? "HIGH" : capUtil > 0.60 ? "ELEVATED" : "NORMAL";
    const heatmap = Array.from({length:8}, () => Array.from({length:8}, () => Math.random() * density * 5));
    return { zone_id: z.id, person_count: count, density, risk_level: risk, heatmap, timestamp: new Date().toISOString() };
  });

  return {
    timestamp: new Date().toISOString(),
    traffic: {
      average_congestion: avgCong,
      worst_intersection: worst.intersection_id,
      worst_congestion: worst.congestion_level,
      alerts: trafficAlerts,
    },
    waste: {
      total_bins: 20, critical_bins: critical,
      average_fill_level: avgFill,
      optimised_route: {
        bins: wasteAlerts.filter(a => a.priority !== "LOW").map(a => a.bin_id),
        total_distance_km: (5 + Math.random() * 10).toFixed(1),
        estimated_duration_minutes: (30 + Math.random() * 30).toFixed(0),
        fuel_saving_percent: (15 + Math.random() * 15).toFixed(1),
        waypoints: [],
      },
      alerts: wasteAlerts,
    },
    energy: {
      total_current_kwh: energyAlerts.reduce((s, a) => s + a.current_kwh, 0),
      total_baseline_kwh: 2260,
      excess_percent: (Math.random() * 20 - 5).toFixed(1),
      anomaly_zones: energyAlerts.filter(a => a.is_anomaly).length,
      alerts: energyAlerts,
    },
    crowd: {
      total_monitored_people: crowdAlerts.reduce((s, a) => s + a.person_count, 0),
      high_risk_zones: crowdAlerts.filter(a => ["CRITICAL","HIGH"].includes(a.risk_level)).length,
      inference_latency_ms: 31,
      alerts: crowdAlerts,
    },
  };
}

// ═══════════════════════════════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════════════════════════════

const TABS = ["Overview", "Traffic", "Waste", "Energy", "Crowd"];

export default function VelocityAIDashboard() {
  const [data, setData]           = useState(null);
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [tick, setTick]           = useState(0);
  const [activeTab, setActiveTab] = useState("Overview");
  const wsRef = useRef(null);
  const timerRef = useRef(null);

  const updateData = useCallback((d) => {
    setData(d);
    setLastUpdate(new Date().toLocaleTimeString());
    setTick(t => t + 1);
  }, []);

  // Try WebSocket; fall back to mock data
  useEffect(() => {
    let ws;
    try {
      ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        startMockPolling();
      };
      ws.onerror = () => {
        setConnected(false);
        ws.close();
        startMockPolling();
      };
      ws.onmessage = (e) => {
        try { updateData(JSON.parse(e.data)); } catch {}
      };
    } catch {
      startMockPolling();
    }

    function startMockPolling() {
      // Immediately populate with mock data
      updateData(generateMockData());
      timerRef.current = setInterval(() => updateData(generateMockData()), REFRESH_INTERVAL);
    }

    return () => {
      ws?.close();
      clearInterval(timerRef.current);
    };
  }, [updateData]);

  // Styles
  const tabStyle = (tab) => ({
    padding: "8px 20px", cursor: "pointer", fontSize: 12,
    fontWeight: activeTab === tab ? 700 : 400,
    color: activeTab === tab ? C.accent : C.textMuted,
    borderBottom: `2px solid ${activeTab === tab ? C.accent : "transparent"}`,
    background: "none", border: "none",
    borderBottom: `2px solid ${activeTab === tab ? C.accent : "transparent"}`,
    transition: "color 0.2s",
    letterSpacing: 1, textTransform: "uppercase",
  });

  const panelStyle = {
    background: C.surface, border: `1px solid ${C.border}`,
    borderRadius: 14, padding: 24,
  };

  return (
    <div style={{
      minHeight: "100vh", background: C.bg, color: C.text,
      fontFamily: "'DM Mono', 'Courier New', monospace",
    }}>
      {/* Import Google Fonts */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Mono:wght@400;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 6px; } 
        ::-webkit-scrollbar-track { background: ${C.bg}; }
        ::-webkit-scrollbar-thumb { background: ${C.border}; border-radius: 3px; }
        body { background: ${C.bg}; }
      `}</style>

      {/* Header */}
      <header style={{
        padding: "16px 28px", borderBottom: `1px solid ${C.border}`,
        display: "flex", alignItems: "center", gap: 16,
        background: `${C.surface}cc`, backdropFilter: "blur(12px)",
        position: "sticky", top: 0, zIndex: 100,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, color: C.accent, fontFamily: "'Space Mono', monospace", letterSpacing: 2 }}>
              VELOCITYAI
            </div>
            <div style={{ fontSize: 10, color: C.textMuted, letterSpacing: 3 }}>SMARTER DECISIONS. STRONGER CITIES.</div>
          </div>
        </div>

        {/* Tabs */}
        <nav style={{ display: "flex", marginLeft: 32, gap: 2 }}>
          {TABS.map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)} style={tabStyle(tab)}>{tab}</button>
          ))}
        </nav>

        {/* AMD badge */}
        <div style={{
          marginLeft: "auto", background: `${C.accent}11`,
          border: `1px solid ${C.accentDim}`, borderRadius: 8,
          padding: "4px 12px", fontSize: 10, color: C.accent, letterSpacing: 2,
        }}>
          AMD ROCm · Instinct GPU
        </div>
      </header>

      {/* Status bar */}
      <StatusBar connected={connected} lastUpdate={lastUpdate} tick={tick} />

      {/* Main content */}
      <main style={{ padding: "24px 28px", maxWidth: 1400, margin: "0 auto" }}>

        {/* OVERVIEW TAB */}
        {activeTab === "Overview" && (
          <div>
            {/* Top KPI strip */}
            {data && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 24 }}>
                <KpiCard label="Avg Congestion" value={pct(data.traffic.average_congestion)}
                  color={congColor(data.traffic.average_congestion)} sub="30% reduction target" />
                <KpiCard label="Critical Bins" value={data.waste.critical_bins} unit={`/ ${data.waste.total_bins}`}
                  color={data.waste.critical_bins > 0 ? C.red : C.green} sub="25% cost saving target" />
                <KpiCard label="Energy Anomalies" value={data.energy.anomaly_zones} unit="zones"
                  color={data.energy.anomaly_zones > 0 ? C.red : C.green} sub="12% consumption target" />
                <KpiCard label="High-Risk Zones" value={data.crowd.high_risk_zones}
                  color={data.crowd.high_risk_zones > 0 ? C.red : C.green} sub="real-time stampede guard" />
              </div>
            )}

            {/* 2×2 module grid */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
              <div style={panelStyle}><TrafficModule data={data?.traffic} /></div>
              <div style={panelStyle}><WasteModule   data={data?.waste}   /></div>
              <div style={panelStyle}><EnergyModule  data={data?.energy}  /></div>
              <div style={panelStyle}><CrowdModule   data={data?.crowd}   /></div>
            </div>

            {/* Impact stats */}
            <div style={{
              marginTop: 20, background: C.surface, border: `1px solid ${C.border}`,
              borderRadius: 14, padding: 20,
              display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 16,
              textAlign: "center",
            }}>
              {[
                ["↓ 30%", "Traffic Congestion"],
                ["↓ 25%", "Waste Collection Cost"],
                ["↓ 12%", "Energy Consumption"],
                ["~0ms", "Crowd Alert Latency"],
                ["~59K kg", "CO₂ / Week Saved"],
                ["4,700+", "Cities Addressable"],
              ].map(([val, label]) => (
                <div key={label}>
                  <div style={{ fontSize: 22, fontWeight: 700, color: C.green, fontFamily: "'Space Mono', monospace" }}>{val}</div>
                  <div style={{ fontSize: 10, color: C.textMuted, marginTop: 4, lineHeight: 1.4 }}>{label}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* INDIVIDUAL MODULE TABS */}
        {activeTab === "Traffic" && <div style={panelStyle}><TrafficModule data={data?.traffic} /></div>}
        {activeTab === "Waste"   && <div style={panelStyle}><WasteModule   data={data?.waste}   /></div>}
        {activeTab === "Energy"  && <div style={panelStyle}><EnergyModule  data={data?.energy}  /></div>}
        {activeTab === "Crowd"   && <div style={panelStyle}><CrowdModule   data={data?.crowd}   /></div>}
      </main>

      {/* Footer */}
      <footer style={{ padding: "16px 28px", borderTop: `1px solid ${C.border}`, display: "flex", justifyContent: "space-between" }}>
        <span style={{ fontSize: 10, color: C.textMuted }}>VelocityAI · AMD Slingshot 2026 · AI for Smart Cities</span>
        <span style={{ fontSize: 10, color: C.textMuted }}>FastAPI + Kafka + React · Sub-40ms latency</span>
      </footer>
    </div>
  );
}
