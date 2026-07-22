import { useState } from "react";

const TIERS = [
  {
    name: "Safe",
    band: "Below 10 µg/L",
    color: "#059669",
    bg: "#ecfdf5",
    meaning: "Low chlorophyll. No bloom expected. Normal precautions are fine.",
  },
  {
    name: "Watch",
    band: "10–20 µg/L",
    color: "#d97706",
    bg: "#fffbeb",
    meaning: "Algae levels are rising. Keep an eye out for green tint or scum, especially in calm, warm weather.",
  },
  {
    name: "Warning",
    band: "20–40 µg/L",
    color: "#ea580c",
    bg: "#fff7ed",
    meaning: "Elevated risk. Avoid swallowing water, and keep pets and young children away from visible scum.",
  },
  {
    name: "Danger",
    band: "Above 40 µg/L",
    color: "#dc2626",
    bg: "#fef2f2",
    meaning: "High risk. Avoid contact with the water until an official advisory clears it.",
  },
];

const FAQS = [
  {
    q: "What is a harmful algal bloom?",
    a: "A rapid overgrowth of cyanobacteria (often called blue-green algae) in a lake. Some cyanobacteria release toxins that can make people and animals sick through skin contact, swallowing water, or inhaling spray. Blooms usually show up as green streaks, a paint-like surface scum, or cloudy discoloration.",
  },
  {
    q: "What does BloomCast actually predict?",
    a: "It forecasts chlorophyll-a, the green pigment found in algae, about a week ahead for monitored NJ lakes. More chlorophyll generally means more algae, so it works as an early signal of rising bloom risk. It does not measure toxins directly, which is why it is a forecast, not a health clearance.",
  },
  {
    q: "Why chlorophyll instead of measuring the toxins?",
    a: "Toxin testing needs a lab and a physical water sample, so it can only tell you about a bloom that is already happening. Chlorophyll can be estimated from monitoring data and satellite imagery, which lets us look ahead instead of only reacting. The tradeoff is that chlorophyll reflects all algae, not only the toxic kind — so we treat a high reading as a reason for caution, not a confirmed toxin level.",
  },
  {
    q: "How accurate is this?",
    a: "It is an experimental research project built by students, not an official monitoring system. Predictions are strongest for lakes with long monitoring records and weaker for lakes with little data. Always treat it as a heads-up, and check the official source before you get in the water.",
  },
  {
    q: "What drives blooms in the first place?",
    a: "Three things mostly: warmth, sunlight, and nutrients. Hot, calm, sunny stretches let cyanobacteria multiply, and rain washes phosphorus and nitrogen off lawns and farmland into the lake, feeding them. That is why blooms peak in late summer.",
  },
];

export default function Explainer() {
  const [open, setOpen] = useState(null);

  return (
    <div className="w-full max-w-3xl mx-auto mt-16 px-1">
      <div className="mb-10">
        <p className="text-xs font-semibold tracking-widest text-slate-400 uppercase mb-2">
          Understanding the forecast
        </p>
        <h2 className="text-2xl font-bold text-slate-800 mb-3">
          What a bloom is, and how to read this app
        </h2>
        <p className="text-slate-600 leading-relaxed">
          BloomCast gives you a week's heads-up on harmful algal bloom risk for
          New Jersey lakes. Here's what that means, what the colors stand for,
          and where the forecast comes from — in plain terms.
        </p>
      </div>

      <div className="mb-12">
        <h3 className="text-sm font-semibold text-slate-700 mb-4">
          What the risk levels mean
        </h3>
        <div className="space-y-2">
          {TIERS.map((tier) => (
            <div
              key={tier.name}
              className="flex items-start gap-4 rounded-lg p-4"
              style={{ backgroundColor: tier.bg }}
            >
              <div className="flex flex-col items-center min-w-[72px]">
                <span
                  className="inline-block w-4 h-4 rounded-full mb-1"
                  style={{ backgroundColor: tier.color }}
                />
                <span className="text-sm font-bold" style={{ color: tier.color }}>
                  {tier.name}
                </span>
                <span className="text-[11px] text-slate-500 mt-0.5 text-center">
                  {tier.band}
                </span>
              </div>
              <p className="text-sm text-slate-700 leading-relaxed pt-0.5">
                {tier.meaning}
              </p>
            </div>
          ))}
        </div>
        <p className="text-xs text-slate-400 mt-3 leading-relaxed">
          These bands adapt WHO guidance on chlorophyll-a and NJ DEP's cyanobacteria
          alert framework into a simplified four-level scale. The official NJ system
          uses cyanobacteria cell counts and toxin levels across six tiers.
        </p>
      </div>

      <div className="mb-12">
        <h3 className="text-sm font-semibold text-slate-700 mb-4">
          How the forecast is made
        </h3>
        <ol className="space-y-4">
          {[
            ["Gather", "We pull years of water quality records (chlorophyll, temperature, phosphorus) for monitored NJ lakes from public EPA and NJ DEP sources."],
            ["Learn", "A machine learning model studies how those readings change over time and finds the patterns that tend to come before a rise in algae."],
            ["Forecast", "For each lake, the model projects chlorophyll about a week ahead and translates it into one of the four risk levels."],
            ["Check", "We validate against real field samples — collecting water and identifying cyanobacteria under a microscope — to confirm the model tracks reality."],
          ].map(([label, text], i) => (
            <li key={label} className="flex gap-4">
              <span className="text-slate-300 font-mono text-sm font-bold pt-0.5 min-w-[28px]">
                {String(i + 1).padStart(2, "0")}
              </span>
              <div>
                <p className="text-sm font-semibold text-slate-800">{label}</p>
                <p className="text-sm text-slate-600 leading-relaxed">{text}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>

      <div className="mb-10">
        <h3 className="text-sm font-semibold text-slate-700 mb-4">
          Common questions
        </h3>
        <div className="divide-y divide-slate-200 border-t border-b border-slate-200">
          {FAQS.map((item, i) => (
            <div key={i}>
              <button
                onClick={() => setOpen(open === i ? null : i)}
                className="w-full flex justify-between items-center text-left py-4 gap-4"
              >
                <span className="text-sm font-medium text-slate-800">{item.q}</span>
                <span className="text-slate-400 text-lg leading-none">
                  {open === i ? "–" : "+"}
                </span>
              </button>
              {open === i && (
                <p className="text-sm text-slate-600 leading-relaxed pb-4 -mt-1">
                  {item.a}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-lg bg-slate-50 border border-slate-200 p-4">
        <p className="text-sm text-slate-600 leading-relaxed">
          BloomCast is a student research project and an experimental forecast — not
          an official health advisory. Before entering any water, check the{" "}
          <a
            href="https://dep.nj.gov/hab/"
            target="_blank"
            rel="noopener noreferrer"
            className="underline font-medium text-slate-700"
          >
            NJ DEP HAB Dashboard
          </a>{" "}
          for current, verified conditions.
        </p>
      </div>
    </div>
  );
}