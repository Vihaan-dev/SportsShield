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
from gemini_logic import generate_type3_explanation
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
    import uuid
    asset_id = f"asset_{uuid.uuid4().hex[:8]}"
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
    
    # CLIP semantic indexing disabled in registration for stability on macOS.
    # Semantic check is now a fallback in /detect only if pHash fails.
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
    """
    Multi-signal detection pipeline.
    
    Decision flow:
    1. Compute pHash → search FAISS for nearest registered original
    2. If no match at all → "clear"
    3. If distance > 30 → completely unrelated structurally → try CLIP semantic
    4. If distance ≤ 30 → image is related to a registered asset. Now classify HOW:
       a. Run OCR check (text/watermark detection) in parallel with
       b. Run deepfake/AI analysis (FFT + SSIM + histogram)
       c. Use multi-signal scoring to determine Type 1 / Type 2 / Type 3
    """
    # ---- Stage 1: Perceptual Hash Lookup ----
    hash_vector, str_hash = hash_logic.compute_phash(file_path)
    matches = hash_logic.search_index(hash_vector, top_k=1)
    
    if not matches:
        return {"status": "analyzed", "verdict": "clear", "message": "No match found in DB", "title": "Scan Complete"}
        
    best_match = matches[0]
    best_faiss_id = best_match["faiss_id"]
    distance = best_match["distance"]
    
    print(f"DEBUG: Match found! FAISS ID: {best_faiss_id}, Distance: {distance:.2f} for {original_filename}")
    db = SessionLocal()
    orig_record = db.query(AssetRecord).filter(AssetRecord.faiss_id == best_faiss_id).first()
    db.close()
    
    if not orig_record:
        return {"status": "analyzed", "verdict": "error", "message": "FAISS ID has no corresponding DB record"}
    
    # ---- Stage 2: Distance-based gating ----
    # Structural tolerance: 60.0 allows for very aggressive crops
    if distance > 60.0:
        return {
            "title": "Scan Complete",
            "status": "analyzed",
            "verdict": "clear",
            "message": "No structural match found within tolerance (60.0).",
        }
    
    # ---- Stage 3: Multi-signal Classification ----
    # Distance ≤ 30: this image IS related to a registered asset.
    # Now determine the TYPE of violation by running all classifiers.
    
    try:
        print(f"DEBUG: Starting OCR check for {file_path}")
        ocr_results = ocr_logic.check_ocr_violation(orig_record.filepath, file_path)
        print(f"DEBUG: OCR check complete")
        
        print(f"DEBUG: Starting Deepfake check for {file_path}")
        df_results = deepfake_logic.check_deepfake_violation(orig_record.filepath, file_path)
        print(f"DEBUG: Deepfake check complete")
    except Exception as e:
        print(f"CRITICAL ERROR in classification pipeline: {e}")
        # Fallback to empty results so the server doesn't die
        ocr_results = {"text_added": False, "ocr_detected": False, "overlay_detected": False}
        df_results = {"ai_confidence_score": 0.0, "ssim_score": 0.5, "is_deepfake": False}
    
    # ---- Stage 4: Scoring & Classification ----
    # 
    # We collect signals and score each violation type.
    # The type with the highest score wins.
    #
    # Score components:
    #   Type 1 (Repost/Copy): very low pHash distance, high SSIM, no text added, no AI manipulation
    #   Type 2 (Watermark/Text): text detected (OCR or pixel overlay), moderate SSIM  
    #   Type 3 (AI/Deepfake): high FFT diff, low SSIM, colour histogram divergence
    
    ssim = df_results.get("ssim_score", 1.0)
    hist_corr = df_results.get("histogram_correlation", 1.0)
    ai_confidence = df_results.get("ai_confidence_score", 0.0)
    text_added = ocr_results.get("text_added", False)
    ocr_detected = ocr_results.get("ocr_detected", False)
    overlay_detected = ocr_results.get("overlay_detected", False)
    
    score_type1 = 0.0  # Repost / Near-exact copy
    score_type2 = 0.0  # Watermark / Text overlay
    score_type3 = 0.0  # AI / Deepfake alteration
    
    # --- Type 1 signals (Reposts) ---
    if distance <= 2.0:
        score_type1 += 1.5
    elif distance <= 15.0:
        score_type1 += 0.8
    
    if ssim > 0.95:
        # Strong but not overwhelming boost for very high SSIM to favor repost/near-exact matches
        score_type1 += 0.6
    
    # --- Type 2 signals (Watermarks/Text) ---
    # Use the overlay analysis score as a graded signal rather than a fixed jump.
    overlay_score = 0.0
    try:
        overlay_score = float(ocr_results.get("overlay_analysis", {}).get("overlay_score", 0.0))
    except Exception:
        overlay_score = 0.0

    # Scale overlay contribution so subtle overlays provide a small bump,
    # while moderate/strong overlays can still decisively indicate Type 2.
    if overlay_score >= 0.20:
        score_type2 += overlay_score * 2.0
    else:
        score_type2 += overlay_score * 0.6
        
    # --- Type 3 signals (AI / Deepfake) ---
    # Increase AI multiplier to ensure genuine AI alterations are detected
    score_type3 += (ai_confidence * 2.4)
    
    # Tie-breaking & Priority: require a measurable margin before zeroing Type 1.
    # This prevents tiny overlay/noise signals from cancelling out an otherwise
    # strong Type 1 repost signal.
    override_margin = 0.05
    if score_type2 >= 1.0 and score_type2 > score_type1 + override_margin:
        score_type1 = 0.0
    if score_type3 >= 1.0 and score_type3 > score_type1 + override_margin:
        score_type1 = 0.0

    # --- Decision Engine ---
    scores = {
        "Type 1 - Repost / Near Exact Copy": score_type1,
        "Type 2 - Watermark / Text Addition": score_type2,
        "Type 3 - Deepfake / AI Alteration": score_type3,
    }
    
    violation_type = max(scores, key=scores.get)

    gemini_explanation = None
    if violation_type == "Type 3 - Deepfake / AI Alteration":
        local_evidence = {
            "violation_type": violation_type,
            "classification_scores": {k: round(v, 3) for k, v in scores.items()},
            "distance": round(distance, 2),
            "ssim_score": round(ssim, 4),
            "histogram_correlation": round(hist_corr, 4),
            "ai_confidence_score": round(ai_confidence, 2),
            "ocr_detected": bool(ocr_detected),
            "overlay_detected": bool(overlay_detected),
            "overlay_score": round(overlay_score, 4),
            "clip_status": "disabled in detection; clip_logic.py remains a registration helper only",
        }
        gemini_explanation = generate_type3_explanation(orig_record.filepath, file_path, local_evidence)
    
    title_map = {
        "Type 1 - Repost / Near Exact Copy": f"Suspicious Activity ({original_filename})",
        "Type 2 - Watermark / Text Addition": f"Unauthorized Watermark/Text ({original_filename})",
        "Type 3 - Deepfake / AI Alteration": f"AI Faceswap/Alteration ({original_filename})",
    }
    
    return {
        "title": title_map[violation_type],
        "status": "analyzed",
        "verdict": "suspicious",
        "closest_original_asset": orig_record.asset_id,
        "hamming_distance_estimate": distance,
        "violation_type": violation_type,
        "classification_scores": {k: round(v, 3) for k, v in scores.items()},
        "ocr_findings": ocr_results,
        "deepfake_findings": df_results,
        "gemini_explanation": gemini_explanation,
        "pipeline": {
            "phash": True,
            "ocr": True,
            "deepfake": True,
            "gemini": gemini_explanation is not None,
            "clip": {
                "active": False,
                "location": "backend/clip_logic.py",
                "note": "CLIP is imported and available, but detection does not use it. Registration stores clip_faiss_id = -1.",
            },
        },
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
