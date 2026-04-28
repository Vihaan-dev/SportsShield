from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker

# Separate database for video assets to keep image and video pipelines independent
SQLALCHEMY_DATABASE_URL = "sqlite:///../data/video_assets.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class VideoAssetRecord(Base):
    """
    Database model for registered video assets
    Stores metadata and FAISS index mappings for video fingerprints
    """
    __tablename__ = "video_assets"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(String, unique=True, index=True)  # Unique identifier like "video_1234567890"
    faiss_id = Column(Integer, unique=True, index=True)  # Position in FAISS index for structural hash
    clip_faiss_id = Column(Integer, index=True)          # Position in CLIP index for semantic matching (nullable)
    filepath = Column(String)                            # Path to original video file for comparison
    owner = Column(String, index=True)                   # Organization or person who registered the asset
    timestamp = Column(Float)                            # Unix timestamp of registration
    signature = Column(String, index=True)               # SHA-256 hash for provenance verification
    duration = Column(Float)                             # Video duration in seconds
    fps = Column(Integer)                                # Frames per second
    resolution = Column(String)                          # Video resolution like "1920x1080"

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

def get_db():
    """
    Dependency injection helper for FastAPI endpoints
    Ensures database connections are properly closed after use
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
