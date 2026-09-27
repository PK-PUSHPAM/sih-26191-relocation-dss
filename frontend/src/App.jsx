import React, { useEffect, useMemo, useState } from "react";
import { api, API_BASE } from "./api";
import { downloadMarkdown, printReport } from "./export";
import MapView from "./map/MapView";

const SCREENS = [
  ["overview","Overview"],["hazards","Hazard Map"],["red-zones","Red Zone Map"],
  ["habitations","Habitation Risk"],["sites","Site Explorer"],["capacity","Capacity Dashboard"],
  ["planner","Relocation Planner"],["allocations","Allocation Results"],
  ["methodology","Methodology"],["reports","Reports Export"],
];

function useApi(loader) {
  const [state,setState]=useState({loading:true,data:null,error:null});
  useEffect(()=>{let alive=true; setState({loading:true,data:null,error:null}); loader().then(data=>alive&&setState({loading:false,data,error:null})).catch(error=>alive&&setState({loading:false,data:null,error})); return()=>{alive=false};},[loader]);
  return state;
}
function Panel({title,children,actions}){return <section className="panel"><div className="panel-head"><h2>{title}</h2>{actions}</div>{children}</section>}
function State({state}){if(state.loading)return <div className="state">Loading authoritative backend data…</div>;if(state.error)return <div className="state error">Backend unavailable: {state.error.message}</div>;return null}
function JsonList({data}){return <pre className="json">{JSON.stringify(data,null,2)}</pre>}

