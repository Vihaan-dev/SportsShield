import os

# Fix OpenMP duplicate lib conflict on macOS
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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
import base64
from pathlib import Path
import numpy as np

# Import video pipeline modules
from video_database import SessionLocal as VideoSessionLocal, VideoAssetRecord
import video_hash_logic
import video_ocr_logic
import video_deepfake_logic
import cv2

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
TRUE_VIDEOS_DIR = "../data/true_videos"
FAKE_VIDEOS_DIR = "../data/fake_videos"
SAMPLE_IMAGES_DIR = "../data/test_dataset/originals"
TEST_DATASET_DIR = "../data/test_dataset"

# Ensure data directories always exist
os.makedirs(TRUE_IMAGES_DIR, exist_ok=True)
os.makedirs(FAKE_IMAGES_DIR, exist_ok=True)
os.makedirs(TRUE_VIDEOS_DIR, exist_ok=True)
os.makedirs(FAKE_VIDEOS_DIR, exist_ok=True)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Digital Asset Protection Backend Running"}

class AssetResponse(BaseModel):
    asset_id: str
    message: str
    phash: str

class VideoAssetResponse(BaseModel):
    asset_id: str
    message: str
    avg_phash: str
    duration: float
    fps: int
    resolution: str

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

# Video endpoints

@app.post("/register_video", response_model=VideoAssetResponse)
async def register_video(file: UploadFile = File(...), owner: str = Form("Unknown")):
    """
    Registers a new original video asset
    Computes perceptual hash from keyframes and stores in FAISS index
    """
    asset_id = f"video_{int(time.time())}"
    file_path = os.path.join(TRUE_VIDEOS_DIR, f"{asset_id}_{file.filename}")
    
    # Save uploaded video file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Extract video metadata
    cap = cv2.VideoCapture(file_path)
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps > 0 else 0
    resolution = f"{width}x{height}"
    cap.release()
    
    # Compute perceptual hash from keyframes
    hash_vector, frame_hashes = video_hash_logic.compute_video_phash(file_path, interval_seconds=3)
    
    if hash_vector is None:
        return {
            "error": "Failed to compute video hash",
            "asset_id": asset_id
        }
    
    # Average hash string for display purposes
    avg_hash_str = frame_hashes[0] if frame_hashes else "unknown"
    
    # Generate provenance signature
    timestamp = time.time()
    sig_raw = f"{avg_hash_str}_{owner}_{timestamp}".encode('utf-8')
    signature = hashlib.sha256(sig_raw).hexdigest()
    
    # Add to FAISS index
    faiss_id = video_hash_logic.add_to_index(hash_vector)
    
    # CLIP semantic embedding not computed during registration (lazy loading)
    clip_faiss_id = -1
    
    # Store in database
    db = VideoSessionLocal()
    record = VideoAssetRecord(
        asset_id=asset_id,
        faiss_id=faiss_id,
        clip_faiss_id=clip_faiss_id,
        filepath=file_path,
        owner=owner,
        timestamp=timestamp,
        signature=signature,
        duration=duration,
        fps=fps,
        resolution=resolution
    )
    db.add(record)
    db.commit()
    db.close()
    
    return VideoAssetResponse(
        asset_id=asset_id,
        message="Video asset successfully registered and indexed.",
        avg_phash=avg_hash_str[:16],
        duration=duration,
        fps=fps,
        resolution=resolution
    )

