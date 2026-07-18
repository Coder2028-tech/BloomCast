import { useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const API_BASE = "https://bloomcast-oaco.onrender.com";

const RISK_COLORS = {
  Safe: "#059669",     // emerald
  Watch: "#d97706",    // amber
  Warning: "#ea580c",  // orange
  Danger: "#dc2626",   // red
};
const NO_DATA_COLOR = "#9ca3af"; // gray

// Center roughly on north-central NJ where most monitored lakes cluster
const NJ_CENTER = [40.75, -74.6];

export default function LakeMap() {
  const [lakes, setLakes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API_BASE}/lakes`);
        if (!res.ok) throw new Error(`Server returned ${res.status}`);
        const data = await res.json();
        setLakes(data.lakes || []);
      } catch (e) {
        setError("Couldn't load the lake map. The backend may be waking up — try refreshing in a moment.");
      }
      setLoading(false);
    }
    load();
  }, []);

  return (
    <div className="w-full max-w-3xl mx-auto mt-10">
      <h2 className="text-lg font-semibold text-slate-800 mb-1">NJ lake risk map</h2>
      <p className="text-sm text-slate-500 mb-3">
        Colored lakes have a current forecast. Gray lakes don't have enough recent monitoring data to forecast.
      </p>

      {loading && <p className="text-sm text-slate-500">Loading lakes…</p>}
      {error && (
        <div className="rounded-lg px-4 py-3 bg-red-50 border border-red-200 text-red-700 text-sm">
          {error}
        </div>
      )}

      {!loading && !error && (
        <>
          <div className="rounded-xl overflow-hidden border border-slate-200" style={{ height: "480px" }}>
            <MapContainer center={NJ_CENTER} zoom={9} style={{ height: "100%", width: "100%" }}>
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              {lakes.map((lake) => {
                const color = lake.has_data ? RISK_COLORS[lake.risk_level] : NO_DATA_COLOR;
                return (
                  <CircleMarker
                    key={lake.lake_name}
                    center={[lake.lat, lake.long]}
                    radius={9}
                    pathOptions={{
                      color: "#fff",
                      weight: 2,
                      fillColor: color,
                      fillOpacity: 0.9,
                    }}
                  >
                    <Popup>
                      <div className="text-sm">
                        <p className="font-semibold">{lake.lake_name}</p>
                        {lake.has_data ? (
                          <>
                            <p>
                              Risk: <span style={{ color, fontWeight: 600 }}>{lake.risk_level}</span>
                            </p>
                            <p className="text-slate-500">
                              Predicted chlorophyll-a: {lake.predicted_chl_a} µg/L
                            </p>
                            <p className="text-slate-400 text-xs mt-1">
                              Based on data from {lake.data_as_of}
                            </p>
                          </>
                        ) : (
                          <p className="text-slate-500">Not enough recent data to forecast</p>
                        )}
                      </div>
                    </Popup>
                  </CircleMarker>
                );
              })}
            </MapContainer>
          </div>

          {/* Legend */}
          <div className="flex flex-wrap gap-4 mt-3 text-sm">
            {Object.entries(RISK_COLORS).map(([level, color]) => (
              <div key={level} className="flex items-center gap-1.5">
                <span className="inline-block w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                <span className="text-slate-600">{level}</span>
              </div>
            ))}
            <div className="flex items-center gap-1.5">
              <span className="inline-block w-3 h-3 rounded-full" style={{ backgroundColor: NO_DATA_COLOR }} />
              <span className="text-slate-600">No data</span>
            </div>
          </div>

          <p className="text-xs text-slate-400 mt-3">
            Experimental forecast — not an official health advisory. For current bloom status, check the{" "}
            <a
              href="https://dep.nj.gov/hab/"
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
            >
              NJ DEP HAB Dashboard
            </a>
            .
          </p>
        </>
      )}
    </div>
  );
}