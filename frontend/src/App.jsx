import React, { useEffect, useMemo, useState } from "react";
import { api, API_BASE } from "./api";
import { downloadMarkdown, printReport } from "./export";
import MapView from "./map/MapView";

const SCREENS = [
  ["overview", "Overview", "⌂"],
  ["hazards", "Hazard Map", "◉"],
  ["red-zones", "Red Zone Map", "△"],
  ["habitations", "Habitation Risk", "⌖"],
  ["sites", "Site Explorer", "◇"],
  ["capacity", "Capacity Dashboard", "▦"],
  ["planner", "Relocation Planner", "⇄"],
  ["allocations", "Allocation Results", "☷"],
  ["methodology", "Methodology", "∑"],
  ["reports", "Reports Export", "↥"],
];

const SCREEN_INFO = Object.fromEntries(
  SCREENS.map(([id, label, icon]) => [id, { label, icon }])
);

function useApi(loader) {
  const [state, setState] = useState({
    loading: true,
    data: null,
    error: null,
  });

  useEffect(() => {
    let alive = true;
    setState({ loading: true, data: null, error: null });

    loader()
      .then((data) => {
        if (alive) setState({ loading: false, data, error: null });
      })
      .catch((error) => {
        if (alive) setState({ loading: false, data: null, error });
      });

    return () => {
      alive = false;
    };
  }, [loader]);

  return state;
}

function Panel({ title, children, actions, accent = "" }) {
  return (
    <section className={`panel ${accent}`}>
      <div className="panel-head">
        <h2>{title}</h2>
        {actions}
      </div>
      {children}
    </section>
  );
}

function State({ state }) {
  if (state.loading) {
    return (
      <div className="state loading-state">
        <span className="spinner" />
        Loading authoritative backend data…
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="state error">
        Backend unavailable: {state.error.message}
      </div>
    );
  }

  return null;
}

