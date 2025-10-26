import logging
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Generator
from app.settings import settings

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
    Creates all tables defined in models that inherit from Base.
    """
    try:
        db_logger.info("🔨 Initializing database tables...")
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        db_logger.info("✅ Database tables initialized successfully")
    except Exception as e:
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
