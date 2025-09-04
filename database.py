from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
import os

Base = declarative_base()

# Database Models
class UserEntry(Base):
    __tablename__ = "user_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    roll_number = Column(String, index=True)
    name = Column(String)
    date = Column(String)
    time = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ShaftMeasurement(Base):
    __tablename__ = "shaft_measurements"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String, unique=True, index=True)
    roll_number = Column(String, index=True)
    shaft_height = Column(Float)
    shaft_radius = Column(Float)
    measurement_timestamp = Column(DateTime(timezone=True), nullable=True)  # When measurement was taken
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # When record was created

class HousingMeasurement(Base):
    __tablename__ = "housing_measurements"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String, unique=True, index=True)
    roll_number = Column(String, index=True)
    housing_type = Column(String)
    depth = Column(Float)
    radius = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    measurement_timestamp = Column(DateTime(timezone=True), nullable=True)  # When measurement was taken
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # When record was created

# Database connection
def get_database_url():
    """Get database URL from environment or default"""
    database_url = os.environ.get("DATABASE_URL")
    if database_url and database_url.startswith("postgres://"):
        # Heroku provides postgres:// but SQLAlchemy needs postgresql://
        database_url = database_url.replace("postgres://", "postgresql://")
    return database_url or "sqlite:///./local_test.db"

def create_database_engine():
    """Create database engine"""
    database_url = get_database_url()
    if database_url.startswith("postgresql://"):
        engine = create_engine(database_url)
    else:
        engine = create_engine(database_url, connect_args={"check_same_thread": False})
    return engine

def get_db_session():
    """Get database session"""
    engine = create_database_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

def init_database():
    """Initialize database tables"""
    engine = create_database_engine()
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")
