"""資料庫設定 — 支援 SQLite（本地）與 PostgreSQL（Railway）"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


def _get_database_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if url:
        return url
    h = os.getenv("PGHOST", "")
    p = os.getenv("PGPORT", "5432")
    u = os.getenv("PGUSER", "")
    k = os.getenv("PGPASSWORD", "")
    d = os.getenv("PGDATABASE", "railway")
    if h and u and k:
        auth = u + chr(58) + k + chr(64)
        return "postgresql://" + auth + h + ":" + p + "/" + d
    return ""


_database_url = _get_database_url()

if _database_url:
    engine = create_engine(_database_url, connect_args={}, pool_pre_ping=True)
else:
    _db_path = os.path.join(os.path.dirname(__file__), "line_broadcast.db")
    engine = create_engine(f"sqlite:///{_db_path}", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def init_db():
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
