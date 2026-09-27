# L16 — Interactive Dashboard & Decision Reports

## Scope
L16 implements the React + MapLibre presentation layer defined by the frozen architecture. It is visualization-only: no authoritative risk, vulnerability, capacity, priority, or optimization calculations are performed in the browser.

## Required screens
1. Overview — study-area summary and backend status.
2. Hazard Map — hazard-layer spatial view.
3. Red Zone Map — modeled risk/red-zone spatial view.
4. Habitation Risk — habitation data inspection.
5. Site Explorer — candidate sites and suitability.
6. Capacity Dashboard — site capacity/bottleneck inspection.
7. Relocation Planner — submits scenario inputs to L15/L13.
8. Allocation Results — displays optimization output.
9. Methodology — frozen formulas and system boundaries.
10. Reports Export — backend report retrieval, Markdown download, browser print/PDF.

## Contracts
- API base defaults to http://localhost:8000 and can be overridden with VITE_API_BASE_URL.
- API responses are treated as authoritative; frontend does not recompute metrics.
- API/display spatial data is consumed as GeoJSON; MapLibre GL JS provides the map view.
- Report export does not invent or alter decision metrics. Markdown serializes the backend report payload; PDF is produced through the browser print flow.
- Backend errors are surfaced to the user rather than converted into empty/fabricated results.
- Canonical analysis CRS remains EPSG:32644; API/display GeoJSON is EPSG:4326.

## Verification
- Frontend dependency installation and production build: npm install then npm run build.
- Python suite remains authoritative for backend layers.
- L16 contract tests verify the ten required screen identifiers, API client routes, report export functions, and MapLibre integration without requiring a browser.
