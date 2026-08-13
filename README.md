# Helios

Helios is a FastAPI service for monitoring Solis solar telemetry and
simulating Tesla charging decisions. Sprint 1 does not send commands to a
Tesla vehicle.

## Local backend

```bash
source .venv/bin/activate
cd backend
uvicorn app.main:app --reload
```

The health endpoint is `GET /api/v1/health`. Copy `.env.example` to `.env`
and fill in the Solis credentials to enable live, read-only telemetry.

## Container deployment

```bash
docker compose up --build
```

The container listens on `PORT` (default `8000`). Persistent SQLite history
and charging settings live in `DATA_DIR`; the Compose configuration mounts
the `helios-data` volume at `/data`. On a cloud platform, attach a persistent
disk and set `DATA_DIR` to its mount path.

Required production values are `SOLIS_BASE_URL`, `SOLIS_API_KEY_ID`,
`SOLIS_API_SECRET`, and `SOLIS_INVERTER_SN`. Keep
`TESLA_SIMULATION_ONLY=true`; startup intentionally fails if it is disabled.

Deploy a single backend replica while SQLite and in-memory charging-controller
state are in use. A future multi-replica deployment should move persistence
and controller coordination to shared services.
