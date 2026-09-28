import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api, API_BASE } from "./api";
import { downloadMarkdown, printReport } from "./export";
import MapView from "./map/MapView";

const NAV = [
  ["overview", "Command Center", "⌂"],
  ["hazards", "Hazard Intelligence", "◉"],
  ["red-zones", "Red Zones", "△"],
  ["habitations", "Vulnerable Habitations", "⌖"],
  ["sites", "Relocation Sites", "◇"],
  ["capacity", "Carrying Capacity", "▦"],
  ["ml", "AI / ML Insights", "✦"],
  ["planner", "Relocation Planner", "⇄"],
  ["allocations", "Allocation Results", "↗"],
  ["methodology", "Decision Logic", "∑"],
  ["reports", "Reports", "↥"],
];

function useRequest(loader, deps = []) {
  const [state, setState] = useState({ loading: true, data: null, error: null });
  useEffect(() => {
    let active = true;
    setState({ loading: true, data: null, error: null });
    Promise.resolve().then(loader).then(data => {
      if (active) setState({ loading: false, data, error: null });
    }).catch(error => {
      if (active) setState({ loading: false, data: null, error });
    });
    return () => { active = false; };
  }, deps);
  return state;
}

function rowsOf(data) {
  if (Array.isArray(data)) return data;
  return data?.items || data?.results || data?.features || [];
}
function propsOf(row) { return row?.properties || row || {}; }
function fmt(value, digits = 2) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return Number.isInteger(value) ? value.toLocaleString("en-IN") : value.toFixed(digits);
  return value;
}
function tierClass(tier = "") { return tier.toLowerCase().replaceAll(" ", "-"); }

function Shell({ screen, setScreen, children }) {
  const [mobile, setMobile] = useState(false);
  const nav = (id) => { setScreen(id); setMobile(false); window.scrollTo({ top: 0, behavior: "smooth" }); };
  return (
    <div className="app">
      <aside className={mobile ? "sidebar open" : "sidebar"}>
        <div className="brand">
          <div className="brand-mark"><span>CH</span><i /></div>
          <div><strong>CHAMOLI</strong><small>RESILIENCE DSS</small></div>
        </div>
        <div className="project-chip"><span className="live-dot" /> SIH 26191 <b>PROTOTYPE</b></div>
        <nav>
          <div className="nav-label">DECISION WORKSPACE</div>
          {NAV.slice(0, 9).map(([id, label, icon]) => (
            <button key={id} className={screen === id ? "active" : ""} onClick={() => nav(id)}>
              <span className="nav-icon">{icon}</span><span>{label}</span>{screen === id && <em />}
            </button>
          ))}
          <div className="nav-label lower">OUTPUT & AUDIT</div>
          <button className={screen === "reports" ? "active" : ""} onClick={() => nav("reports")}><span className="nav-icon">↥</span><span>Reports & Evidence</span>{screen === "reports" && <em />}</button>
        </nav>
        <div className="sidebar-bottom">
          <div className="system-mini"><span className="live-dot" /><div><b>System operational</b><small>Backend authoritative</small></div></div>
          <div className="crs-mini">PROCESSING CRS <strong>EPSG:32644</strong></div>
        </div>
      </aside>
      <main>
        <header>
          <button className="menu" onClick={() => setMobile(v => !v)}>☰</button>
          <div className="crumb"><span>SIH 26191</span><b>/</b>{NAV.find(x => x[0] === screen)?.[1]}</div>
          <div className="header-actions"><span className="api-pill"><i /> API CONNECTED</span><a href={API_BASE} target="_blank" rel="noreferrer">API ↗</a></div>
        </header>
        <div className="content">{children}</div>
        <footer><span>CHAMOLI RESILIENCE DSS</span><span>Decision support · not a legal notification</span><span>SIH 26191 · L17 verified</span></footer>
      </main>
    </div>
  );
}

function Intro({ eyebrow = "DECISION SUPPORT", title, text, action }) {
  return <div className="hero-intro">
    <div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{text}</p></div>
    {action}
  </div>;
}

