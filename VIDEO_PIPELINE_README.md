# Video Detection Pipeline

This directory contains the complete video asset protection pipeline, kept separate from the image pipeline for modularity.

## Architecture Overview

The video pipeline mirrors the image pipeline but operates on video keyframes:

```
Video Upload → Keyframe Extraction → pHash per Frame → Average Hash → FAISS Index → Database
```

## Files and Their Purpose

### 1. `generate_test_videos.py` (scripts/)
**Purpose**: Generates test video variants from seed videos

**What it does**:
- Takes original videos from `data/seed_videos/`
- Creates 7 manipulation types per video:
  - `type1_trimmed`: Removes first/last 10% of frames (simulates clip theft)
  - `type1_compressed`: Adds noise to simulate low-quality re-encoding
  - `type1_cropped`: Crops 15% from all edges (removes watermarks)
  - `type2_text_overlay`: Adds fake social media handle text
  - `type2_logo_overlay`: Adds fake branding rectangle
  - `type3_color_graded`: Heavy color manipulation (simulates AI filter)
  - `type4_mixed_trim_text`: Combination of trimming + text overlay
- Outputs to `data/test_video_dataset/`

**Usage**:
```bash
# Place seed videos in data/seed_videos/
python scripts/generate_test_videos.py
```

### 2. `video_hash_logic.py` (backend/)
**Purpose**: Computes perceptual hashes from video keyframes

**Key functions**:
- `extract_keyframes(video_path, interval_seconds=3)`: Extracts one frame every 3 seconds
- `compute_video_phash(video_path)`: Computes pHash for each keyframe, returns average
- `add_to_index(hash_vector)`: Adds to FAISS index, returns faiss_id
- `search_index(hash_vector, top_k=1)`: Finds nearest neighbor videos by L2 distance

**How it works**:
- Extracts keyframes at regular intervals (default: every 3 seconds)
- Computes 64-bit perceptual hash for each keyframe using imagehash
- Averages all keyframe hashes into single 64-dim vector
- This makes the fingerprint robust to minor edits like trimming a few frames

**FAISS Index**: Stored in `data/faiss_video.index` (separate from image index)

### 3. `video_ocr_logic.py` (backend/)
**Purpose**: Detects text overlays added to videos

**Key functions**:
- `extract_text_from_frames(video_path, sample_frames=5)`: Samples frames and extracts text
- `check_video_ocr_violation(original_path, suspect_path)`: Compares text between videos

**How it works**:
- Samples 5 frames evenly throughout the video
- Runs EasyOCR on each frame to extract text
- Compares suspect text vs original text (set difference)
- Flags as Type 2 violation if new text found

**Use case**: Detects when someone adds their watermark/handle to stolen sports clips

### 4. `video_deepfake_logic.py` (backend/)
**Purpose**: Detects AI-manipulated videos using two methods

**Key functions**:
- `analyze_video_fft(video_path, sample_frames=10)`: FFT frequency analysis
- `analyze_temporal_face_consistency(video_path)`: Face embedding variance check
- `check_video_deepfake_violation(original_path, suspect_path)`: Combined deepfake detection

**How it works**:

**Method A - FFT Analysis**:
- Samples 10 frames from video
- Computes 2D FFT on each frame
- Calculates high-frequency power ratio
- AI-generated videos lack camera noise (ratio < 0.8)

**Method B - Temporal Face Consistency**:
- Extracts face embeddings from multiple frames using DeepFace (Facenet)
- Calculates variance of embeddings across time
- Real faces have consistent embeddings (low variance)
- Deepfake faces (generated per-frame) have high variance (> 0.03)

**Both run in parallel via ThreadPoolExecutor**

**Use case**: Detects face-swaps, AI-generated content, heavily filtered videos

### 5. `video_database.py` (backend/)
**Purpose**: SQLAlchemy model for video asset storage

**Schema**:
```python
VideoAssetRecord:
    - asset_id: "video_1234567890"
    - faiss_id: Position in FAISS index
    - clip_faiss_id: Position in CLIP index (not implemented, set to -1)
    - filepath: Path to original video
    - owner: "Official Broadcaster"
    - timestamp: Unix timestamp
    - signature: SHA-256 provenance hash
    - duration: Video length in seconds
    - fps: Frames per second
    - resolution: "1920x1080"
```

