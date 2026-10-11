import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = None
SessionLocal = None
if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    except Exception as e:
        print(f"[warn] Could not set up database engine; community features disabled: {e}")
        engine = None
        SessionLocal = None
else:
    print("[warn] DATABASE_URL not set; community features disabled.")

Base = declarative_base()