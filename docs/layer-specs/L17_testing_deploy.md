# L17 — Testing, Deployment & Final Audit

## Purpose

L17 is the release-readiness layer for the 17-layer SIH 26191 prototype. It does not introduce new analytical formulas, datasets, ML models, or decision rules. It verifies that the already-frozen L01–L16 contracts remain testable and deployable.

## Scope

1. Automated backend verification with `python -m pytest -q`.
2. Frontend verification with `npm run build`.
3. Docker verification for the Python backend, React frontend, health check, and Compose configuration.
4. CI verification for backend tests, frontend build, and Compose validation.
5. Final audit for silent install failures, invalid entrypoints, backend authority, and documented data limitations.

## Required local verification

From the repository root:

```powershell
python -m pytest -q
docker compose config
docker compose build backend frontend
```

Then:

```powershell
docker compose up -d
curl http://localhost:8000/health
```

Expected health payload:

```json
{"status":"ok","service":"sih-26191-relocation-dss","api_version":"1.0"}
```

Frontend production verification:

```powershell
cd frontend
npm install
npm run build
```

## Acceptance criteria

- Full backend test suite passes locally.
- Frontend production build succeeds.
- Compose configuration parses.
- Docker install steps do not hide dependency failures with `|| true`.
- Backend Docker entrypoint targets `src.api.app:app`.
- CI contains backend-test, frontend-build, and Compose-validation jobs.
- No new authoritative analytical assumptions are introduced.

A successful L17 audit does not mean real Chamoli hazard outputs are available. The absence of authoritative L04–L06 hazard inputs remains a documented data-readiness limitation.