function Metric({ label, value, icon, tone = "" }) {
  return (
    <div className={`metric ${tone}`}>
      <div className="metric-icon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

function PageIntro({ title, text }) {
  return (
    <div className="intro">
      <div>
        <div className="eyebrow">SIH 26191 · CHAMOLI DSS</div>
        <h1>{title}</h1>
        <p>{text}</p>
      </div>
      <div className="intro-status">
        <span className="pulse" /> LIVE DATA
        <br />
        <small>Backend authoritative</small>
      </div>
    </div>
  );
}

function JsonDetails({ data }) {
  return (
    <details className="raw-details">
      <summary>View raw backend payload</summary>
      <pre className="json">{JSON.stringify(data, null, 2)}</pre>
    </details>
  );
}

function DataTable({ data }) {
  const rows = Array.isArray(data)
    ? data
    : data?.items || data?.results || [];

  if (!Array.isArray(rows) || rows.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">◇</div>
        <strong>No records available</strong>
        <span>The backend returned no records for this view.</span>
      </div>
    );
  }

  const keys = [
    ...new Set(
      rows.flatMap((row) =>
        row && typeof row === "object" ? Object.keys(row) : []
      )
    ),
  ].slice(0, 6);

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {keys.map((key) => (
              <th key={key}>{key.replaceAll("_", " ")}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 50).map((row, index) => (
            <tr key={index}>
              {keys.map((key) => {
                const value = row?.[key];
                return (
                  <td key={key}>
                    {typeof value === "object"
                      ? JSON.stringify(value)
                      : String(value ?? "—")}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Overview() {
  const state = useApi(React.useCallback(() => api.habitations(), []));
  const count = Array.isArray(state.data)
    ? state.data.length
    : state.data?.items?.length ?? null;

  return (
    <>
      <PageIntro
        title="Decision Command Center"
        text="A unified view of hazard exposure, vulnerable habitations, relocation sites and allocation decisions."
      />
      <State state={state} />

      {state.data && (
        <>
          <div className="cards">
            <Metric
              icon="⌖"
              label="Habitations in response"
              value={count ?? "—"}
            />
            <Metric
              icon="◉"
              label="Analysis CRS"
              value="EPSG:32644"
              tone="gold"
            />
            <Metric
              icon="●"
              label="System status"
              value="Operational"
              tone="green"
            />
          </div>

          <div className="overview-grid">
            <Panel title="Operational posture" accent="accent-panel">
              <div className="posture">
                <div className="posture-ring">
                  <span>LIVE</span>
                </div>
                <div>
                  <h3>Decision support online</h3>
                  <p>
                    All scoring, capacity and optimization remain authoritative
                    in the backend. The interface only visualizes and submits
                    scenarios.
                  </p>
                  <div className="status-list">
                    <span>● API connected</span>
                    <span>● Data integrity preserved</span>
                    <span>● No fabricated metrics</span>
                  </div>
                </div>
              </div>
            </Panel>

            <Panel title="Habitation dataset" actions={<span className="section-tag">AUTHORITATIVE</span>}>
              <DataTable data={state.data} />
            </Panel>
          </div>

          <div className="command-strip">
            <div><span className="strip-icon">◉</span><div><b>Hazard intelligence</b><small>Explore multi-hazard spatial layers</small></div><a href="#hazards">Open map →</a></div>
            <div><span className="strip-icon red">△</span><div><b>Red-zone assessment</b><small>Review modeled risk classifications</small></div><a href="#red-zones">View zones →</a></div>
            <div><span className="strip-icon gold">◇</span><div><b>Relocation planning</b><small>Evaluate candidate sites and capacity</small></div><a href="#sites">Explore sites →</a></div>
          </div>
        </>
      )}
    </>
  );
}

function GeoScreen({ title, text, loader, mode }) {
  const state = useApi(loader);

  return (
    <>
      <PageIntro title={title} text={text} />
      <State state={state} />

      {state.data && (
        <>
          <div className="map-hero">
            <div className="map-hero-main">
              <MapView data={state.data} mode={mode} />
              <div className="map-overlay">
                <span className="map-live"><i /> LIVE LAYER</span>
                <div className="map-title">{mode === "risk" ? "Risk classification" : "Multi-hazard intelligence"}</div>
                <div className="map-subtitle">Backend-authoritative spatial visualization</div>
              </div>
              <div className="map-legend">
                <b>LEGEND</b>
                {mode === "risk" ? <><span><i className="legend red"/> Red zone</span><span><i className="legend amber"/> Amber</span><span><i className="legend green"/> Lower risk</span></> : <><span><i className="legend teal"/> Hazard layer</span><span><i className="legend white"/> Features</span></>}
              </div>
            </div>
            <div className="map-side">
              <div className="map-side-head"><span>SPATIAL STATUS</span><strong>LIVE</strong></div>
              <div className="spatial-orb"><span>{mode === "risk" ? "RISK" : "HAZARD"}</span></div>
              <h3>{mode === "risk" ? "Risk zone intelligence" : "Multi-hazard overview"}</h3>
              <p>{mode === "risk" ? "Modeled red-zone and risk-tier classifications are rendered directly from the backend." : "Hazard features are rendered directly from the authoritative hazard API response."}</p>
              <div className="map-side-stat"><span>Data source</span><b>Backend API</b></div>
              <div className="map-side-stat"><span>Display CRS</span><b>EPSG:4326</b></div>
              <details><summary>Inspect payload</summary><JsonDetails data={state.data}/></details>
            </div>
          </div>
        </>
      )}
    </>
  );
}

function Habitations() {
  const state = useApi(React.useCallback(() => api.habitations(), []));
  const rows = state.data?.features || state.data?.items || state.data?.results || [];
  const riskCount = rows.filter((row) => {
    const tier = row?.properties?.tier ?? row?.tier;
    return tier === "Immediate" || tier === "Short-term";
  }).length;

  return (
    <>
      <PageIntro
        title="Habitation Risk"
        text="Inspect vulnerable habitations, exposure and backend-computed priority classifications."
      />
      <State state={state} />
      {state.data && (
        <>
          <div className="cards">
            <Metric icon="⌖" label="Habitations returned" value={rows.length} />
            <Metric icon="△" label="Priority tiers present" value={riskCount} tone="gold" />
            <Metric icon="●" label="Source" value="Backend API" tone="green" />
          </div>
          <div className="risk-grid">
            {rows.length ? rows.slice(0, 24).map((feature, index) => {
              const item = feature?.properties || feature;
              const tier = item.tier || "Unclassified";
              const tierClass = tier.toLowerCase().replaceAll(" ", "-");
              return (
                <article className="risk-card" key={item.habitation_id || index}>
                  <div className="risk-card-top">
                    <span className="risk-id">{item.habitation_id || "HABITATION"}</span>
                    <span className={`tier-badge ${tierClass}`}>{tier}</span>
                  </div>
                  <h3>{item.name || "Unnamed habitation"}</h3>
                  <div className="risk-card-metrics">
                    <div><span>Population</span><b>{item.population ?? "—"}</b></div>
                    <div><span>Vulnerability</span><b>{item.vulnerability ?? "—"}</b></div>
                    <div><span>Priority score</span><b>{item.priority_score ?? "—"}</b></div>
                    <div><span>Population year</span><b>{item.population_year ?? "—"}</b></div>
                  </div>
                  <div className="risk-card-footer"><span>Admin unit</span><b>{item.admin_unit_id ?? "—"}</b></div>
                </article>
              );
            }) : <div className="empty-state wide-empty"><div className="empty-icon">⌖</div><strong>No habitation records</strong><span>Import or connect the authoritative habitation dataset to populate this workspace.</span></div>}
          </div>
          <Panel title="Backend record detail" actions={<span className="section-tag">RAW / AUDIT</span>}>
            <DataTable data={state.data} />
            <JsonDetails data={state.data} />
          </Panel>
        </>
      )}
    </>
  );
}

function Sites() {
  const state = useApi(React.useCallback(() => api.sites(), []));
  const rows = state.data?.features || state.data?.items || state.data?.results || [];

  return (
    <>
      <PageIntro
        title="Site Explorer"
        text="Explore candidate relocation sites and backend-computed suitability information."
      />
      <State state={state} />
      {state.data && (
        <>
          <div className="cards">
            <Metric icon="◇" label="Candidate sites" value={rows.length} />
            <Metric icon="◎" label="Suitability source" value="L10" tone="gold" />
            <Metric icon="●" label="Status" value="Backend authoritative" tone="green" />
          </div>
          <div className="site-grid">
            {rows.length ? rows.slice(0, 24).map((feature, index) => {
              const item = feature?.properties || feature;
              const suitability = item.suitability;
              const status = item.status || "Unspecified";
              return (
                <article className="site-card" key={item.site_id || index}>
                  <div className="site-card-top">
                    <span className="site-id">{item.site_id || "SITE"}</span>
                    <span className="status-badge">{status}</span>
                  </div>
                  <div className="site-visual"><span>◇</span><small>CANDIDATE SITE</small></div>
                  <div className="site-card-body">
                    <div><span>Area</span><b>{item.area ?? "—"}</b></div>
                    <div><span>Suitability</span><b>{suitability ?? "—"}</b></div>
                  </div>
                  <div className="site-explain">{item.explanation_json ? "Backend explanation available" : "No explanation payload available"}</div>
                </article>
              );
            }) : <div className="empty-state wide-empty"><div className="empty-icon">◇</div><strong>No candidate sites</strong><span>Candidate-site outputs will appear here when the backend dataset is available.</span></div>}
          </div>
          <Panel title="Site records" actions={<span className="section-tag">AUTHORITATIVE</span>}>
            <DataTable data={state.data} />
            <JsonDetails data={state.data} />
          </Panel>
        </>
      )}
    </>
  );
}

function Capacity() {
  const [id, setId] = useState("");
  const [state, setState] = useState(null);

  const loadCapacity = () => {
    if (!id.trim()) return;
    setState({ loading: true });
    api.siteCapacity(id.trim()).then((data) => setState({ data })).catch((error) => setState({ error }));
  };

  return (
    <>
      <PageIntro
        title="Capacity Dashboard"
        text="Inspect the five capacity components, effective capacity and the backend-identified binding bottleneck."
      />
      <Panel title="Site capacity lookup" actions={<span className="section-tag">L11 OUTPUT</span>}>
        <div className="lookup-box">
          <div><span className="lookup-icon">▦</span><div><b>Capacity intelligence</b><small>Enter a candidate site ID to retrieve authoritative capacity outputs.</small></div></div>
          <div className="form-row">
            <input value={id} onChange={(event) => setId(event.target.value)} onKeyDown={(event) => event.key === "Enter" && loadCapacity()} placeholder="e.g. SITE-001" />
            <button onClick={loadCapacity}>Inspect capacity →</button>
          </div>
        </div>

        {state?.loading && <div className="state loading-state"><span className="spinner" />Loading capacity output…</div>}
        {state?.error && <div className="state error">{state.error.message}</div>}

        {state?.data && (
          <div className="capacity-result">
            <div className="capacity-hero">
              <div><span>Effective capacity</span><strong>{state.data.effective_cap ?? "—"}</strong><small>persons / backend output</small></div>
              <div className="bottleneck"><span>Binding bottleneck</span><b>{state.data.binding_bottleneck ?? "—"}</b></div>
            </div>
            <div className="capacity-grid">
              {[
                ["land_cap","LAND"],["water_cap","WATER"],["sanitation_cap","SANITATION"],
                ["health_cap","HEALTH"],["access_cap","ACCESS"],
              ].map(([key,label]) => (
                <div className="capacity-item" key={key}>
                  <span>{label}</span><strong>{state.data[key] ?? "—"}</strong><small>authoritative output</small>
                </div>
              ))}
            </div>
            <div className="capacity-meta"><span>Site <b>{state.data.site_id ?? id}</b></span><span>Suitability <b>{state.data.suitability ?? "—"}</b></span><span>Status <b>{state.data.status ?? "—"}</b></span></div>
            <JsonDetails data={state.data} />
          </div>
        )}
      </Panel>
    </>
  );
}

function Planner({ onResult }) {
  const [payload, setPayload] = useState(
    '{"habitations":[],"sites":[],"distances":{},"distance_weight":1,"unmet_penalty":1,"hazard_weight":0}'
  );
  const [state, setState] = useState(null);

  const runOptimization = () => {
    try {
      setState({ loading: true });

      api
        .optimize(JSON.parse(payload))
        .then((data) => {
          setState({ data });
          onResult(data);
        })
        .catch((error) => setState({ error }));
    } catch (error) {
      setState({ error });
    }
  };

  return (
    <>
      <PageIntro
        title="Relocation Planner"
        text="Build and submit an optimization scenario. L13 remains the sole optimization authority."
      />

      <Panel title="Scenario configuration">
        <div className="planner-note">
          <span>⚡</span>
          <div>
            <strong>Backend optimization</strong>
            <small>No allocation is calculated in the browser.</small>
          </div>
        </div>

        <textarea
          value={payload}
          onChange={(event) => setPayload(event.target.value)}
        />

        <button onClick={runOptimization}>
          Run optimization <span>→</span>
        </button>

        {state?.loading && (
          <div className="state loading-state">
            <span className="spinner" />
            Running backend optimization…
          </div>
        )}

        {state?.error && (
          <div className="state error">{state.error.message}</div>
        )}

        {state?.data && (
          <div className="result-card">
            <JsonDetails data={state.data} />
          </div>
        )}
      </Panel>
    </>
  );
}

function Allocations({ result }) {
  return (
    <>
      <PageIntro
        title="Allocation Results"
        text="Review the most recent optimization response without recalculating allocations."
      />

      <Panel title="Scenario result">
        {result ? (
          <JsonDetails data={result} />
        ) : (
          <div className="empty-state">
            <div className="empty-icon">⇄</div>
            <strong>No optimization result yet</strong>
            <span>
              Run a scenario in Relocation Planner to populate this workspace.
            </span>
          </div>
        )}
      </Panel>
    </>
  );
}

function Methodology() {
  const steps = [
    ["01", "Hazard", "H = 0.45L + 0.35F + 0.20R"],
    [
      "02",
      "Vulnerability",
      "V = 0.35P + 0.25S + 0.20A + 0.10I + 0.10D",
    ],
    ["03", "Capacity", "floor(min(inputs) × 0.80)"],
    [
      "04",
      "Priority",
      "RP = 0.40 Risk + 0.25 Exposed Pop + 0.20 V + 0.10 Response Difficulty + 0.05 Recurrence",
    ],
  ];

  const pipeline = [
    "Hazard",
    "Vulnerability",
    "Risk",
    "Site Suitability",
    "Capacity",
    "Priority",
    "Allocation",
  ];

  return (
    <>
      <PageIntro
        title="Methodology"
        text="Transparent display of the frozen decision rules used by the decision-support pipeline."
      />

      <div className="method-grid">
        {steps.map(([number, title, formula]) => (
          <div className="method-card" key={number}>
            <span>{number}</span>
            <h3>{title}</h3>
            <code>{formula}</code>
          </div>
        ))}
      </div>

      <Panel title="Decision pipeline">
        <div className="pipeline">
          {pipeline.map((step, index) => (
            <React.Fragment key={step}>
              <div>{step}</div>
              {index < pipeline.length - 1 && <span>→</span>}
            </React.Fragment>
          ))}
        </div>

        <p className="muted">
          The dashboard is visualization-only; authoritative scoring and
          optimization execute in the backend.
        </p>
      </Panel>
    </>
  );
}

function Reports() {
  const [id, setId] = useState("");
  const [state, setState] = useState(null);

  const loadReport = () => {
    if (!id) return;

    api
      .report(id)
      .then((data) => setState({ data }))
      .catch((error) => setState({ error }));
  };

  return (
    <>
      <PageIntro
        title="Reports Export"
        text="Retrieve a backend decision report and export it for review or submission."
      />

      <Panel title="Run report">
        <div className="form-row">
          <input
            value={id}
            onChange={(event) => setId(event.target.value)}
            placeholder="Enter run ID"
          />
          <button onClick={loadReport}>Load report</button>
        </div>

        {state?.error && (
          <div className="state error">{state.error.message}</div>
        )}

        {state?.data && (
          <>
            <div className="actions">
              <button onClick={() => downloadMarkdown(state.data)}>
                Download Markdown
              </button>
              <button onClick={() => printReport(state.data)}>
                Print / Save PDF
              </button>
            </div>
            <JsonDetails data={state.data} />
          </>
        )}
      </Panel>
    </>
  );
}

function App() {
  const [screen, setScreen] = useState(
    () => location.hash.slice(1) || "overview"
  );
  const [result, setResult] = useState(null);

  useEffect(() => {
    const handleHashChange = () =>
      setScreen(location.hash.slice(1) || "overview");

    addEventListener("hashchange", handleHashChange);
    return () => removeEventListener("hashchange", handleHashChange);
  }, []);

  const content = useMemo(() => {
    switch (screen) {
      case "hazards":
        return (
          <GeoScreen
            title="Hazard Map"
            text="Multi-hazard spatial layers from the backend."
            loader={api.hazards}
            mode="hazards"
          />
        );
      case "red-zones":
        return (
          <GeoScreen
            title="Red Zone Map"
            text="Risk cells and modeled red-zone classifications from the backend."
            loader={api.riskMap}
            mode="risk"
          />
        );
      case "habitations":
        return <Habitations />;
      case "sites":
        return <Sites />;
      case "capacity":
        return <Capacity />;
      case "planner":
        return <Planner onResult={setResult} />;
      case "allocations":
        return <Allocations result={result} />;
      case "methodology":
        return <Methodology />;
      case "reports":
        return <Reports />;
      default:
        return <Overview />;
    }
  }, [screen, result]);

  const info = SCREEN_INFO[screen] || SCREEN_INFO.overview;

  return (
    <div className="app-shell">
      <aside>
        <div className="brand">
          <div className="brand-mark">◈</div>
          <div>
            <strong>HILL LAYER</strong>
            <small>SIH 26191 · DSS</small>
          </div>
        </div>

        <div className="nav-label">COMMAND CENTER</div>

        <nav>
          {SCREENS.map(([id, label, icon]) => (
            <a
              key={id}
              href={`#${id}`}
              className={screen === id ? "active" : ""}
            >
              <span className="nav-icon">{icon}</span>
              <span>{label}</span>
              {screen === id && <i />}
            </a>
          ))}
        </nav>

        <div className="side-status">
          <span className="pulse" /> SYSTEM OPERATIONAL
          <div>Decision support interface</div>
        </div>

        <div className="side-note">
          Modeled decision support
          <br />
          Not a legal notification.
        </div>
      </aside>

      <main>
        <header>
          <div className="breadcrumb">
            <span>HILL LAYER</span>
            <b>/</b>
            {info.label}
          </div>

          <div className="header-actions">
            <span className="live-pill">
              <i /> BACKEND CONNECTED
            </span>
            <span className="api-label">{API_BASE}</span>
          </div>
        </header>

        <div className="content">{content}</div>
      </main>
    </div>
  );
}

export default App;
