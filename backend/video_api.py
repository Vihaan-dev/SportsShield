import os
import time
import shutil
import hashlib
import random
import glob
import cv2
from fastapi import FastAPI, File, UploadFile, Form
from pydantic import BaseModel
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from video_database import SessionLocal, VideoAssetRecord
import video_hash_logic
import video_ocr_logic
import video_deepfake_logic

# This file contains video-specific endpoints
# Kept separate from main.py to maintain clean separation between image and video pipelines

TRUE_VIDEOS_DIR = "../data/true_videos"
FAKE_VIDEOS_DIR = "../data/fake_videos"

# Ensure directories exist
os.makedirs(TRUE_VIDEOS_DIR, exist_ok=True)
os.makedirs(FAKE_VIDEOS_DIR, exist_ok=True)

class VideoAssetResponse(BaseModel):
    """Response model for video registration endpoint"""
    asset_id: str
    message: str
    avg_phash: str
    duration: float
    fps: int
    resolution: str

def register_video_asset(file: UploadFile, owner: str = "Unknown"):
    """
    Registers a new original video asset
    Computes perceptual hash from keyframes and stores in FAISS index
    
    Args:
        file: Uploaded video file
        owner: Organization or person registering the asset
    
    Returns:
        VideoAssetResponse with registration details
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
    db = SessionLocal()
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
    Uses distance-based decision tree similar to image pipeline
    
    Args:
        file_path: Path to suspect video file
        original_filename: Original filename for display
    
    Returns:
        Dict with analysis results and violation classification
    """
    # Compute hash of suspect video
    hash_vector, frame_hashes = video_hash_logic.compute_video_phash(file_path, interval_seconds=3)
    
    if hash_vector is None:
        return {
            "status": "analyzed",
            "verdict": "error",
            "message": "Failed to compute video hash"
        }
    
    # Search FAISS index for closest match
    matches = video_hash_logic.search_index(hash_vector, top_k=1)
    
    if not matches:
        return {
            "status": "analyzed",
            "verdict": "clear",
            "message": "No match found in database"
        }
    
    best_match = matches[0]
    best_faiss_id = best_match["faiss_id"]
    distance = best_match["distance"]
    
    # Look up original video in database
    db = SessionLocal()
    orig_record = db.query(VideoAssetRecord).filter(VideoAssetRecord.faiss_id == best_faiss_id).first()
    db.close()
    
    if not orig_record:
        return {
            "status": "analyzed",
            "verdict": "error",
            "message": "FAISS ID has no corresponding database record"
        }
    
    # Decision tree based on distance
    
    # Case 1: Exact match (distance < 8)
    if distance < 8.0:
        return {
            "title": f"Suspicious Activity ({original_filename})",
            "status": "analyzed",
            "verdict": "suspicious",
            "closest_original_asset": orig_record.asset_id,
            "hamming_distance_estimate": distance,
            "violation_type": "Type 1 - Repost / Near Exact Copy",
            "flags": ["Exact hash match short-circuit"]
        }
    
    # Case 2: Too distant (distance > 25) - would use CLIP but it's not implemented for videos yet
    if distance > 25.0:
        return {
            "title": "Clean Video",
            "status": "analyzed",
            "verdict": "clear",
            "message": "Hash distance too high, no structural similarity",
            "distance": distance
        }
    
    # Case 3: Derivative zone (8-25) - run classifier checks in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_ocr = executor.submit(
            video_ocr_logic.check_video_ocr_violation,
            orig_record.filepath,
            file_path,
            sample_frames=5
        )
        future_deepfake = executor.submit(
            video_deepfake_logic.check_video_deepfake_violation,
            orig_record.filepath,
            file_path,
            sample_frames=10
        )
        
        ocr_results = future_ocr.result()
        df_results = future_deepfake.result()
    
    # Resolution hierarchy: deepfake > text overlay
    violation_type = "Requires Deeper Inspection"
    title = f"Violation Detected ({original_filename})"
    
    if df_results["is_deepfake"]:
        violation_type = "Type 3 - Deepfake / AI Alteration"
        title = f"AI Manipulation Detected ({original_filename})"
    elif ocr_results["text_added"]:
        violation_type = "Type 2 - Watermark / Text Addition"
        title = f"Unauthorized Watermark ({original_filename})"
    
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

def detect_video_asset(file: UploadFile):
    """
    Endpoint handler for video detection
    Saves uploaded suspect video and runs analysis pipeline
    
    Args:
        file: Uploaded suspect video file
    
    Returns:
        Analysis results dict
    """
    temp_id = f"suspect_{int(time.time())}"
    file_path = os.path.join(FAKE_VIDEOS_DIR, f"{temp_id}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return analyze_suspect_video(file_path, file.filename)

def simulate_video_scrape():
    """
    Simulates scraping by randomly selecting a test video and analyzing it
    Adds fake social media metadata for demo purposes
    
    Returns:
        Analysis results with social metadata
    """
    # Find all videos in test dataset
    search_path = os.path.join("..", "data", "test_video_dataset", "**", "*.*")
    files = [f for f in glob.glob(search_path, recursive=True) 
             if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))]
    
    if not files:
        return {
            "error": "No videos found in test dataset. Please run generate_test_videos.py first."
        }
    
    target_file = random.choice(files)
    filename = os.path.basename(target_file)
    
    # Run detection pipeline
    result = analyze_suspect_video(target_file, filename)
    
    # Append fake social metadata for demo
    platforms = ["Twitter", "Instagram", "TikTok", "YouTube"]
    locations = [
        [19.0760, 72.8777],   # Mumbai
        [51.5560, -0.2796],   # London
        [34.0522, -118.243],  # LA
        [48.8566, 2.3522],    # Paris
        [-33.8688, 151.209]   # Sydney
    ]
    
    social_metadata = {
        "platform": random.choice(platforms),
        "location": random.choice(locations),
        "time": "Just now",
        "severity": "high" if "Type 3" in result.get("violation_type", "") else (
            "medium" if "Type 2" in result.get("violation_type", "") else "low"
        ),
        "type": "deepfake" if "Type 3" in result.get("violation_type", "") else (
            "repost" if "Type 1" in result.get("violation_type", "") else "derivative"
        )
    }
    
    result.update(social_metadata)
    return result

# These functions would be integrated into main.py as FastAPI endpoints:
# @app.post("/register_video", response_model=VideoAssetResponse)
# @app.post("/detect_video")
# @app.get("/simulate_video_scrape")
