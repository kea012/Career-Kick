"""
Database Configuration Module
=============================

This module centralizes the connection logic and session management for 
the application's data persistence layer. 

Career Kick utilizes a split-database architecture:
1. Member Database: Stores professional profiles and user identity.
2. Jobs Database: Stores job listings crawled from external sources.

This separation ensures that high-volume job data operations do not 
impact the performance or availability of critical user profile services.
"""
import os
import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

# --- Base Configuration ---
# The Base class provides the foundation for SQLAlchemy's ORM models.
Base = declarative_base()

# --- Member Database Configuration ---
# Configuration for the database containing user professional profiles.
MEMBERS_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://kennethea:postgres@localhost:5432/career_kick_test",
)
members_engine = create_async_engine(MEMBERS_DATABASE_URL, echo=False)
MemberSessionLocal = async_sessionmaker(
    members_engine, expire_on_commit=False, class_=AsyncSession
)

# --- Jobs Database Configuration ---
# Configuration for the database containing job listings.
# Optimized with a larger pool size to handle high-concurrency crawling.
JOBS_DATABASE_URL = os.getenv(
    "JOBS_DATABASE_URL",
    "postgresql+asyncpg://kennethea:postgres@localhost:5432/career_kick_jobs",
)
jobs_engine = create_async_engine(
    JOBS_DATABASE_URL, pool_size=20, max_overflow=10, pool_recycle=3600
)
JobsSessionLocal = async_sessionmaker(
    jobs_engine, expire_on_commit=False, class_=AsyncSession
)


async def get_member_session() -> AsyncIterator[AsyncSession]:
    """
    FastAPI Dependency: Provides an isolated member database session.
    
    This generator ensures that sessions are properly opened and closed 
    per request, preventing connection leaks.
    """
    async with MemberSessionLocal() as session:
        yield session


async def get_jobs_session() -> AsyncIterator[AsyncSession]:
    """
    FastAPI Dependency: Provides an isolated jobs database session.
    
    This generator ensures that sessions are properly opened and closed 
    per request, preventing connection leaks.
    """
    async with JobsSessionLocal() as session:
        yield session
