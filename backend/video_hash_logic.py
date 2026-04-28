import os
import cv2
import faiss
import numpy as np
import imagehash
from PIL import Image

FAISS_VIDEO_INDEX_PATH = "../data/faiss_video.index"
VECTOR_DIMENSION = 64

# Load existing FAISS index or create new one
# This index stores perceptual hashes of video keyframes for fast similarity search
if os.path.exists(FAISS_VIDEO_INDEX_PATH):
    index = faiss.read_index(FAISS_VIDEO_INDEX_PATH)
else:
    index = faiss.IndexFlatL2(VECTOR_DIMENSION)

def extract_keyframes(video_path, interval_seconds=3):
    """
    Extracts keyframes from video at regular intervals
    Used to create a fingerprint of the video without processing every single frame
    
    Args:
        video_path: Path to the video file
        interval_seconds: Extract one frame every N seconds (default 3)
    
    Returns:
        List of numpy arrays representing extracted frames
    """
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        return []
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = int(fps * interval_seconds)
    
    keyframes = []
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Extract frame at specified intervals
        if frame_count % frame_interval == 0:
            keyframes.append(frame)
        
        frame_count += 1
    
    cap.release()
    return keyframes

def compute_video_phash(video_path, interval_seconds=3):
    """
    Computes perceptual hash for each keyframe in the video
    Returns BOTH average hash (for structural similarity) AND individual frame hashes
    
    This creates a structural fingerprint of the video that is resistant to:
    - Compression artifacts
    - Minor color changes
    - Small crops
    
    Args:
        video_path: Path to video file
        interval_seconds: Keyframe extraction interval
    
    Returns:
        Tuple of (average_hash_vector, list_of_frame_hash_strings, individual_hash_vectors)
    """
    keyframes = extract_keyframes(video_path, interval_seconds)
    
    if not keyframes:
        return None, [], []
    
    hash_vectors = []
    hash_strings = []
    
    for frame in keyframes:
        # Convert BGR (OpenCV) to RGB (PIL)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_frame)
        
        # Compute perceptual hash for this frame
        hash_obj = imagehash.phash(pil_image)
        hash_array = np.array(hash_obj.hash, dtype='float32').flatten()
        
        hash_vectors.append(hash_array)
        hash_strings.append(str(hash_obj))
    
    # Average all keyframe hashes to create a single video fingerprint
    # This makes the hash robust to minor edits like trimming a few frames
    avg_hash_vector = np.mean(hash_vectors, axis=0).astype('float32')
    
    return avg_hash_vector, hash_strings, hash_vectors

def add_to_index(hash_vector):
    """
    Adds a video hash vector to the FAISS index and persists to disk
    
    Args:
        hash_vector: 64-dimensional float32 numpy array
    
    Returns:
        Integer FAISS ID assigned to this vector (auto-incremented)
    """
    assigned_id = index.ntotal
    vector_2d = np.expand_dims(hash_vector, axis=0)
    index.add(vector_2d)
    faiss.write_index(index, FAISS_VIDEO_INDEX_PATH)
    return assigned_id

def search_index(hash_vector, top_k=1):
    """
    Searches the FAISS index for nearest neighbor videos
    Uses L2 distance to find structurally similar videos
    
    Args:
        hash_vector: Query vector (64-dim float32)
        top_k: Number of closest matches to return
    
    Returns:
        List of dicts with 'faiss_id' and 'distance' keys
        Lower distance = more similar videos
    """
    if index.ntotal == 0:
        return []
    
    vector_2d = np.expand_dims(hash_vector, axis=0)
    distances, indices = index.search(vector_2d, top_k)
    
    results = []
    for dist, faiss_id in zip(distances[0], indices[0]):
        if faiss_id != -1:
            results.append({
                "faiss_id": int(faiss_id),
                "distance": float(dist)
            })
    
    return results