def analyze_suspect_video(file_path: str, original_filename: str):
    """
    Analyzes a suspect video against registered originals
    Uses BOTH average distance AND max frame distance for better detection
    """
    # Compute hash of suspect video
    hash_vector, frame_hashes, individual_hashes = video_hash_logic.compute_video_phash(file_path, interval_seconds=3)
    
    if hash_vector is None:
        return {
            "status": "analyzed",
            "verdict": "error",
            "message": "Failed to compute video hash"
        }
    
    # Search FAISS index for closest match using average hash
    matches = video_hash_logic.search_index(hash_vector, top_k=1)
    
    if not matches:
        return {
            "status": "analyzed",
            "verdict": "clear",
            "message": "No match found in database"
        }
    
    best_match = matches[0]
    best_faiss_id = best_match["faiss_id"]
    avg_distance = best_match["distance"]
    
    # Look up original video in database
    db = VideoSessionLocal()
    orig_record = db.query(VideoAssetRecord).filter(VideoAssetRecord.faiss_id == best_faiss_id).first()
    db.close()
    
    if not orig_record:
        return {
            "status": "analyzed",
            "verdict": "error",
            "message": "FAISS ID has no corresponding database record"
        }
    
    # Compute frame-by-frame comparison for better detection
    # This catches modifications that averaging misses (like text on some frames)
    orig_hash_vector, orig_frame_hashes, orig_individual_hashes = video_hash_logic.compute_video_phash(orig_record.filepath, interval_seconds=3)
    
    # Calculate max distance among all frame pairs
    max_frame_distance = 0
    if orig_individual_hashes and individual_hashes:
        for orig_frame_hash in orig_individual_hashes:
            for suspect_frame_hash in individual_hashes:
                frame_dist = np.linalg.norm(orig_frame_hash - suspect_frame_hash)
                max_frame_distance = max(max_frame_distance, frame_dist)
    
    # Use the HIGHER of average distance or max frame distance
    # This ensures text overlays and color changes are detected
    distance = max(avg_distance, max_frame_distance * 0.5)  # Scale max distance down a bit
    
    # Debug logging
    print(f"\n[VIDEO DETECTION] File: {original_filename}")
    print(f"[VIDEO DETECTION] Avg Distance: {avg_distance:.2f}, Max Frame Distance: {max_frame_distance:.2f}")
    print(f"[VIDEO DETECTION] Final Distance: {distance:.2f}")
    print(f"[VIDEO DETECTION] Matched asset: {orig_record.asset_id}")
    
    # Case 1: Exact match (distance < 8)
    if distance < 8.0:
        print(f"[VIDEO DETECTION] Classification: Reupload (distance < 8)")
        return {
            "title": f"Suspicious Activity ({original_filename})",
            "status": "analyzed",
            "verdict": "suspicious",
            "closest_original_asset": orig_record.asset_id,
            "hamming_distance_estimate": distance,
            "violation_type": "Reupload",
            "flags": ["Exact hash match short-circuit"]
        }
    
    # Case 2: Too distant (distance > 25) - would use CLIP but it's not implemented for videos yet
    if distance > 25.0:
        print(f"[VIDEO DETECTION] Classification: Clear (distance > 25)")
        return {
            "title": "Clean Video",
            "status": "analyzed",
            "verdict": "clear",
            "message": "Hash distance too high, no structural similarity",
            "distance": distance
        }
    
    # Case 3: Derivative zone (8-25) - run classifier checks in parallel
    print(f"[VIDEO DETECTION] Entering derivative zone (8-25), running OCR + Deepfake checks...")
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_ocr = executor.submit(
            video_ocr_logic.check_video_ocr_violation,
            orig_record.filepath,
            file_path,
            sample_frames=3  # Reduced from 5 to speed up
        )
        future_deepfake = executor.submit(
            video_deepfake_logic.check_video_deepfake_violation,
            orig_record.filepath,
            file_path,
            sample_frames=5  # Reduced from 10 to speed up
        )
        
        ocr_results = future_ocr.result()
        df_results = future_deepfake.result()
    
    print(f"[VIDEO DETECTION] OCR found text: {ocr_results.get('text_added', False)}")
    print(f"[VIDEO DETECTION] Deepfake detected: {df_results.get('is_deepfake', False)}")
    
    # Resolution hierarchy: deepfake > text overlay
    violation_type = "Requires Deeper Inspection"
    title = f"Violation Detected ({original_filename})"
    
    if df_results["is_deepfake"]:
        violation_type = "AI Manipulated"
        title = f"AI Manipulation Detected ({original_filename})"
    elif ocr_results["text_added"]:
        violation_type = "Watermarked"
        title = f"Unauthorized Watermark ({original_filename})"
    
    print(f"[VIDEO DETECTION] Final Classification: {violation_type}")
    
    return {
        "title": title,
        "status": "analyzed",
        "verdict": "suspicious",
        "closest_original_asset": orig_record.asset_id,
        "hamming_distance_estimate": distance,
        "violation_type": violation_type,
        "ocr_findings": ocr_results,
        "deepfake_findings": df_results
    }

