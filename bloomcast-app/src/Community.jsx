import { useState, useEffect } from "react";

const API_BASE = "https://bloomcast-oaco.onrender.com";

export default function Community() {
  const [token, setToken] = useState(() => localStorage.getItem("bc_token"));
  const [username, setUsername] = useState(() => localStorage.getItem("bc_username"));

  function saveAuth(tok, name) {
    localStorage.setItem("bc_token", tok);
    localStorage.setItem("bc_username", name);
    setToken(tok);
    setUsername(name);
  }

  function logout() {
    localStorage.removeItem("bc_token");
    localStorage.removeItem("bc_username");
    setToken(null);
    setUsername(null);
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-slate-800 mb-1">Community Observations</h1>
      <p className="text-sm text-slate-500 mb-6">
        Share what you've seen at NJ lakes. Posts are reviewed before appearing.
        Community reports are unverified observations, the model forecast is the
        authoritative signal.
      </p>

      {token ? (
        <LoggedIn username={username} token={token} onLogout={logout} />
      ) : (
        <AuthForm onAuth={saveAuth} />
      )}

      <Feed />
    </div>
  );
}

function AuthForm({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function submit() {
    setError(null);
    if (!username.trim() || !password) {
      setError("Enter a username and password.");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Something went wrong.");
      } else {
        onAuth(data.token, data.username);
      }
    } catch {
      setError("Couldn't reach the server. It may be waking up — try again.");
    }
    setLoading(false);
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 mb-8">
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setMode("login")}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
            mode === "login" ? "bg-slate-800 text-white" : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          Log in
        </button>
        <button
          onClick={() => setMode("signup")}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
            mode === "signup" ? "bg-slate-800 text-white" : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          Sign up
        </button>
      </div>

      <div className="space-y-3">
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Username"
          className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-400"
        />
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          type="password"
          placeholder="Password"
          className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-400"
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          onClick={submit}
          disabled={loading}
          className="w-full bg-slate-800 text-white rounded-lg py-2 font-medium disabled:opacity-50"
        >
          {loading ? "..." : mode === "login" ? "Log in" : "Create account"}
        </button>
      </div>
    </div>
  );
}

function LoggedIn({ username, token, onLogout }) {
  const [lake, setLake] = useState("");
  const [body, setBody] = useState("");
  const [lakes, setLakes] = useState([]);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/lakes`)
      .then((r) => r.json())
      .then((d) => setLakes((d.lakes || []).map((l) => l.lake_name)))
      .catch(() => setLakes([]));
  }, []);

  async function submit() {
    setStatus(null);
    if (!lake || !body.trim()) {
      setStatus({ error: "Pick a lake and write something." });
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/posts`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ lake_name: lake, body: body.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        setStatus({ error: data.detail || "Couldn't submit." });
      } else {
        setStatus({ ok: data.message || "Submitted for review." });
        setBody("");
        setLake("");
      }
    } catch {
      setStatus({ error: "Couldn't reach the server." });
    }
    setLoading(false);
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 mb-8">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-slate-600">
          Logged in as <span className="font-semibold">{username}</span>
        </p>
        <button onClick={onLogout} className="text-sm text-slate-500 hover:underline">
          Log out
        </button>
      </div>

      <div className="space-y-3">
        <select
          value={lake}
          onChange={(e) => setLake(e.target.value)}
          className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-400"
        >
          <option value="">Select a lake…</option>
          {lakes.map((name) => (
            <option key={name} value={name}>{name}</option>
          ))}
        </select>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={3}
          maxLength={1000}
          placeholder="What did you observe? (e.g. green water, dead fish, a posted warning sign)"
          className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-400"
        />
        {status?.error && <p className="text-sm text-red-600">{status.error}</p>}
        {status?.ok && <p className="text-sm text-green-700">{status.ok}</p>}
        <button
          onClick={submit}
          disabled={loading}
          className="bg-slate-800 text-white rounded-lg px-4 py-2 font-medium disabled:opacity-50"
        >
          {loading ? "..." : "Submit observation"}
        </button>
      </div>
    </div>
  );
}

function Feed() {
  const [posts, setPosts] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/posts`)
      .then((r) => r.json())
      .then((d) => setPosts(d.posts || []))
      .catch(() => setPosts([]));
  }, []);

  if (posts === null) {
    return <p className="text-sm text-slate-400">Loading observations…</p>;
  }
  if (posts.length === 0) {
    return <p className="text-sm text-slate-400">No observations yet. Be the first to post.</p>;
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-slate-800">Recent observations</h2>
      {posts.map((p) => (
        <div key={p.id} className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-baseline justify-between mb-1">
            <span className="font-medium text-slate-700">{p.lake_name}</span>
            <span className="text-xs text-slate-400">
              {new Date(p.created_at).toLocaleDateString()}
            </span>
          </div>
          <p className="text-slate-700 text-sm">{p.body}</p>
          <p className="text-xs text-slate-400 mt-2">— {p.username}</p>
        </div>
      ))}
    </div>
  );
}