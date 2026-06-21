from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import DateTime, Float, String, Text, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from stock_helper.config import get_settings


class Base(DeclarativeBase):
    pass


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(64))
    headline: Mapped[str] = mapped_column(String(512))
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    tickers: Mapped[str] = mapped_column(String(256), default="")
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    event_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sentiment: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BriefRecord(Base):
    __tablename__ = "brief_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    brief_date: Mapped[str] = mapped_column(String(10), index=True)
    session: Mapped[str] = mapped_column(String(32))
    markdown: Mapped[str] = mapped_column(Text)
    macro_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    snapshot_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChatMemory(Base):
    __tablename__ = "chat_memory"

    chat_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    context: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AgentTracking(Base):
    __tablename__ = "agent_tracking"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    reason: Mapped[str] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class CostLog(Base):
    __tablename__ = "cost_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    node: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    estimated_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AlertRecord(Base):
    __tablename__ = "alert_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dedupe_key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    alert_type: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SystemMeta(Base):
    __tablename__ = "system_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


_LAST_INGEST_KEY = "last_ingest_at"


_engine = None
_Session = None


def get_engine():
    global _engine
    if _engine is None:
        url = get_settings().database_url
        if url.startswith("sqlite"):
            db_path = url.replace("sqlite:///", "")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, echo=False)
        Base.metadata.create_all(_engine)
        _migrate_schema(_engine)
    return _engine


def _migrate_schema(engine) -> None:
    """Add columns to existing SQLite tables when models evolve."""
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if "brief_records" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("brief_records")}
        if "snapshot_json" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE brief_records ADD COLUMN snapshot_json TEXT")
                )


def get_chat_context(chat_id: str | int, max_len: int = 4000) -> str:
    session = get_session()
    row = session.get(ChatMemory, str(chat_id))
    session.close()
    if not row or not row.context:
        return ""
    return row.context[-max_len:]


def save_chat_context(chat_id: str | int, context: str, max_len: int = 4000) -> None:
    trimmed = context[-max_len:]
    session = get_session()
    row = session.get(ChatMemory, str(chat_id))
    if row:
        row.context = trimmed
        row.updated_at = datetime.utcnow()
    else:
        session.add(ChatMemory(chat_id=str(chat_id), context=trimmed))
    session.commit()
    session.close()


def record_ingest_run(source: str = "unknown") -> None:
    session = get_session()
    now = datetime.utcnow()
    row = session.get(SystemMeta, _LAST_INGEST_KEY)
    payload = f"{now.isoformat()}|{source}"
    if row:
        row.value = payload
        row.updated_at = now
    else:
        session.add(SystemMeta(key=_LAST_INGEST_KEY, value=payload))
    session.commit()
    session.close()


def minutes_since_last_ingest() -> float | None:
    session = get_session()
    row = session.get(SystemMeta, _LAST_INGEST_KEY)
    session.close()
    if not row or not row.value:
        return None
    ts_str = row.value.split("|", 1)[0]
    try:
        last = datetime.fromisoformat(ts_str)
    except ValueError:
        return None
    return (datetime.utcnow() - last).total_seconds() / 60.0


def should_skip_ingest(cooldown_minutes: int) -> bool:
    if cooldown_minutes <= 0:
        return False
    elapsed = minutes_since_last_ingest()
    return elapsed is not None and elapsed < cooldown_minutes


def get_session():
    global _Session
    if _Session is None:
        _Session = sessionmaker(bind=get_engine())
    return _Session()