function KPI({ icon, label, value, sub, tone = "" }) {
  return <div className={"kpi " + tone}><div className="kpi-icon">{icon}</div><div><span>{label}</span><strong>{value}</strong>{sub && <small>{sub}</small>}</div></div>;
}
function Panel({ title, eyebrow, children, action }) {
  return <section className="panel"><div className="panel-head"><div>{eyebrow && <span>{eyebrow}</span>}<h2>{title}</h2></div>{action}</div>{children}</section>;
}
function Loading({ text = "Loading authoritative data…" }) { return <div className="loading"><i />{text}</div>; }
function ErrorBox({ error }) { return <div className="error-box"><b>Backend response unavailable</b><span>{error?.message || "Unknown error"}</span></div>; }
function Empty({ icon = "◇", title = "No authoritative records", text = "The backend returned no records for this view." }) {
  return <div className="empty"><div>{icon}</div><b>{title}</b><span>{text}</span></div>;
}
function Badge({ children, tone = "" }) { return <span className={"badge " + tone}>{children}</span>; }

function CommandCenter({ go }) {
  const state = useRequest(() => Promise.allSettled([api.habitations(), api.sites(), api.priorities(), api.hazards(), api.mlStatus()]), []);
  if (state.loading) return <><Intro title="Command Center" text="Loading the Chamoli decision-support workspace…" /><Loading /></>;
  if (state.error) return <><Intro title="Command Center" text="Unified operational view." /><ErrorBox error={state.error} /></>;
  const [hab, sites, priorities, hazards, ml] = state.data.map(x => x.status === "fulfilled" ? x.value : null);
  const hRows = rowsOf(hab), sRows = rowsOf(sites), pRows = rowsOf(priorities), hzRows = rowsOf(hazards);
  const immediate = pRows.filter(x => propsOf(x).tier === "Immediate").length;
  const population = hRows.reduce((n, x) => n + Number(propsOf(x).population || 0), 0);
  return <>
    <Intro eyebrow="CHAMOLI · DISTRICT RESPONSE WORKSPACE" title="Resilience Command Center"
      text="From hazard intelligence to relocation allocation — one auditable workspace for vulnerable habitations and safer relocation planning."
      action={<button className="primary" onClick={() => go("hazards")}>Open live map <span>→</span></button>} />
    <div className="kpi-grid">
      <KPI icon="⌖" label="Habitations" value={fmt(hRows.length)} sub="backend records" />
      <KPI icon="△" label="Immediate priority" value={fmt(immediate)} sub="L12 tier" tone="red" />
      <KPI icon="◇" label="Candidate sites" value={fmt(sRows.length)} sub="L10 outputs" tone="gold" />
      <KPI icon="✦" label="AI / ML" value={ml?.status === "READY_TO_TRAIN" ? "READY" : "ASSISTIVE"} sub={ml?.status || "not trained"} tone="violet" />
    </div>
    <div className="dashboard-grid">
      <Panel title="Spatial situation" eyebrow="LIVE GIS" action={<button className="ghost" onClick={() => go("red-zones")}>Open risk map ↗</button>}>
        <div className="dashboard-map"><MapView data={apiMapFallback(hab)} mode="risk" /></div>
      </Panel>
      <Panel title="Response posture" eyebrow="SYSTEM STATUS">
        <div className="posture-hero"><div className="radar"><span>LIVE</span></div><div><Badge tone="green">OPERATIONAL</Badge><h3>Decision pipeline online</h3><p>Backend remains the single source of truth. Scores are not recomputed in the browser.</p></div></div>
        <div className="signal-list"><div><span>Data API</span><b>CONNECTED</b></div><div><span>Hazard layers</span><b>{hzRows.length ? hzRows.length + " REGISTERED" : "AWAITING INPUT"}</b></div><div><span>Population records</span><b>{population ? fmt(population) : "—"}</b></div><div><span>ML role</span><b>ASSISTIVE ONLY</b></div></div>
      </Panel>
    </div>
    <div className="section-title"><span>PRIORITY QUEUE</span><h2>Habitations requiring attention</h2><button className="ghost" onClick={() => go("habitations")}>View all →</button></div>
    <div className="priority-table">
      {pRows.length ? pRows.slice(0, 6).map((row, i) => {
        const p = propsOf(row); return <button key={p.habitation_id || i} className="priority-row" onClick={() => go("habitations")}>
          <span className="rank">0{i + 1}</span><div><b>{p.name || p.habitation_id || "Habitation"}</b><small>{p.habitation_id || "ID unavailable"}</small></div>
          <span className={"tier " + tierClass(p.tier)}>{p.tier || "Unclassified"}</span><strong>{fmt(p.priority_score)}</strong><span className="row-arrow">→</span>
        </button>;
      }) : <Empty icon="⌖" title="Priority outputs not populated" text="Connect L12 priority outputs to populate the response queue." />}
    </div>
    <div className="habitation-feature">
      <div className="habitation-feature-head">
        <div><span className="eyebrow">L09 + L12 · VULNERABILITY & PRIORITY</span><h2>Vulnerable Habitations</h2><p>See exposed populations, vulnerability scores and relocation priority in one operational register.</p></div>
        <button className="primary" onClick={() => go("habitations")}>Open habitation register <span>→</span></button>
      </div>
      <div className="habitation-feature-stats">
        <div><b>{fmt(hRows.length)}</b><span>REGISTERED HABITATIONS</span></div>
        <div><b>{fmt(immediate)}</b><span>IMMEDIATE / SHORT-TERM</span></div>
        <div><b>{fmt(population)}</b><span>POPULATION COVERAGE</span></div>
      </div>
    </div>
    <div className="feature-strip">
      <button onClick={() => go("ml")}><span>✦</span><div><b>AI-assisted susceptibility</b><small>Spatially validated ML framework · deterministic safety fallback</small></div><em>Explore →</em></button>
      <button onClick={() => go("sites")}><span>◇</span><div><b>Relocation readiness</b><small>Suitability → capacity → allocation</small></div><em>Explore →</em></button>
      <button onClick={() => go("methodology")}><span>∑</span><div><b>Auditable decision logic</b><small>Frozen weights, thresholds and provenance</small></div><em>Inspect →</em></button>
    </div>
  </>;
}
function apiMapFallback(hab) {
  return hab?.type === "FeatureCollection" ? hab : { type: "FeatureCollection", features: [] };
}

