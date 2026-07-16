import { useState } from "react";

const RISK_STYLES = {
  Safe: { bg: "bg-emerald-100", text: "text-emerald-800", ring: "ring-emerald-300" },
  Watch: { bg: "bg-yellow-100", text: "text-yellow-800", ring: "ring-yellow-300" },
  Warning: { bg: "bg-orange-100", text: "text-orange-800", ring: "ring-orange-300" },
  Danger: { bg: "bg-red-100", text: "text-red-800", ring: "ring-red-300" },
};

const API_BASE = "https://bloomcast-oaco.onrender.com";

export default function App() {
  const [zip, setZip] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit() {
    if (!/^\d{5}$/.test(zip)) {
      setResult({ error: "Enter a valid 5-digit zip code" });
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/forecast/${zip}`);
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
    <div className="min-h-screen flex flex-col items-center justify-center p-4 bg-slate-50">
      <h1 className="text-2xl font-bold mb-1 text-slate-800">BloomCast NJ</h1>
      <p className="text-sm text-slate-500 mb-6">Harmful algal bloom risk forecast</p>

      <div className="flex gap-2 mb-6">
        <input
          value={zip}
          onChange={(e) => setZip(e.target.value.replace(/\D/g, "").slice(0, 5))}
          onKeyDown={handleKeyDown}
          placeholder="Enter NJ zip code"
          maxLength={5}
          inputMode="numeric"
          className="px-4 py-2 rounded-lg border border-slate-300 w-48 focus:outline-none focus:ring-2 focus:ring-slate-400"
        />
        <button
          onClick={handleSubmit}
          disabled={loading}
          className="px-4 py-2 rounded-lg bg-slate-800 text-white font-medium disabled:opacity-50"
        >
          {loading ? "..." : "Check"}
        </button>
      </div>

      {result && !result.error && (
        <div className={`rounded-2xl p-6 w-72 ring-2 ${style.ring} ${style.bg}`}>
          <p className="text-sm text-slate-600">{result.lake_name ?? "Nearest lake"}</p>
          <p className={`text-3xl font-bold ${style.text}`}>{result.risk_level}</p>
          <p className="text-sm text-slate-500 mt-1">
            {result.valid_for_days ? `${result.valid_for_days}-day forecast` : "7-day forecast"}
          </p>
        </div>
      )}

      {result?.error && (
        <div className="rounded-lg px-4 py-3 w-72 bg-red-50 border border-red-200 text-red-700 text-sm">
          {result.error}
        </div>
      )}
    </div>
  );
}