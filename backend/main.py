import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.neo4j_service import neo4j_service
from routers import vapi_tools, vapi_webhook, tasks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("LifePilot backend starting up")
    neo4j_service.connect()
    if neo4j_service.available:
        neo4j_service.seed_demo_data()
    yield
    # Shutdown
    neo4j_service.close()
    logger.info("LifePilot backend shut down")


app = FastAPI(
    title="LifePilot Backend",
    description="Backend for LifePilot voice agent — handles Vapi webhooks, tool calls, task management, and SSE streaming.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow dashboard frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Routers
app.include_router(vapi_tools.router, tags=["Vapi Tools"])
app.include_router(vapi_webhook.router, tags=["Vapi Webhooks"])
app.include_router(tasks.router, tags=["Tasks"])


@app.get("/")
async def root():
    return {
        "service": "LifePilot Backend",
        "status": "running",
        "neo4j": "connected" if neo4j_service.available else "not configured",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