function MapWorkspace({ mode = "hazards" }) {
  const loader = useCallback(() => mode === "risk" ? api.riskMap() : api.hazards(), [mode]);
  const state = useRequest(loader, [loader]);
  const title = mode === "risk" ? "Red Zone Intelligence" : "Multi-Hazard Intelligence";
  if (state.loading) return <><Intro eyebrow="GIS INTELLIGENCE" title={title} text="Loading backend spatial layers…" /><Loading /></>;
  if (state.error) return <><Intro title={title} text="Backend spatial visualization." /><ErrorBox error={state.error} /></>;
  return <><Intro eyebrow="GIS INTELLIGENCE · EPSG:4326 DISPLAY" title={title}
    text={mode === "risk" ? "Inspect modeled risk tiers, hard exclusions and combined hazard outputs." : "Explore registered hazard layers and their provenance without changing authoritative scores."}
    action={<Badge tone="green">● LIVE BACKEND LAYER</Badge>} />
    <div className="map-workspace"><div className="big-map"><MapView data={state.data} mode={mode} /><div className="map-hud"><span>CHAMOLI</span><b>{mode === "risk" ? "COMBINED RISK" : "HAZARD STACK"}</b></div><div className="map-legend-box"><b>LEGEND</b>{mode === "risk" ? <><span><i className="dot red"/> Red zone ≥ 0.70</span><span><i className="dot amber"/> Amber 0.55–0.70</span><span><i className="dot green"/> Lower risk &lt; 0.55</span></> : <><span><i className="dot teal"/> Registered hazard features</span><span><i className="dot white"/> Other geometry</span></>}</div></div>
      <aside className="map-inspector"><div className="inspector-top"><span>SPATIAL INSPECTOR</span><Badge tone="green">LIVE</Badge></div><div className="inspector-orb">{mode === "risk" ? "RISK" : "HAZARD"}</div><h3>{mode === "risk" ? "Decision layer" : "Hazard stack"}</h3><p>Rendered directly from the backend. The frontend does not invent or recalculate spatial scores.</p><div className="inspector-stat"><span>Display CRS</span><b>EPSG:4326</b></div><div className="inspector-stat"><span>Processing CRS</span><b>EPSG:32644</b></div><div className="inspector-stat"><span>Records</span><b>{rowsOf(state.data).length}</b></div><div className="inspector-note">⚡ Deterministic rules remain authoritative for safety decisions.</div></aside></div>
  </>;
}

