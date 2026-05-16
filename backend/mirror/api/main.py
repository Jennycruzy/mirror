from fastapi import FastAPI

from mirror.api.routes import agents, blue_findings, calibration, forecasts, health, lineage, onchain, patches, stream, trades

app = FastAPI(title="MIRROR API")

app.include_router(health.router)
app.include_router(agents.router)
app.include_router(blue_findings.router)
app.include_router(forecasts.router)
app.include_router(trades.router)
app.include_router(patches.router)
app.include_router(calibration.router)
app.include_router(lineage.router)
app.include_router(onchain.router)
app.include_router(stream.router)
