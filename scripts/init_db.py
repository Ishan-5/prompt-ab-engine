"""
Run this once to create all tables in Supabase.

Usage: python3 scripts/init_db.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import engine
from app.db.models import Base

if __name__ == "__main__":
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Done. Tables created:")
    for table in Base.metadata.tables:
        print(f"  - {table}")