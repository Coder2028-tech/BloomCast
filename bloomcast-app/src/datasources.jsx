export default function DataSources() {
  return (
    <footer className="border-t border-slate-200 bg-white/70 backdrop-blur mt-12">
      <div className="max-w-3xl mx-auto px-4 py-4 text-xs text-slate-500 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <p>
          <span className="font-medium text-slate-600">Data sources:</span>{" "}
          <a
            href="https://www.waterqualitydata.us/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-teal-700 underline decoration-slate-300"
          >
            EPA Water Quality Portal
          </a>{" "}
          ·{" "}
          <a
            href="https://dep.nj.gov/hab/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-teal-700 underline decoration-slate-300"
          >
            NJ DEP HAB Dashboard
          </a>{" "}
          ·{" "}
          <a
            href="https://simplemaps.com/data/us-zips"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-teal-700 underline decoration-slate-300"
          >
            ZIP coordinates: SimpleMaps
          </a>
        </p>
        <p className="text-slate-400 shrink-0">
          Experimental forecast · not an official advisory
        </p>
      </div>
    </footer>
  );
}