import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional

# Load .env from project root
load_dotenv()

_MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
_MONGO_DB = os.getenv("MONGO_DB", "test_database")

_client: Optional[AsyncIOMotorClient] = None
_db = None

async def init_client():
    global _client, _db
    if _client is None:
        _client = AsyncIOMotorClient(_MONGO_URL)
        _db = _client[_MONGO_DB]

async def get_db():
    if _db is None:
        await init_client()
    return _db

async def close_client():
    global _client
    if _client is not None:
        _client.close()
        _client = None
