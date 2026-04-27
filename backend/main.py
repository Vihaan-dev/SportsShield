import os

# Fix OpenMP duplicate lib conflict on macOS
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import time
import shutil
from database import SessionLocal, AssetRecord
import hash_logic
import ocr_logic
import deepfake_logic
import clip_logic
import hashlib
import random
import glob
from concurrent.futures import ThreadPoolExecutor

app = FastAPI(title="Digital Asset Protection API", version="1.0.0")

# Setup CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TRUE_IMAGES_DIR = "../data/true_images"
FAKE_IMAGES_DIR = "../data/fake_images"

# Ensure data directories always exist
os.makedirs(TRUE_IMAGES_DIR, exist_ok=True)
os.makedirs(FAKE_IMAGES_DIR, exist_ok=True)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Digital Asset Protection Backend Running"}

class AssetResponse(BaseModel):
    asset_id: str
    message: str
    phash: str

@app.post("/register", response_model=AssetResponse)
async def register_asset(file: UploadFile = File(...), owner: str = Form("Unknown")):
    """
    Registers a new original asset. 
    """
    asset_id = f"asset_{int(time.time())}"
    file_path = os.path.join(TRUE_IMAGES_DIR, f"{asset_id}_{file.filename}")
    
    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Compute Hash
    hash_vector, str_hash = hash_logic.compute_phash(file_path)
    
    # Generate signature
    timestamp = time.time()
    sig_raw = f"{str_hash}_{owner}_{timestamp}".encode('utf-8')
    signature = hashlib.sha256(sig_raw).hexdigest()
    
    # Make sure DB schema gets what it needs
    db = SessionLocal()
    
    # Index in FAISS (structural, fast)
    faiss_id = hash_logic.add_to_index(hash_vector)
    
    # CLIP semantic embedding is computed lazily on /detect only (not on registration)
    # to keep registration fast. clip_faiss_id stored as -1 placeholder.
    clip_faiss_id = -1
    
    record = AssetRecord(
        asset_id=asset_id,
        faiss_id=faiss_id,
        clip_faiss_id=clip_faiss_id,
        filepath=file_path,
        owner=owner,
        timestamp=timestamp,
        signature=signature
    )
    db.add(record)
    db.commit()
    db.close()

    return AssetResponse(
        asset_id=asset_id, 
        message="Asset successfully registered and indexed.",
        phash=str_hash
    )

