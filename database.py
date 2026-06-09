"""資料庫設定 — 支援 SQLite（本地）與 PostgreSQL（Railway）"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Railway 會提供 DATABASE_URL 環境變數（PostgreSQL）
# 本地開發用 SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "")

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