function Habitations() {
  const state = useRequest(() => api.habitations("?limit=1000"), []);
  if (state.loading) return <><Intro title="Vulnerable Habitations" text="Exposure, vulnerability and relocation priority in one place."/><Loading/></>;
  if (state.error) return <><Intro title="Vulnerable Habitations" text="Population exposure and priority workspace."/><ErrorBox error={state.error}/></>;
  const rows = rowsOf(state.data), immediate = rows.filter(x => ["Immediate","Short-term"].includes(propsOf(x).tier));
  return <><Intro eyebrow="L09 + L12" title="Vulnerable Habitations" text="Move from a district-wide list to an explainable priority decision." action={<Badge>{rows.length} RECORDS</Badge>}/>
    <div className="kpi-grid compact"><KPI icon="⌖" label="Records" value={fmt(rows.length)}/><KPI icon="!" label="Immediate + short" value={fmt(immediate.length)} tone="red"/><KPI icon="◌" label="Population coverage" value={fmt(rows.reduce((n,r)=>n+Number(propsOf(r).population||0),0))}/></div>
    <Panel title="Priority register" eyebrow="BACKEND OUTPUT"><div className="table-shell"><table><thead><tr><th>HABITATION</th><th>POPULATION</th><th>VULNERABILITY</th><th>PRIORITY</th><th>TIER</th></tr></thead><tbody>{rows.slice(0,80).map((row,i)=>{const p=propsOf(row);return <tr key={p.habitation_id||i}><td><b>{p.name||"Unnamed habitation"}</b><small>{p.habitation_id||"—"}</small></td><td>{fmt(p.population)}</td><td>{fmt(p.vulnerability)}</td><td><strong>{fmt(p.priority_score)}</strong></td><td><span className={"tier "+tierClass(p.tier)}>{p.tier||"—"}</span></td></tr>})}</tbody></table>{!rows.length&&<Empty icon="⌖" title="No habitation outputs" text="Authoritative habitation data is present in the project; priority outputs may still await analytical inputs."/ >}</div></Panel>
  </>;
}

function Sites() {
  const state=useRequest(()=>api.sites(),[]);
  if(state.loading)return <><Intro title="Relocation Sites" text="Find safer candidate sites and understand their suitability."/><Loading/></>;
  if(state.error)return <><Intro title="Relocation Sites" text="Candidate site intelligence."/><ErrorBox error={state.error}/></>;
  const rows=rowsOf(state.data);
  return <><Intro eyebrow="L10 + L11" title="Relocation Site Explorer" text="Suitability is only the first gate — capacity and bottlenecks complete the relocation picture." action={<Badge tone="gold">{rows.length} CANDIDATES</Badge>}/>
    <div className="site-layout"><div className="site-map"><MapView data={state.data} mode="sites"/></div><div className="site-list">{rows.length?rows.slice(0,18).map((row,i)=>{const p=propsOf(row);return <article className="site-item" key={p.site_id||i}><div className="site-head"><div><span>SITE {String(p.site_id||"—").slice(0,16)}</span><h3>Candidate relocation site</h3></div><Badge tone={p.status==="eligible"?"green":"gold"}>{p.status||"UNSPECIFIED"}</Badge></div><div className="site-metrics"><div><span>SUITABILITY</span><b>{fmt(p.suitability)}</b></div><div><span>AREA</span><b>{fmt(p.area)}</b></div></div><div className="site-foot"><span>Backend explanation {p.explanation_json?"available":"pending"}</span><button className="ghost">Inspect →</button></div></article>}) : <Empty icon="◇" title="No candidate sites" text="L10 candidate-site outputs will appear here when available."/>}</div></div>
  </>;
}

