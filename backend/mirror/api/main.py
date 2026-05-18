from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mirror.api.routes import agents, blue_findings, calibration, events, forecasts, health, lineage, onchain, patches, stream, trades
from mirror.config import get_settings

app = FastAPI(title="MIRROR API")
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(agents.router)
app.include_router(blue_findings.router)
app.include_router(forecasts.router)
app.include_router(trades.router)
app.include_router(patches.router)
app.include_router(calibration.router)
app.include_router(lineage.router)
app.include_router(onchain.router)
app.include_router(events.router)
app.include_router(stream.router)