@app.post("/detect_video")
async def detect_video(file: UploadFile = File(...)):
    """
    Analyzes a suspect video against registered videos
    """
    temp_id = f"suspect_{int(time.time())}"
    file_path = os.path.join(FAKE_VIDEOS_DIR, f"{temp_id}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return analyze_suspect_video(file_path, file.filename)

# Track shown videos to avoid repeats and implement stop condition
shown_videos = set()
detection_count = 0
max_detections = random.randint(5, 12)  # Random stop point

@app.get("/simulate_video_scrape")
def simulate_video_scrape():
    """
    Simulates scraping by randomly selecting a test video and analyzing it
    Stops after 5-12 detections to avoid infinite loop
    """
    global shown_videos, detection_count, max_detections
    
    # Reset if we've shown all videos
    if detection_count >= max_detections:
        shown_videos.clear()
        detection_count = 0
        max_detections = random.randint(5, 12)
        return {
            "status": "complete",
            "message": f"Scan complete. Analyzed {detection_count} threats."
        }
    
    # Find all videos in test dataset, EXCLUDING originals folder
    search_path = os.path.join("..", "data", "test_video_dataset", "**", "*.*")
    files = [f for f in glob.glob(search_path, recursive=True) 
             if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))
             and 'originals' not in f.lower()
             and f not in shown_videos]  # Exclude already shown
    
    if not files:
        # All videos shown, reset
        shown_videos.clear()
        detection_count = 0
        max_detections = random.randint(5, 12)
        return {
            "status": "complete",
            "message": "All test videos analyzed. Resetting..."
        }
    
    target_file = random.choice(files)
    shown_videos.add(target_file)
    filename = os.path.basename(target_file)
    
    # Run detection pipeline
    result = analyze_suspect_video(target_file, filename)
    
    # Skip if verdict is clear (no violation detected)
    if result.get('verdict') == 'clear':
        return result  # Return without social metadata
    
    detection_count += 1
    
    # Append fake social metadata with DIVERSE locations
    platforms = ["Twitter", "Instagram", "TikTok", "YouTube", "Facebook", "Reddit"]
    
    # Much more diverse locations
    locations = [
        [19.0760, 72.8777],   # Mumbai
        [51.5074, -0.1278],   # London
        [40.7128, -74.0060],  # New York
        [34.0522, -118.2437], # Los Angeles
        [48.8566, 2.3522],    # Paris
        [-33.8688, 151.2093], # Sydney
        [35.6762, 139.6503],  # Tokyo
        [55.7558, 37.6173],   # Moscow
        [28.6139, 77.2090],   # Delhi
        [-23.5505, -46.6333], # São Paulo
        [1.3521, 103.8198],   # Singapore
        [25.2048, 55.2708],   # Dubai
        [52.5200, 13.4050],   # Berlin
        [37.7749, -122.4194], # San Francisco
        [-34.6037, -58.3816], # Buenos Aires
    ]
    
    # Map violation types to severity and type
    violation_type = result.get('violation_type', '')
    
    if 'AI' in violation_type or 'Deepfake' in violation_type:
        severity = 'high'
        threat_type = 'deepfake'
    elif 'Watermark' in violation_type or 'Text' in violation_type:
        severity = 'medium'
        threat_type = 'watermark'
    elif 'Reupload' in violation_type:
        severity = 'low'
        threat_type = 'repost'
    else:
        severity = 'medium'
        threat_type = 'derivative'
    
    social_metadata = {
        "platform": random.choice(platforms),
        "location": random.choice(locations),  # Truly random location each time
        "time": "Just now",
        "severity": severity,
        "type": threat_type
    }
    
    result.update(social_metadata)
    return result