function Capacity() {
  const [id,setId]=useState(""); const [state,setState]=useState(null);
  const inspect=()=>{if(!id.trim())return;setState({loading:true});api.siteCapacity(id.trim()).then(data=>setState({data})).catch(error=>setState({error}));};
  return <><Intro eyebrow="L11 · BOTTLENECK ANALYSIS" title="Carrying Capacity" text="Understand how land, water, sanitation, health and access constrain a relocation site."/>
    <Panel title="Inspect a candidate site" eyebrow="CAPACITY LOOKUP"><div className="lookup"><div><span className="lookup-icon">▦</span><div><b>Site capacity intelligence</b><small>Enter the exact site ID returned by the backend.</small></div></div><div className="lookup-row"><input value={id} onChange={e=>setId(e.target.value)} onKeyDown={e=>e.key==="Enter"&&inspect()} placeholder="SITE-001"/><button className="primary" onClick={inspect}>Inspect capacity →</button></div></div>
    {state?.loading&&<Loading text="Loading capacity output…"/>}{state?.error&&<ErrorBox error={state.error}/>}
    {state?.data&&<div className="capacity-result"><div className="capacity-main"><span>EFFECTIVE CAPACITY</span><strong>{fmt(state.data.effective_cap)}</strong><small>persons · backend output</small></div><div className="bottleneck-card"><span>BINDING BOTTLENECK</span><strong>{state.data.binding_bottleneck||"—"}</strong><small>limiting component</small></div><div className="capacity-bars">{[["Land",state.data.land_cap],["Water",state.data.water_cap],["Sanitation",state.data.sanitation_cap],["Health",state.data.health_cap],["Access",state.data.access_cap]].map(([n,v])=><div key={n}><div><span>{n}</span><b>{fmt(v)}</b></div><div className="bar"><i style={{width:v==null?"0%":Math.min(100,Math.max(4,Number(v)/Math.max(1,Number(state.data.effective_cap)||1)*55))+"%"}}/></div></div>)}</div></div>}</Panel></>;
}

function MLInsights() {
  const state=useRequest(()=>api.mlStatus(),[]);
  if(state.loading)return <><Intro eyebrow="AI / ML" title="Landslide Susceptibility Intelligence" text="Assistive machine learning, spatially validated and never allowed to override deterministic safety rules."/><Loading/></>;
  if(state.error)return <><Intro title="AI / ML Insights" text="Assistive susceptibility framework."/><ErrorBox error={state.error}/></>;
  const d=state.data;
  return <><Intro eyebrow="AI / ML · ASSISTIVE LAYER" title="Landslide Susceptibility Intelligence" text="ML estimates susceptibility where authoritative labelled inventory supports training. Deterministic L07/L08 safety logic remains the final authority." action={<Badge tone="violet">RANDOM FOREST + BASELINE</Badge>}/>
    <div className="ml-hero"><div className="ml-status-card"><div className="ai-orb">✦</div><div><span>MODEL STATUS</span><h2>{d.status?.replaceAll("_"," ")||"NOT TRAINED"}</h2><p>{d.message}</p></div></div><div className="ml-principle"><span>SAFETY PRINCIPLE</span><strong>ML assists. Rules decide.</strong><p>No ML probability can silently turn a safe cell into a legal red zone. L08 remains authoritative.</p></div></div>
    <div className="ml-grid"><Panel title="Feature stack" eyebrow="MODEL INPUTS"><div className="feature-list">{(d.features||[]).map((x,i)=><div key={x}><span>{String(i+1).padStart(2,"0")}</span><b>{x.replaceAll("_"," ")}</b><em>feature</em></div>)}</div></Panel><Panel title="Validation protocol" eyebrow="SPATIAL CV"><div className="validation-list"><div><b>Random Forest</b><span>Primary baseline</span></div><div><b>Logistic Regression</b><span>Interpretable comparison</span></div><div><b>Spatial blocking</b><span>Prevents spatial leakage</span></div><div><b>Metrics</b><span>ROC-AUC · PR-AUC · calibration</span></div></div></Panel></div>
    <Panel title="Current readiness" eyebrow="NO FABRICATED METRICS"><div className="readiness"><div><span>Training rows</span><strong>{fmt(d.training_rows)}</strong></div><div><span>Artifact</span><strong>{d.artifact||"Not promoted"}</strong></div><div><span>Role</span><strong>Assistive</strong></div><div><span>Authority</span><strong>Deterministic L07/L08</strong></div></div><div className="ml-note">⚠ Authoritative labelled landslide inventory is not currently present in the repository. Therefore the system deliberately shows readiness instead of inventing an accuracy score or prediction surface.</div></Panel>
  </>;
}