function Overview(){
 const state=useApi(React.useCallback(()=>api.habitations(),[]));
 return <><PageIntro title="Overview" text="Chamoli District relocation decision-support overview. Authoritative metrics remain backend-owned."/><State state={state}/>{state.data&&<div className="cards">
   <Metric label="Habitations returned" value={Array.isArray(state.data)?state.data.length:(state.data.items?.length ?? "—")}/>
   <Metric label="API" value={API_BASE}/>
   <Metric label="CRS" value="EPSG:4326 display / EPSG:32644 analysis"/>
 </div>}<Panel title="Data status"><p className="muted">No fabricated summary metrics are shown when the backend does not provide them.</p></Panel></>
}
function Metric({label,value}){return <div className="metric"><span>{label}</span><strong>{value}</strong></div>}
function PageIntro({title,text}){return <div className="intro"><div><div className="eyebrow">SIH 26191 · CHAMOLI DSS</div><h1>{title}</h1><p>{text}</p></div></div>}
function GeoScreen({title,text,loader,mode}){const state=useApi(loader);return <><PageIntro title={title} text={text}/><State state={state}/>{state.data&&<div className="map-grid"><Panel title="Spatial view"><MapView data={state.data} mode={mode}/></Panel><Panel title="Backend payload"><JsonList data={state.data}/></Panel></div>}</>}
function Habitations(){const state=useApi(React.useCallback(()=>api.habitations(),[]));return <><PageIntro title="Habitation Risk" text="Search and inspect habitation vulnerability and priority data returned by the API."/><State state={state}/>{state.data&&<Panel title="Habitations"><JsonList data={state.data}/></Panel>}</>}
function Sites(){const state=useApi(React.useCallback(()=>api.sites(),[]));return <><PageIntro title="Site Explorer" text="Candidate relocation sites and suitability values are displayed exactly as supplied by the backend."/><State state={state}/>{state.data&&<Panel title="Candidate sites"><JsonList data={state.data}/></Panel>}</>}
function Capacity(){const [id,setId]=useState("");const [state,setState]=useState(null);return <><PageIntro title="Capacity Dashboard" text="Inspect the five capacity components and the binding bottleneck for a selected site."/><Panel title="Site capacity lookup"><div className="form-row"><input value={id} onChange={e=>setId(e.target.value)} placeholder="site_id"/><button onClick={()=>{if(!id)return;setState({loading:true});api.siteCapacity(id).then(data=>setState({data})).catch(error=>setState({error}))}}>Load</button></div>{state?.loading&&<div className="state">Loading…</div>}{state?.error&&<div className="state error">{state.error.message}</div>}{state?.data&&<JsonList data={state.data}/>}</Panel></>}
function Planner({onResult}){const [payload,setPayload]=useState('{"habitations":[],"sites":[],"distances":{},"distance_weight":1,"unmet_penalty":1,"hazard_weight":0}');const [state,setState]=useState(null);return <><PageIntro title="Relocation Planner" text="Scenario sandbox. The frontend submits inputs; L13 remains the sole optimization authority."/><Panel title="Optimization scenario"><textarea value={payload} onChange={e=>setPayload(e.target.value)}/><button onClick={()=>{try{setState({loading:true});api.optimize(JSON.parse(payload)).then(data=>{setState({data});onResult(data)}).catch(error=>setState({error}))}catch(error){setState({error})}}}>Run scenario</button>{state?.loading&&<div className="state">Running backend optimization…</div>}{state?.error&&<div className="state error">{state.error.message}</div>}{state?.data&&<JsonList data={state.data}/>}</Panel></>}
function Allocations({result}){return <><PageIntro title="Allocation Results" text="Displays the most recent optimization response without recalculating allocations."/><Panel title="Scenario result">{result?<JsonList data={result}/>:<div className="state">Run a scenario in Relocation Planner to view its result here.</div>}</Panel></>}
function Methodology(){return <><PageIntro title="Methodology" text="Transparent display of frozen decision rules and formulas."/><Panel title="Authoritative formulas"><div className="formula-list"><code>H = 0.45L + 0.35F + 0.20R</code><code>V = 0.35P + 0.25S + 0.20A + 0.10I + 0.10D</code><code>Effective Capacity = floor(min(land, water, sanitation, health, access) × 0.80)</code><code>RP = 0.40 Risk + 0.25 Exposed Pop + 0.20 V + 0.10 Response Difficulty + 0.05 Recurrence</code></div><p className="muted">The dashboard is visualization-only; authoritative scoring and optimization execute in the backend.</p></Panel></>}
function Reports(){const [id,setId]=useState("");const [state,setState]=useState(null);return <><PageIntro title="Reports Export" text="Retrieve a backend decision report and export it as Markdown or print it to PDF using the browser."/><Panel title="Run report"><div className="form-row"><input value={id} onChange={e=>setId(e.target.value)} placeholder="run_id"/><button onClick={()=>id&&api.report(id).then(data=>setState({data})).catch(error=>setState({error}))}>Load report</button></div>{state?.error&&<div className="state error">{state.error.message}</div>}{state?.data&&<><div className="actions"><button onClick={()=>downloadMarkdown(state.data)}>Download Markdown</button><button onClick={()=>printReport(state.data)}>Print / Save PDF</button></div><JsonList data={state.data}/></>}</Panel></>}
function App(){
 const [screen,setScreen]=useState(()=>location.hash.slice(1)||"overview"); const [result,setResult]=useState(null);
 useEffect(()=>{const fn=()=>setScreen(location.hash.slice(1)||"overview");addEventListener("hashchange",fn);return()=>removeEventListener("hashchange",fn)},[]);
 const content=useMemo(()=>{switch(screen){
 case"hazards":return <GeoScreen title="Hazard Map" text="Multi-hazard spatial layers from the backend." loader={api.hazards} mode="hazards"/>;
 case"red-zones":return <GeoScreen title="Red Zone Map" text="Risk cells and modeled red-zone classifications from the backend." loader={api.riskMap} mode="risk"/>;
 case"habitations":return <Habitations/>; case"sites":return <Sites/>; case"capacity":return <Capacity/>;
 case"planner":return <Planner onResult={setResult}/>; case"allocations":return <Allocations result={result}/>; case"methodology":return <Methodology/>; case"reports":return <Reports/>; default:return <Overview/>;}},[screen,result]);
 return <div className="app-shell"><aside><div className="brand"><span className="brand-mark">◆</span><div><strong>CHAMOLI DSS</strong><small>SIH 26191</small></div></div><nav>{SCREENS.map(([id,label])=><a key={id} href={"#"+id} className={screen===id?"active":""}>{label}</a>)}</nav><div className="side-note">Modeled decision support<br/>Not a legal notification.</div></aside><main><header><span>Relocation Decision Support System</span><span className="status-dot">Backend authoritative</span></header>{content}</main></div>
}
export default App;