# Demo endpoints for clean prototype

@app.get("/get_sample_images")
def get_sample_images():
    """
    Returns list of available sample images for demo
    """
    samples = []
    sample_files = glob.glob(os.path.join(SAMPLE_IMAGES_DIR, "*_original.jpg"))
    
    for filepath in sample_files:
        filename = os.path.basename(filepath)
        name = filename.replace('_original.jpg', '').title()
        
        samples.append({
            "id": filename.replace('_original.jpg', ''),
            "name": name,
            "filename": filename,
            "path": f"/sample_image/{filename}"
        })
    
    return {"samples": samples}

@app.get("/sample_image/{filename}")
def get_sample_image(filename: str):
    """
    Serves sample image files
    """
    filepath = os.path.join(SAMPLE_IMAGES_DIR, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath)
    raise HTTPException(status_code=404, detail="Image not found")

@app.get("/sample_video/{filename}")
def get_sample_video(filename: str):
    """
    Serves sample video files
    """
    filepath = os.path.join("../data/test_video_dataset/originals", filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Video not found")

@app.get("/variant_video/{category}/{filename}")
def get_variant_video(category: str, filename: str):
    """
    Serves variant video files from test dataset
    """
    filepath = os.path.join("../data/test_video_dataset", category, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Video not found")

@app.get("/get_sample_videos")
def get_sample_videos():
    """
    Returns list of available sample videos for demo
    """
    samples = []
    sample_dir = "../data/test_video_dataset/originals"
    sample_files = glob.glob(os.path.join(sample_dir, "*_original.mp4"))
    
    for filepath in sample_files:
        filename = os.path.basename(filepath)
        name = filename.replace('_original.mp4', '').title()
        
        samples.append({
            "id": filename.replace('_original.mp4', ''),
            "name": name,
            "filename": filename,
            "path": f"/sample_video/{filename}",
            "thumbnail": f"/sample_video/{filename}"
        })
    
    return {"samples": samples}

@app.get("/variant_image/{category}/{filename}")
def get_variant_image(category: str, filename: str):
    """
    Serves variant image files from test dataset
    """
    filepath = os.path.join(TEST_DATASET_DIR, category, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath)
    raise HTTPException(status_code=404, detail="Image not found")

def classify_variant_type(category: str) -> dict:
    """
    Maps category folder to human-readable violation type
    Works for both images and videos
    """
    type_map = {
        # Image types
        "type1_cropped": {"type": "Cropped", "severity": "low", "color": "repost"},
        "type1_compressed": {"type": "Reupload", "severity": "low", "color": "repost"},
        "type2_text_overlay": {"type": "Watermarked", "severity": "medium", "color": "watermark"},
        "type2_watermarked": {"type": "Watermarked", "severity": "medium", "color": "watermark"},
        "type3_ai_simulated": {"type": "AI Manipulated", "severity": "high", "color": "deepfake"},
        "type4_mixed_crop_text": {"type": "Modified", "severity": "medium", "color": "derivative"},
        "type4_mixed_compress_watermark": {"type": "Modified", "severity": "medium", "color": "derivative"},
        # Video types
        "type1_trimmed": {"type": "Trimmed", "severity": "low", "color": "repost"},
        "type2_logo_overlay": {"type": "Logo Added", "severity": "medium", "color": "watermark"},
        "type3_color_graded": {"type": "Color Graded", "severity": "high", "color": "deepfake"},
        "type4_mixed_trim_text": {"type": "Modified", "severity": "medium", "color": "derivative"},
    }
    return type_map.get(category, {"type": "Modified", "severity": "medium", "color": "derivative"})

@app.post("/analyze_sample")
async def analyze_sample(sample_id: str = Form(...)):
    """
    Analyzes a sample image and returns 3-7 random violations from its variants
    Shows where the image was found on the internet (simulated)
    """
    
    # Find all variants for this sample
    all_variants = []
    
    categories = [
        "type1_cropped",
        "type1_compressed",
        "type2_text_overlay",
        "type2_watermarked",
        "type3_ai_simulated",
        "type4_mixed_crop_text",
        "type4_mixed_compress_watermark"
    ]
    
    for category in categories:
        pattern = os.path.join(TEST_DATASET_DIR, category, f"{sample_id}_*.jpg")
        files = glob.glob(pattern)
        for filepath in files:
            all_variants.append({
                "category": category,
                "filename": os.path.basename(filepath),
                "filepath": filepath
            })
    
    if not all_variants:
        return {
            "status": "not_found",
            "message": "No variants found for this sample"
        }
    
    # Randomly select 3-7 violations
    num_violations = random.randint(3, min(7, len(all_variants)))
    selected_variants = random.sample(all_variants, num_violations)
    
    # Diverse locations
    locations = [
        {"coords": [19.0760, 72.8777], "city": "Mumbai"},
        {"coords": [51.5074, -0.1278], "city": "London"},
        {"coords": [40.7128, -74.0060], "city": "New York"},
        {"coords": [34.0522, -118.2437], "city": "Los Angeles"},
        {"coords": [48.8566, 2.3522], "city": "Paris"},
        {"coords": [-33.8688, 151.2093], "city": "Sydney"},
        {"coords": [35.6762, 139.6503], "city": "Tokyo"},
        {"coords": [55.7558, 37.6173], "city": "Moscow"},
        {"coords": [28.6139, 77.2090], "city": "Delhi"},
        {"coords": [-23.5505, -46.6333], "city": "São Paulo"},
        {"coords": [1.3521, 103.8198], "city": "Singapore"},
        {"coords": [25.2048, 55.2708], "city": "Dubai"},
        {"coords": [52.5200, 13.4050], "city": "Berlin"},
        {"coords": [37.7749, -122.4194], "city": "San Francisco"},
        {"coords": [-34.6037, -58.3816], "city": "Buenos Aires"},
    ]
    
    platforms = ["Twitter", "Instagram", "TikTok", "Facebook", "Reddit", "YouTube"]
    
    # Build violations list
    violations = []
    used_locations = random.sample(locations, num_violations)
    
    for i, variant in enumerate(selected_variants):
        classification = classify_variant_type(variant["category"])
        
        violations.append({
            "id": i + 1,
            "type": classification["type"],
            "severity": classification["severity"],
            "color": classification["color"],
            "location": used_locations[i]["coords"],
            "city": used_locations[i]["city"],
            "platform": random.choice(platforms),
            "time": f"{random.randint(1, 48)} hours ago",
            "original_image": f"/sample_image/{sample_id}_original.jpg",
            "found_image": f"/variant_image/{variant['category']}/{variant['filename']}",
            "category": variant["category"],
            "filename": variant["filename"]
        })
    
    return {
        "status": "found",
        "sample_id": sample_id,
        "total_violations": num_violations,
        "violations": violations,
        "message": f"Found {num_violations} unauthorized copies across the internet"
    }

@app.post("/analyze_upload")
async def analyze_upload(file: UploadFile = File(...)):
    """
    Analyzes an uploaded image
    If it's not a sample image, returns 'not found' after simulated delay
    """
    
    # Save uploaded file temporarily
    temp_path = os.path.join(FAKE_IMAGES_DIR, f"temp_{int(time.time())}_{file.filename}")
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Simulate processing delay
    time.sleep(1)
    
    # Check if this matches any sample (simple filename check for demo)
    filename_lower = file.filename.lower()
    
    sample_names = ["messi", "ronaldo", "verstappen"]
    matched_sample = None
    
    for sample in sample_names:
        if sample in filename_lower:
            matched_sample = sample
            break
    
    # Clean up temp file
    if os.path.exists(temp_path):
        os.remove(temp_path)
    
    if matched_sample:
        # Redirect to analyze_sample logic
        return await analyze_sample(sample_id=matched_sample)
    else:
        # Not a sample image
        return {
            "status": "not_found",
            "message": "No unauthorized copies found on the internet",
            "scanned_platforms": ["Twitter", "Instagram", "Facebook", "TikTok", "Reddit", "YouTube"],
            "scan_time": "2.3 seconds"
        }

@app.post("/analyze_sample_video")
async def analyze_sample_video(sample_id: str = Form(...)):
    """
    Analyzes a sample video and returns 3-7 random violations from its variants
    """
    all_variants = []
    categories = [
        "type1_trimmed", "type1_compressed", "type1_cropped",
        "type2_text_overlay", "type2_logo_overlay",
        "type3_color_graded", "type4_mixed_trim_text"
    ]
    
    video_dataset_dir = "../data/test_video_dataset"
    
    for category in categories:
        pattern = os.path.join(video_dataset_dir, category, f"{sample_id}_*.mp4")
        files = glob.glob(pattern)
        for filepath in files:
            all_variants.append({
                "category": category,
                "filename": os.path.basename(filepath),
                "filepath": filepath
            })
    
    if not all_variants:
        return {"status": "not_found", "message": "No variants found"}
    
    num_violations = random.randint(3, min(7, len(all_variants)))
    selected_variants = random.sample(all_variants, num_violations)
    
    locations = [
        {"coords": [19.0760, 72.8777], "city": "Mumbai"},
        {"coords": [51.5074, -0.1278], "city": "London"},
        {"coords": [40.7128, -74.0060], "city": "New York"},
        {"coords": [34.0522, -118.2437], "city": "Los Angeles"},
        {"coords": [48.8566, 2.3522], "city": "Paris"},
        {"coords": [-33.8688, 151.2093], "city": "Sydney"},
        {"coords": [35.6762, 139.6503], "city": "Tokyo"},
        {"coords": [55.7558, 37.6173], "city": "Moscow"},
        {"coords": [28.6139, 77.2090], "city": "Delhi"},
    ]
    
    platforms = ["Twitter", "Instagram", "TikTok", "Facebook", "Reddit", "YouTube"]
    violations = []
    used_locations = random.sample(locations, num_violations)
    
    for i, variant in enumerate(selected_variants):
        classification = classify_variant_type(variant["category"])
        violations.append({
            "id": i + 1,
            "type": classification["type"],
            "severity": classification["severity"],
            "color": classification["color"],
            "location": used_locations[i]["coords"],
            "city": used_locations[i]["city"],
            "platform": random.choice(platforms),
            "time": f"{random.randint(1, 48)} hours ago",
            "original_video": f"/sample_video/{sample_id}_original.mp4",
            "found_video": f"/variant_video/{variant['category']}/{variant['filename']}",
            "category": variant["category"],
            "filename": variant["filename"]
        })
    
    return {
        "status": "found",
        "sample_id": sample_id,
        "total_violations": num_violations,
        "violations": violations,
        "message": f"Found {num_violations} unauthorized copies"
    }

@app.post("/analyze_upload_video")
async def analyze_upload_video(file: UploadFile = File(...)):
    """
    Analyzes uploaded video, returns not found if not a sample
    """
    temp_path = os.path.join(FAKE_VIDEOS_DIR, f"temp_{int(time.time())}_{file.filename}")
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    time.sleep(2)
    filename_lower = file.filename.lower()
    
    if "volleyball" in filename_lower:
        matched_sample = "Volleyball"
    else:
        matched_sample = None
    
    if os.path.exists(temp_path):
        os.remove(temp_path)
    
    if matched_sample:
        return await analyze_sample_video(sample_id=matched_sample)
    else:
        return {
            "status": "not_found",
            "message": "No unauthorized copies found on the internet",
            "scanned_platforms": ["Twitter", "Instagram", "TikTok", "YouTube"],
            "scan_time": "3.7 seconds"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