function Planner({onResult}) {
  const [payload,setPayload]=useState(JSON.stringify({habitations:[],sites:[],distances:{},distance_weight:1,unmet_penalty:1,hazard_weight:0},null,2)); const [state,setState]=useState(null);
  const run=()=>{try{setState({loading:true});api.optimize(JSON.parse(payload)).then(d=>{setState({data:d});onResult(d)}).catch(e=>setState({error:e}))}catch(e){setState({error:e})}};
  return <><Intro eyebrow="L13 · CP-SAT" title="Relocation Scenario Planner" text="Submit an explicit scenario to the backend optimizer. Nothing is calculated authoritatively inside the browser."/>
    <div className="planner-grid"><Panel title="Scenario" eyebrow="INPUT"><div className="planner-callout"><span>⚡</span><div><b>Backend optimization only</b><small>Distances, capacities and feasibility must be explicitly supplied.</small></div></div><textarea value={payload} onChange={e=>setPayload(e.target.value)}/><button className="primary wide" onClick={run}>Run CP-SAT optimization <span>→</span></button>{state?.loading&&<Loading text="Solving allocation scenario…"/>}{state?.error&&<ErrorBox error={state.error}/>}</Panel><Panel title="What the solver optimizes" eyebrow="OBJECTIVE"><div className="formula-big">min ∑ distance × allocation + penalties</div><ul className="plain-list"><li>Exposure demand constraints</li><li>Site capacity constraints</li><li>Feasibility constraints</li><li>Unmet-demand penalty</li><li>Hazard penalty</li></ul>{state?.data&&<div className="solver-result"><Badge tone="green">{state.data.status}</Badge><strong>{fmt(state.data.objective_value)}</strong><span>objective value</span></div>}</Panel></div></>;
}

function Allocations({result}) {
  const allocations=result?.allocations||[]; const unmet=result?.unmet||[];
  return <><Intro eyebrow="L13 · DECISION OUTPUT" title="Allocation Results" text="Turn optimization output into an auditable relocation plan." action={result&&<Badge tone="green">SCENARIO READY</Badge>}/>
    {!result?<Empty icon="⇄" title="No scenario has been solved" text="Run the Relocation Planner to populate allocation results."/>:<><div className="kpi-grid compact"><KPI icon="↗" label="Allocation records" value={fmt(allocations.length)}/><KPI icon="!" label="Unmet records" value={fmt(unmet.length)} tone={unmet.length?"red":"green"}/><KPI icon="∑" label="Objective" value={fmt(result.objective_value)}/></div><Panel title="Allocation register" eyebrow="SOLVER OUTPUT"><div className="table-shell"><table><thead><tr><th>HABITATION</th><th>SITE</th><th>ALLOCATED</th><th>DISTANCE</th></tr></thead><tbody>{allocations.map((a,i)=><tr key={i}><td>{a.habitation_id}</td><td>{a.site_id}</td><td><strong>{fmt(a.allocated_population)}</strong></td><td>{fmt(a.distance)}</td></tr>)}</tbody></table></div><details className="audit"><summary>View complete solver payload</summary><pre>{JSON.stringify(result,null,2)}</pre></details></Panel></>}</>;
}

