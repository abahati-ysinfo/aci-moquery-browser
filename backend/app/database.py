import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from .models import Base

DATABASE_URL = "sqlite+aiosqlite:///./data/db.sqlite"

os.makedirs("./data", exist_ok=True)

async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={
        "check_same_thread": False,
    },
    pool_pre_ping=True,
)

sync_engine = create_engine(
    DATABASE_URL.replace("+aiosqlite", ""),
    echo=False,
    connect_args={
        "check_same_thread": False,
    },
)

AsyncSessionLocal = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    async with async_engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA synchronous=NORMAL"))
        await conn.execute(text("PRAGMA temp_store=MEMORY"))
        await conn.execute(text("PRAGMA cache_size=10000"))
        
        await conn.run_sync(Base.metadata.create_all)
