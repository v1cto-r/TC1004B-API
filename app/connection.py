import logging
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Generator
from app.settings import settings
import time
from sqlalchemy.exc import OperationalError

# Logger setup
db_logger = logging.getLogger("database")
db_logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
if not db_logger.handlers:
    db_logger.addHandler(stream_handler)

# Base class for SQLAlchemy models
Base = declarative_base()

# Global engine and session factory (cached)
_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    """
    Returns a cached SQLAlchemy engine instance.
    Creates it on first call, reuses it afterward.
    """
    global _engine
    if _engine is None:
        db_logger.info("🔌 Creating database engine...")
        _engine = create_engine(
            settings.database_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Verify connections before using them
            pool_recycle=3600,   # Recycle connections after 1 hour
            echo=False,          # Set to True for SQL query logging
        )
        db_logger.info("✅ Database engine created successfully")
    return _engine


def get_session_factory() -> sessionmaker:
    """
    Returns a cached sessionmaker instance.
    """
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine
        )
        db_logger.info("✅ Session factory created")
    return _SessionLocal


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    Automatically handles session lifecycle and rollback on errors.
    
    Usage:
        with get_db() as db:
            db.query(Model).all()
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        db_logger.error(f"❌ Database error: {e}")
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """
    Returns a new database session.
    Caller is responsible for closing it.
    
    For FastAPI dependency injection:
        def get_db_dependency():
            db = get_db_session()
            try:
                yield db
            finally:
                db.close()
    """
    SessionLocal = get_session_factory()
    return SessionLocal()


def init_db():
    """
    Initialize database tables.
    Retries on connection failure to handle the container startup race condition.
    """
    db_logger.info("🔨 Initializing database tables...")
    engine = get_engine()
    
    retries = 10  # Number of retries
    delay = 3   # Seconds to wait between retries
    
    while retries > 0:
        try:
            # This is the line that tries to connect
            Base.metadata.create_all(bind=engine)
            
            # If it succeeds, log it and break the loop
            db_logger.info("✅ Database tables initialized successfully")
            break
            
        except OperationalError as e:
            # If it fails, log the warning and countdown retries
            db_logger.warning(f"Database connection failed: {e}")
            retries -= 1
            
            if retries == 0:
                # If we run out of retries, log error and re-raise
                db_logger.error("❌ Could not connect to database after all retries.")
                raise  
            
            db_logger.info(f"Retrying in {delay} seconds... ({retries} retries left)")
            time.sleep(delay)
            
        except Exception as e:
            # Catch any other unexpected errors
            db_logger.error(f"❌ Failed to initialize database: {e}")
            raise


def close_db():
    """
    Cleanup database connections.
    Call this on application shutdown.
    """
    global _engine
    if _engine:
        db_logger.info("🔌 Closing database connections...")
        _engine.dispose()
        _engine = None
        db_logger.info("✅ Database connections closed")