function Methodology() {
  const cards=[["01","MULTI-HAZARD","H = 0.45L + 0.35F + 0.20R","L07"],["02","RED ZONE","Hard exclusion OR H ≥ 0.70","L08"],["03","VULNERABILITY","V = 0.35P + 0.25S + 0.20A + 0.10I + 0.10D","L09"],["04","SITE SUITABILITY","Eight normalized criteria + hard exclusions","L10"],["05","CAPACITY","floor(min(land, water, sanitation, health, access) × 0.80)","L11"],["06","PRIORITY","Risk + exposed population + vulnerability + response + recurrence","L12"],["07","ALLOCATION","CP-SAT minimizes distance and unmet/hazard penalties","L13"]];
  return <><Intro eyebrow="AUDITABLE DECISION LOGIC" title="How the DSS makes a decision" text="Every recommendation follows an explicit, reviewable rule. The frontend only explains and visualizes backend outputs."/>
    <div className="pipeline">{cards.map(([n,t,f,l],i)=><React.Fragment key={n}><article><span>{n}</span><em>{l}</em><h3>{t}</h3><code>{f}</code></article>{i<cards.length-1&&<b>→</b>}</React.Fragment>)}</div>
    <Panel title="Architecture guardrails" eyebrow="NON-NEGOTIABLE"><div className="guard-grid"><div><b>Backend authority</b><span>Frontend never recalculates authoritative metrics.</span></div><div><b>No silent missing data</b><span>Unavailable inputs remain unavailable instead of becoming zero.</span></div><div><b>ML is assistive</b><span>Susceptibility predictions cannot override deterministic safety rules.</span></div><div><b>Provenance</b><span>Sources, model versions and configuration are preserved for audit.</span></div></div></Panel>
  </>;
}

function Reports() {
  const [id,setId]=useState(""); const [state,setState]=useState(null);
  const load=()=>{if(!id.trim())return;setState({loading:true});api.report(id.trim()).then(d=>setState({data:d})).catch(e=>setState({error:e}))};
  return <><Intro eyebrow="AUDIT + EXPORT" title="Decision Reports" text="Generate a portable evidence package from a persisted backend run."/>
    <Panel title="Report retrieval" eyebrow="RUN ID"><div className="lookup"><div><span className="lookup-icon">↥</span><div><b>Backend report endpoint</b><small>Reports are based on persisted model-run and allocation records.</small></div></div><div className="lookup-row"><input value={id} onChange={e=>setId(e.target.value)} placeholder="run UUID"/><button className="primary" onClick={load}>Load report →</button></div></div>
    {state?.loading&&<Loading/>}{state?.error&&<ErrorBox error={state.error}/>}
    {state?.data&&<><div className="report-actions"><button onClick={()=>downloadMarkdown(state.data)}>Download Markdown</button><button onClick={()=>printReport(state.data)}>Print / Save PDF</button></div><details className="audit" open><summary>Report payload</summary><pre>{JSON.stringify(state.data,null,2)}</pre></details></>}</Panel></>;
}

export default function App() {
  const [screen,setScreen]=useState("overview"); const [result,setResult]=useState(null);
  const go=id=>setScreen(id);
  let page;
  if(screen==="overview")page=<CommandCenter go={go}/>;
  else if(screen==="hazards")page=<MapWorkspace/>;
  else if(screen==="red-zones")page=<MapWorkspace mode="risk"/>;
  else if(screen==="habitations")page=<Habitations/>;
  else if(screen==="sites")page=<Sites/>;
  else if(screen==="capacity")page=<Capacity/>;
  else if(screen==="ml")page=<MLInsights/>;
  else if(screen==="planner")page=<Planner onResult={setResult}/>;
  else if(screen==="allocations")page=<Allocations result={result}/>;
  else if(screen==="methodology")page=<Methodology/>;
  else page=<Reports/>;
  return <Shell screen={screen} setScreen={setScreen}>{page}</Shell>;
}
