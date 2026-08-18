import { useState } from "react";
import LakeMap from "./LakeMap";
import Explainer from "./Explainer";
import { Routes, Route, NavLink } from "react-router-dom";

function NavBar() {
  const linkClass = ({ isActive }) =>
    `px-3 py-2 text-sm font-medium rounded-lg transition ${
      isActive ? "bg-slate-800 text-white" : "text-slate-600 hover:bg-slate-200"
    }`;
  return (
    <nav className="w-full flex items-center gap-2 px-4 py-3 border-b border-slate-200 bg-white">
      <span className="font-bold text-slate-800 mr-4">BloomCast NJ</span>
      <NavLink to="/" className={linkClass} end>Forecast</NavLink>
      <NavLink to="/about" className={linkClass}>How it works</NavLink>
    </nav>
  );
}

const RISK_STYLES = {
  Safe: { bg: "bg-emerald-100", text: "text-emerald-800", ring: "ring-emerald-300" },
  Watch: { bg: "bg-yellow-100", text: "text-yellow-800", ring: "ring-yellow-300" },
  Warning: { bg: "bg-orange-100", text: "text-orange-800", ring: "ring-orange-300" },
  Danger: { bg: "bg-red-100", text: "text-red-800", ring: "ring-red-300" },
};

const API_BASE = "https://bloomcast-oaco.onrender.com";

function Home() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  async function handleSubmit() {
    const q = query.trim();
    if (!q) return;
    const isZip = /^\d{5}$/.test(q);
    const url = isZip
      ? `${API_BASE}/forecast/${q}`
      : `${API_BASE}/lake/${encodeURIComponent(q)}`;
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setResult({ error: "Couldn't fetch forecast. The backend may be waking up from sleep - try again in a moment." });
  }
    setLoading(false);
}

  function handleKeyDown(e) {
    if (e.key === "Enter") handleSubmit();
  }

  const style = result?.risk_level ? RISK_STYLES[result.risk_level] : null;
  return (
    <div className="flex flex-col items-center justify-center p-4">
      <h1 className="text-2xl font-bold mb-1 text-slate-800">BloomCast NJ</h1>
      <p className="text-sm text-slate-500 mb-6">Harmful algal bloom risk forecast</p>

      <div className="flex gap-2 mb-6">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter NJ zip code or lake name"
          className="px-4 py-2 rounded-lg border border-slate-300 w-64 focus:outline-none focus:ring-2 focus:ring-slate-400"
        />
        <button
          onClick={handleSubmit}
          disabled={loading}
          className="px-4 py-2 rounded-lg bg-slate-800 text-white font-medium disabled:opacity-50"
        >
          {loading ? "..." : "Check"}
        </button>
      </div>

      {result && !result.error && style &&(
        <div className={`rounded-2xl p-6 w-72 ring-2 ${style.ring} ${style.bg}`}>
          <p className="text-xs text-slate-500">Nearest Monitored Lake:</p>
          <p className="text-sm font-medium text-slate-700">
            {result.lake_name}
            {result.distance_miles != null && (
              <span className="text-slate-500 font-normal"> · {result.distance_miles} mi away</span>
              )}
          </p>
          <p className={`text-3xl font-bold ${style.text}`}>{result.risk_level}</p>
          <p className="text-sm text-slate-500 mt-1">
            {result.valid_for_days ? `${result.valid_for_days}-day forecast` : "Next observation forecast"}
          </p>
           {result.data_as_of && (
      <p className="text-xs text-slate-400 mt-0.5">Based on data from {result.data_as_of}</p>
    )}

    <p className={`text-3xl font-bold ${style.text}`}>{result.risk_level}</p>
    {result.predicted_chl_a != null && (
      <p className="text-sm text-slate-600 mt-1">
        Predicted chlorophyll-a: {result.predicted_chl_a} µg/L
    </p>
)}

    {result.drivers?.length > 0 && (
      <div className="mt-4 pt-3 border-t border-black/10">
        <p className="text-xs font-semibold text-slate-600 mb-2">What's driving this</p>
        <div className="space-y-1.5">
          {result.drivers.map((d) => (
            <div key={d.label} className="flex items-baseline justify-between text-sm">
              <span className="text-slate-600">{d.label}</span>
              <span className="text-slate-800 font-medium">
                {d.value} <span className="text-slate-500 font-normal">· {d.note}</span>
              </span>
            </div>
          ))}
        </div>
      </div>
    )}
        </div>
      )}

      {result?.error && (
        <div className="rounded-lg px-4 py-3 w-72 bg-red-50 border border-red-200 text-red-700 text-sm">
          {result.error}
        </div>
      )}
      <LakeMap />
    </div>
  );
}
export default function App() {
  return (
    <div className="min-h-screen bg-slate-50">
      <NavBar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/about" element={<Explainer />} />
      </Routes>
    </div>
  );
}