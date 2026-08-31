import { lazy, Suspense, useState } from "react";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import Community from "./Community";

const LakeMap = lazy(() => import("./LakeMap"));
const Explainer = lazy(() => import("./Explainer"));
const Cyanobacteria = lazy(() => import("./Cyanobacteria"));

function NavBar() {
  const linkClass = ({ isActive }) =>
    `px-3 py-2 text-sm font-medium rounded-lg transition ${
      isActive ? "bg-teal-700 text-white" : "text-slate-600 hover:bg-teal-50 hover:text-teal-800"
    }`;

  return (
    <nav aria-label="Primary navigation" className="w-full flex flex-wrap items-center gap-1 sm:gap-2 px-4 py-3 border-b border-slate-200 bg-white/80 backdrop-blur sticky top-0 z-[1000]">
      <NavLink to="/" className="flex items-center gap-2 mr-auto sm:mr-4">
        <img src="/favicon.svg" alt="BloomCast logo" className="h-7 w-7" />
        <span className="font-bold text-slate-800">BloomCast <span className="text-teal-700">NJ</span></span>
      </NavLink>
      <NavLink to="/" className={linkClass} end>Forecast</NavLink>
      <NavLink to="/about" className={linkClass}>How it works</NavLink>
      <NavLink to="/field-research" className={linkClass}>Bloom science</NavLink>
      <NavLink to="/community" className={linkClass}>Community</NavLink>
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

  async function handleSubmit(event) {
    event?.preventDefault();
    const q = query.trim();
    if (!q || loading) return;

    const isZip = /^\d{5}$/.test(q);
    const url = isZip
      ? `${API_BASE}/forecast/${q}`
      : `${API_BASE}/lake/${encodeURIComponent(q)}`;

    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      setResult(await res.json());
    } catch {
      setResult({ error: "Couldn't fetch the forecast. The data service may be waking up—please try again in a moment." });
    } finally {
      setLoading(false);
    }
  }

  const style = result?.risk_level ? RISK_STYLES[result.risk_level] : null;

  return (
    <div className="flex flex-col items-center justify-center px-4 pt-10 pb-4">
      <h1 className="text-3xl font-bold mb-1 text-slate-800">BloomCast <span className="text-teal-700">NJ</span></h1>
      <p className="text-sm text-slate-500 mb-1">Harmful algal bloom risk forecast for New Jersey lakes</p>
      <p className="text-sm font-semibold text-teal-700 mb-6">Check before you go.</p>

      <form id="check-before-you-go" onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-2 mb-2 w-full sm:w-auto">
        <label htmlFor="lake-search" className="sr-only">New Jersey ZIP code or lake name</label>
        <input
          id="lake-search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Enter NJ zip code or lake name"
          className="px-4 py-2 rounded-lg border border-slate-300 w-full sm:w-64 focus:outline-none focus:ring-2 focus:ring-teal-500"
        />
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 rounded-lg bg-teal-700 text-white font-medium hover:bg-teal-800 disabled:opacity-50 transition shadow-sm"
        >
          {loading ? "Checking…" : "Check lake risk"}
        </button>
      </form>
      <p aria-live="polite" className="text-xs text-slate-400 mb-6 min-h-4">
        {loading ? "Getting the latest available forecast…" : "Experimental forecast (always verify official conditions)."}
      </p>

      {result && !result.error && style && (
        <div className={`rounded-2xl p-6 w-72 ring-2 shadow-sm ${style.ring} ${style.bg}`}>
          <p className="text-xs text-slate-500">Nearest monitored lake</p>
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
          {result.predicted_chl_a != null && (
            <p className="text-sm text-slate-600 mt-1">Predicted chlorophyll-a: {result.predicted_chl_a} µg/L</p>
          )}
          {result.drivers?.length > 0 && (
            <div className="mt-4 pt-3 border-t border-black/10">
              <p className="text-xs font-semibold text-slate-600 mb-2">What's driving this</p>
              <div className="space-y-1.5">
                {result.drivers.map((driver) => (
                  <div key={driver.label} className="flex items-baseline justify-between gap-3 text-sm">
                    <span className="text-slate-600">{driver.label}</span>
                    <span className="text-slate-800 font-medium text-right">
                      {driver.value} <span className="text-slate-500 font-normal">· {driver.note}</span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {result?.error && (
        <div role="alert" className="rounded-lg px-4 py-3 w-72 bg-red-50 border border-red-200 text-red-700 text-sm">
          {result.error}
        </div>
      )}

      <Suspense fallback={<p className="w-full max-w-3xl mx-auto mt-10 text-sm text-slate-500">Loading lake map…</p>}>
        <LakeMap />
      </Suspense>
    </div>
  );
}

export default function App() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-sky-100 via-sky-50 to-slate-50">
      <NavBar />
      <Suspense fallback={<div className="w-full max-w-3xl mx-auto mt-16 px-4 text-sm text-slate-500">Loading…</div>}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/about" element={<Explainer />} />
          <Route path="/field-research" element={<Cyanobacteria />} />
          <Route path="/cyanobacteria" element={<Navigate to="/field-research" replace />} />
          <Route path="/community" element={<Community />} />
        </Routes>
      </Suspense>
    </div>
  );
}