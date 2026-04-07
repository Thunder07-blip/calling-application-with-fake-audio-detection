from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from database import init_db
from routes.companies import router as companies_router
from routes.calls import router as calls_router
from routes.auth import router as token_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("backend_api")

app = FastAPI(
    title="Safe Call Platform API",
    description="Multi-tenant WebRTC calling platform with AI-based audio safety monitoring.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(companies_router)
app.include_router(calls_router)
app.include_router(token_router)


print("🔥 FASTAPI STARTED INITIALIZING")

@app.on_event("startup")
def on_startup():
    print("🚀 APP STARTED SUCCESSFULLY IN ON_STARTUP", flush=True)
    logger.info("Starting Safe Call API — initialising database tables...")
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}
