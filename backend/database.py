from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///../data/assets.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class AssetRecord(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(String, unique=True, index=True)
    faiss_id = Column(Integer, unique=True, index=True) # Structural hash mapping id
    clip_faiss_id = Column(Integer, index=True)         # Semantic CLIP mapping id (nullable)
    filepath = Column(String) # Store to retrieve original for comparisons
    owner = Column(String, index=True)
    timestamp = Column(Float)
    signature = Column(String, index=True)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
