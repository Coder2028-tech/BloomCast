import { Link } from "react-router-dom";

const SAMPLES = [
  {
    id: "HOP-2026-07-11-01",
    lake: "Lake Hopatcong",
    status: "Caution",
    statusClass: "bg-amber-100 text-amber-800",
    conditions: "25.4°C water · pH 7.4 · moderate wind",
    finding: "Cyanobacteria observed; rare relative density (1 of 4).",
    interpretation: "The field record and microscope capture support treating the site as an early caution signal, not a toxin confirmation.",
    images: [
      { src: "/field-research/lhshore1.jpg", alt: "Lake Hopatcong shoreline sampling location", caption: "Shoreline context" },
      { src: "/field-research/lhshore2.jpg", alt: "Close view of water at the Lake Hopatcong shoreline", caption: "Near-shore water" },
      { src: "/field-research/lhdolicho1.jpg", alt: "Microscope field from the Lake Hopatcong sample", caption: "Microscope field" },
    ],
  },
  {
    id: "BUD-2026-07-11-01",
    lake: "Budd Lake",
    status: "Caution",
    statusClass: "bg-amber-100 text-amber-800",
    conditions: "25.6°C water · pH 7.0 · calm wind",
    finding: "Cyanobacteria observed; scattered relative density (2 of 4).",
    interpretation: "Green, low-clarity water and the higher microscope density made this the strongest field signal of the three samples.",
    images: [
      { src: "/field-research/blwater1.jpg", alt: "Green water at the Budd Lake sampling location", caption: "Sampling location" },
      { src: "/field-research/blwater2.jpg", alt: "Close view of green, low-clarity water at Budd Lake", caption: "Water appearance" },
      { src: "/field-research/blmicro1.jpg", alt: "Microscope field from the Budd Lake sample", caption: "Microscope field" },
    ],
  },
  {
    id: "RVR-2026-07-11-01",
    lake: "Round Valley Reservoir",
    status: "No Advisory",
    statusClass: "bg-emerald-100 text-emerald-800",
    conditions: "25.2°C water · pH 8.2 · light wind",
    finding: "No confirmed cyanobacteria; rare relative density score (1 of 4).",
    interpretation: "The visible plant material and microscope particles were not recorded as confirmed cyanobacteria, underscoring why appearance alone is insufficient.",
    images: [
      { src: "/field-research/rvwater1.jpg", alt: "Round Valley Reservoir shoreline with aquatic vegetation", caption: "Shoreline context" },
      { src: "/field-research/rvwater2.jpg", alt: "Shallow water and vegetation at Round Valley Reservoir", caption: "Water appearance" },
      { src: "/field-research/rvbact1.jpg", alt: "Microscope field from the Round Valley Reservoir sample", caption: "Microscope field" },
    ],
  },
];

function Photo({ photo }) {
  return (
    <a href={photo.src} target="_blank" rel="noopener noreferrer" className="group block">
      <div className="aspect-[4/3] overflow-hidden rounded-lg bg-slate-100 border border-slate-200">
        <img
          src={photo.src}
          alt={photo.alt}
          loading="lazy"
          decoding="async"
          className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.02]"
        />
      </div>
      <p className="mt-1.5 text-xs text-slate-500 group-hover:text-slate-700">{photo.caption} ↗</p>
    </a>
  );
}

