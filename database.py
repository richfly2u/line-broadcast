"""資料庫設定 — 支援 SQLite（本地）與 PostgreSQL（Railway）"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def _get_database_url() -> str:
    """優先使用 DATABASE_URL，否則從個別 PG 變數組裝，最後回退 SQLite。"""
    url = os.getenv("DATABASE_URL", "")
    if url:
        return url
    pg_host = os.getenv("PGHOST", "")
    pg_port = os.getenv("PGPORT", "5432")
    pg_user = os.getenv("PGUSER", "")
    pg_pass = os.getenv("PGPASSWORD", "")
    pg_db = os.getenv("PGDATABASE", "railway")
    if pg_host and pg_user:
        return f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
    return ""

DATABASE_URL = _get_database_url()

if DATABASE_URL:
    # PostgreSQL（Railway 生產環境）
    engine = create_engine(DATABASE_URL, connect_args={}, pool_pre_ping=True)
else:
    # SQLite（本地開發）
    DB_PATH = os.path.join(os.path.dirname(__file__), "line_broadcast.db")
    engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

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