def analyze_suspect_file(file_path: str, original_filename: str):
    # 1. Image Hash check (Distance)
    hash_vector, str_hash = hash_logic.compute_phash(file_path)
    matches = hash_logic.search_index(hash_vector, top_k=1)
    
    if not matches:
        return {"status": "analyzed", "verdict": "clear", "message": "No match found in DB"}
        
    best_match = matches[0]
    best_faiss_id = best_match["faiss_id"]
    distance = best_match["distance"]
    
    # Look up original asset in DB
    db = SessionLocal()
    orig_record = db.query(AssetRecord).filter(AssetRecord.faiss_id == best_faiss_id).first()
    db.close()
    
    if not orig_record:
        return {"status": "analyzed", "verdict": "error", "message": "FAISS ID has no corresponding DB record"}
        
    # 1. Exact Match Short-Circuit
    if distance < 8.0:
        return {
            "title": f"Suspicious Activity ({original_filename})",
            "status": "analyzed",
            "verdict": "suspicious",
            "closest_original_asset": orig_record.asset_id,
            "hamming_distance_estimate": distance,
            "violation_type": "Type 1 - Repost / Near Exact Copy",
            "suspect_phash": str_hash,
            "flags": ["Exact hash match short-circuit"]
        }
        
    # 2. Too Distant -> Might be completely unrelated. 
    # FAISS always returns the "closest" match mathematically, even if the closest match is still 
    # totally unrelated. If distance is huge (>25), we assume pHash failed to find a similarity.
    if distance > 25.0:
        clip_emb = clip_logic.compute_embedding(file_path)
        clip_matches = clip_logic.search_index(clip_emb, top_k=1)
        
        if not clip_matches:
            return {"title": "Scan Complete", "status": "analyzed", "verdict": "clear", "message": "No semantic matches found."}
            
        best_clip = clip_matches[0]
        clip_similarity = best_clip["similarity"]
        
        # Inner product of normalized vectors gives Cosine Similarity.
        # High similarity (>0.85) means semantic duplicate (Deepfake structural replacement)
        if clip_similarity > 0.85:
            # Query db for the specific matched semantic record
            db_rec = SessionLocal().query(AssetRecord).filter(AssetRecord.clip_faiss_id == best_clip["clip_faiss_id"]).first()
            return {
                "title": f"Deepfake AI Generation ({original_filename})",
                "status": "analyzed",
                "verdict": "suspicious",
                "violation_type": "Type 3 - Deepfake AI Generation (Semantic Match)",
                "closest_original_asset": db_rec.asset_id if db_rec else "Unknown",
                "clip_similarity_score": clip_similarity
            }
        else:
            return {
               "title": "Clean Image",
               "status": "analyzed",
               "verdict": "clear",
               "message": "Hash distance blocked, uncorrelated structure. Semantic check cleared.",
               "clip_similarity": clip_similarity
            }
        
    # 3. The "Derivative Zone" (Distance between 8 and 25)
    # The image is similar but clearly has modifications. We run the threads to find out what changed.
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_ocr = executor.submit(ocr_logic.check_ocr_violation, orig_record.filepath, file_path)
        future_deepfake = executor.submit(deepfake_logic.check_deepfake_violation, orig_record.filepath, file_path)
        
        ocr_results = future_ocr.result()
        df_results = future_deepfake.result()
        
    # Resolution Hierarchy
    violation_type = "Requires Deeper Inspection (CLIP)"
    title = f"Violation Detected ({original_filename})"
    if df_results["is_deepfake"]:
        violation_type = "Type 3 - Deepfake / AI Alteration"
        title = f"AI Faceswap/Alteration ({original_filename})"
    elif ocr_results["text_added"]:
        violation_type = "Type 2 - Watermark / Text Addition"
        title = f"Unauthorized Watermark/Text ({original_filename})"
        
    return {
        "title": title,
        "status": "analyzed",
        "verdict": "suspicious",
        "closest_original_asset": orig_record.asset_id,
        "hamming_distance_estimate": distance,
        "violation_type": violation_type,
        "ocr_findings": ocr_results,
        "deepfake_findings": df_results,
        "suspect_phash": str_hash
    }

@app.post("/detect")
async def detect_asset(file: UploadFile = File(...)):
    """
    Analyzes a suspect asset against registered assets.
    """
    temp_id = f"suspect_{int(time.time())}"
    file_path = os.path.join(FAKE_IMAGES_DIR, f"{temp_id}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return analyze_suspect_file(file_path, file.filename)

@app.get("/simulate_scrape")
def simulate_scrape():
    """
    Randomly selects a file from the test dataset to simulate a social media scrape.
    Passes the file into the detection pipeline and appends fake social media metadata.
    """
    # Find all images in test_dataset
    search_path = os.path.join("..", "data", "test_dataset", "**", "*.*")
    files = [f for f in glob.glob(search_path, recursive=True) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
    
    if not files:
        return {"error": "No files found in test dataset. Please run generate_test_data.py first."}
        
    target_file = random.choice(files)
    filename = os.path.basename(target_file)
    
    # 1. Run core pipeline
    result = analyze_suspect_file(target_file, filename)
    
    # 2. Append social mockup data
    platforms = ["Twitter", "Instagram", "Reddit", "TikTok"]
    locations = [
        [19.0760, 72.8777], # Mumbai
        [51.5560, -0.2796], # London
        [34.0522, -118.243], # LA
        [48.8566, 2.3522],   # Paris
        [-33.8688, 151.209]  # Sydney
    ]
    
    social_metadata = {
        "platform": random.choice(platforms),
        "location": random.choice(locations),
        "time": "Just now",
        "severity": "high" if "Type 3" in result.get("violation_type", "") else ("medium" if "Type 2" in result.get("violation_type", "") else "low"),
        "type": "deepfake" if "Type 3" in result.get("violation_type", "") else ("repost" if "Type 1" in result.get("violation_type", "") else "derivative")
    }
    
    result.update(social_metadata)
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