**Database**: Stored in `data/video_assets.db` (separate from image database)

### 6. `video_api.py` (backend/)
**Purpose**: FastAPI endpoint handlers for video operations

**Functions**:
- `register_video_asset(file, owner)`: Registers original video
- `analyze_suspect_video(file_path, filename)`: Runs detection pipeline
- `detect_video_asset(file)`: Endpoint handler for video detection
- `simulate_video_scrape()`: Fake scraping for demo (picks random test video)

**Detection Pipeline**:
```
1. Compute pHash from keyframes
2. FAISS search for closest match
3. Distance-based decision tree:
   - Distance < 8: Type 1 (Exact Repost)
   - Distance 8-25: Run OCR + Deepfake checks in parallel
     → Deepfake detected: Type 3
     → Text added: Type 2
   - Distance > 25: Clear (no match)
4. Append fake social metadata (platform, location)
5. Return results to frontend
```

## Complete Workflow

### Setup Phase
```bash
# 1. Place seed videos
mkdir -p data/seed_videos
# Add your sports videos here (mp4, avi, mov, mkv)

# 2. Generate test variants
python scripts/generate_test_videos.py
# Creates ~7 variants per seed video in data/test_video_dataset/

# 3. Start backend (if integrating into main.py)
cd backend
python main.py
```

### Registration Phase
```python
# User uploads original video via frontend
# Backend calls register_video_asset():
#   - Saves to data/true_videos/
#   - Extracts keyframes every 3 seconds
#   - Computes average pHash
#   - Stores in FAISS index
#   - Creates database record with metadata
```

### Detection Phase
```python
# Simulated scraping picks random test video
# Backend calls analyze_suspect_video():
#   - Computes pHash from keyframes
#   - FAISS finds closest registered video
#   - Calculates distance
#   - Runs OCR + Deepfake checks if distance 8-25
#   - Returns classification + fake social metadata
# Frontend displays on map + feed
```

## Integration with Main Application

To integrate into `main.py`, add these endpoints:

```python
from video_api import register_video_asset, detect_video_asset, simulate_video_scrape

@app.post("/register_video", response_model=VideoAssetResponse)
async def register_video(file: UploadFile = File(...), owner: str = Form("Unknown")):
    return register_video_asset(file, owner)

@app.post("/detect_video")
async def detect_video(file: UploadFile = File(...)):
    return detect_video_asset(file)

@app.get("/simulate_video_scrape")
def simulate_video_scrape_endpoint():
    return simulate_video_scrape()
```

## Current Limitations

### What Works
✅ Keyframe extraction and pHash computation
✅ FAISS indexing for structural similarity
✅ OCR text overlay detection
✅ Deepfake detection (FFT + face embeddings)
✅ Distance-based classification
✅ Fake scraping from test dataset

### What's Missing
❌ CLIP semantic embeddings for videos (not computed during registration)
❌ Real web scraping (Twitter/YouTube/TikTok APIs)
❌ Real geolocation data (locations are random from hardcoded list)
❌ Audio fingerprinting (only visual analysis)
❌ Scene detection for better keyframe selection
❌ Gemini AI analysis integration

### Known Issues
- CLIP semantic matching is broken (clip_faiss_id always -1)
- Distance > 25 always returns "clear" (no semantic fallback)
- Location data is 100% fake random
- Scraping just loops through same test files

## Performance Notes

**Keyframe extraction**: ~1-2 seconds for 30-second video
**pHash computation**: ~0.5 seconds per keyframe
**FAISS search**: < 1ms
**OCR check**: ~2-3 seconds (5 frames)
**Deepfake check**: ~5-8 seconds (10 frames with face detection)
**Total detection time**: ~10-15 seconds per video

## Demo Strategy

For prototype/hackathon:
1. Generate 10-15 test videos with diverse content
2. Register all originals before presenting
3. Let auto-scrape run for 2-3 minutes to populate map
4. Show live detection feed with violations appearing
5. Click map clusters to filter threats by location
6. Emphasize real-time monitoring illusion

**The system is a working demo for video manipulation detection but has no real scraping capability.**
