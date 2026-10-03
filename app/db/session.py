"""
Database engine + session handling.

Synchronous SQLAlchemy, not async -- deliberate: the bottleneck in this
system is LLM API latency, not DB I/O, so async DB access adds complexity
for no real benefit here.
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL not set. Check your .env file has the Supabase "
        "direct connection string (port 5432)."
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,   # avoids stale-connection errors -- Supabase closes
                            # idle connections, and without this you'll get
                            # intermittent failures under low traffic
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency: yields a DB session, closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()