export default function Cyanobacteria() {
  return (
    <main className="w-full max-w-3xl mx-auto mt-16 px-4 sm:px-1 pb-16">
      <header className="mb-10">
        <p className="text-xs font-semibold tracking-widest text-slate-400 uppercase mb-2">
          Bloom science · Field study 1
        </p>
        <h1 className="text-2xl font-bold text-slate-800 mb-3">Cyanobacteria and Field Research</h1>
        <p className="text-slate-600 leading-relaxed max-w-2xl">
          Cyanobacteria are a natural part of freshwater ecosystems. In warm,
          nutrient-rich, calm conditions they can multiply into harmful algal blooms.
          Our field research connects visible lake conditions and microscope observations
          with BloomCast’s data-driven early risk signal.
        </p>
      </header>

      <section aria-labelledby="science-heading" className="mb-12">
        <h2 id="science-heading" className="text-sm font-semibold text-slate-700 mb-4">The science behind the signal</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <article className="rounded-lg border border-slate-200 bg-white p-5">
            <p className="font-semibold text-slate-800 mb-2">What are cyanobacteria?</p>
            <p className="text-sm text-slate-600 leading-relaxed">
              Often called blue-green algae, they are photosynthetic bacteria. Not every bloom is toxic, and toxin presence cannot be determined by sight; laboratory testing is required.
            </p>
          </article>
          <article className="rounded-lg border border-amber-200 bg-amber-50 p-5">
            <p className="font-semibold text-amber-900 mb-2">Why blooms matter</p>
            <p className="text-sm text-amber-900/80 leading-relaxed">
              Some blooms can irritate skin or produce toxins that affect people, pets, and wildlife. Avoid suspicious water or scum and follow official NJ DEP advisories.
            </p>
          </article>
        </div>
      </section>

      <section aria-labelledby="visit-heading" className="mb-12">
        <p className="text-xs font-semibold tracking-widest text-slate-400 uppercase mb-2">July 11, 2026 · Three monitored lakes</p>
        <h2 id="visit-heading" className="text-xl font-bold text-slate-800 mb-2">Field Visit 1: What we recorded</h2>
        <p className="text-sm text-slate-600 leading-relaxed mb-6">
          The same-day comparison combined water chemistry, site conditions, official status, and microscope review. These are field observations—not toxin results or health clearances.
        </p>

        <div className="space-y-8">
          {SAMPLES.map((sample) => (
            <article key={sample.id} className="rounded-xl border border-slate-200 bg-white overflow-hidden">
              <div className="p-5 sm:p-6">
                <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
                  <div>
                    <h3 className="text-lg font-bold text-slate-800">{sample.lake}</h3>
                    <p className="font-mono text-[11px] text-slate-400 mt-0.5">{sample.id}</p>
                  </div>
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${sample.statusClass}`}>{sample.status}</span>
                </div>
                <div className="grid gap-4 sm:grid-cols-[0.8fr_1.2fr] mb-5">
                  <div>
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Recorded conditions</p>
                    <p className="text-sm text-slate-700">{sample.conditions}</p>
                    <p className="text-sm font-semibold text-slate-800 mt-3">{sample.finding}</p>
                  </div>
                  <p className="text-sm text-slate-600 leading-relaxed">{sample.interpretation}</p>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {sample.images.map((photo) => <Photo key={photo.src} photo={photo} />)}
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="rounded-lg bg-slate-800 text-white p-5 mb-12 sm:flex sm:items-start sm:justify-between sm:gap-8">
        <div>
          <h2 className="text-sm font-semibold mb-2">What Field Visit I taught us</h2>
          <p className="text-sm text-slate-300 leading-relaxed max-w-xl">
            Three lakes sampled on the same day produced three different combinations of water appearance, chemistry, and microscope evidence. That variation is exactly why BloomCast combines multiple signals instead of relying on a single photo or observation.
          </p>
        </div>
        <p className="text-sm font-medium text-white mt-4 sm:mt-0 sm:max-w-[220px]">
          Forecast + field evidence = a more informed lake-day decision.
        </p>
      </section>

      <section className="rounded-lg border border-emerald-200 bg-emerald-50 p-5 sm:flex sm:items-center sm:justify-between sm:gap-6">
        <div>
          <p className="text-xs font-semibold tracking-widest text-emerald-700 uppercase mb-1">BloomCast’s role</p>
          <h2 className="text-lg font-bold text-emerald-950">Check before you go.</h2>
          <p className="text-sm text-emerald-900/80 mt-1 max-w-lg">
            Start with an early forecast, then verify current conditions with the official source before entering the water.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 mt-4 sm:mt-0 shrink-0">
          <Link to="/" className="rounded-lg bg-slate-800 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-700 transition">Check a lake</Link>
          <a href="https://dep.nj.gov/hab/" target="_blank" rel="noopener noreferrer" className="rounded-lg border border-emerald-700 px-3 py-2 text-sm font-semibold text-emerald-800 hover:bg-emerald-100 transition">NJ DEP status</a>
        </div>
      </section>
    </main>
  );
}