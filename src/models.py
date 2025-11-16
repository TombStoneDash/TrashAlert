"""
Database models for TrashAlert.

Defines the database schema for addresses and trash collection schedules.
"""

from sqlalchemy import Column, Integer, String, Float, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class Address(Base):
    """
    Address model for storing normalized addresses with trash collection info.
    """
    __tablename__ = 'addresses'

    id = Column(Integer, primary_key=True, index=True)
    house_number = Column(String, nullable=False)
    street = Column(String, nullable=False)
    city = Column(String, nullable=False)
    subdivision_id = Column(String, nullable=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    normalized_address = Column(String, nullable=False, index=True)
    trash_day_of_week = Column(String, nullable=True)  # e.g., "Monday", "Tuesday"
    osm_id = Column(String, nullable=True)

    def __repr__(self):
        return f"<Address(id={self.id}, address='{self.normalized_address}', trash_day='{self.trash_day_of_week}')>"


def create_database(database_url: str = "sqlite:///./trashalert.db"):
    """
    Create the database and tables.

    Args:
        database_url: Database connection URL

    Returns:
        Tuple of (engine, SessionLocal)
    """
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    return engine, SessionLocal


def get_db_session(SessionLocal):
    """
    Get a database session with automatic cleanup.

    Args:
        SessionLocal: Session factory

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
