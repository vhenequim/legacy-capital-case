from datetime import datetime

from sqlalchemy import Column, DateTime, Float, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from legacy_retrieval.config import get_settings


class Base(DeclarativeBase):
    pass


class TimeSeriesPoint(Base):
    __tablename__ = "time_series"

    id = Column(String, primary_key=True)
    company = Column(String, index=True)
    metric = Column(String, index=True)
    period = Column(String, index=True)
    value = Column(Float)
    source = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


def get_engine():
    settings = get_settings()
    return create_engine(settings.database_url)


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)


def get_session() -> Session:
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def store_metric(company: str, metric: str, period: str, value: float, source: str) -> None:
    try:
        init_db()
        session = get_session()
        point_id = f"{company}_{metric}_{period}"
        existing = session.get(TimeSeriesPoint, point_id)
        if existing:
            existing.value = value
        else:
            session.add(
                TimeSeriesPoint(
                    id=point_id,
                    company=company,
                    metric=metric,
                    period=period,
                    value=value,
                    source=source,
                )
            )
        session.commit()
        session.close()
    except Exception:
        pass
