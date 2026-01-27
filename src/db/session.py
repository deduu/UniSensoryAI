from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from contextlib import asynccontextmanager
import os
from typing import Optional, AsyncGenerator

class DatabaseSessionManager:
    def __init__(self, write_url: str, read_url: Optional[str] = None):
        if not write_url:
             raise ValueError("write_url is required")

        self.write_engine = create_async_engine(
            write_url,
            pool_pre_ping=True,
            pool_size=20,
            max_overflow=10,
            pool_recycle=3600,
        )
        
        self.read_engine = create_async_engine(
            read_url or write_url,
            pool_pre_ping=True,
            pool_size=10,
        )
        
        self.write_session_factory = async_sessionmaker(
            bind=self.write_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        
        self.read_session_factory = async_sessionmaker(
            bind=self.read_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def session(self, read_only: bool = False) -> AsyncGenerator[AsyncSession, None]:
        """IMPORTANT: Caller is responsible for commit/rollback"""
        factory = self.read_session_factory if read_only else self.write_session_factory
        session = factory()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Global instance
session_manager: Optional[DatabaseSessionManager] = None

def init_db(write_url: str, read_url: Optional[str] = None) -> None:
    global session_manager
    session_manager = DatabaseSessionManager(write_url, read_url)

async def get_db(read_only: bool = False) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency or general usage"""
    if session_manager is None:
        raise RuntimeError("DatabaseSessionManager is not initialized")
    async with session_manager.session(read_only=read_only) as session:
        yield session
