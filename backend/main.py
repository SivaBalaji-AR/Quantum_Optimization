from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from db import init_client, close_client
from routes import router as api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_client()
    yield
    await close_client()

app = FastAPI(title="Quantum Route Optimization API", lifespan=lifespan)

# CORS (adjust origins if you want to lock it down)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # e.g. ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API
app.include_router(api_router, prefix="/api")
