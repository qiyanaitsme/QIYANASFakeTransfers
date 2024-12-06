from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool
from contextlib import asynccontextmanager
from models import Base
import os

DATABASE_URL = "sqlite+aiosqlite:///crypto_wallet.db"

engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    poolclass=AsyncAdaptedQueuePool,
    pool_size=20,
    max_overflow=30
)

async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_models():
    db_file = "crypto_wallet.db"
    if not os.path.exists(db_file):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

@asynccontextmanager
async def get_session():
    session = async_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
