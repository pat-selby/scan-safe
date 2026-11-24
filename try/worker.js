// Run the published scoring rules locally. Scanned strings are passed as data.
let engine;
async function initialize() {
  const base = new URL("vendor/runtime/", location.href).href;
  importScripts(base + "pyodide.js");
  const [runtime, source] = await Promise.all([
    loadPyodide({indexURL: base}),
    fetch("scorer.py").then(response => {
      if (!response.ok) throw new Error("Scoring rules unavailable");
      return response.text();
    })
  ]);
  runtime.runPython(source);
  runtime.runPython("import json");
  return runtime;
}
self.onmessage = async ({data}) => {
  try {
    engine ??= initialize();
    const runtime = await engine;
    runtime.globals.set("submitted_address", data);
    const result = runtime.runPython([
      "del _SIMHASH_CACHE[:-64]",
      "r = score_url(submitted_address, enable_radar=False)",
      "json.dumps(dict(level=r.level, score=r.score, findings=r.user_findings, technical=r.tech_findings))"
    ].join("\n"));
    self.postMessage({result: JSON.parse(result)});
  } catch {
    engine = null;
    self.postMessage({error: "The scanner could not load. Check your connection and try again."});
  }
};
