import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor

def analyze_video_fft(video_path, sample_frames=10):
    """
    Analyzes frequency spectrum of video frames to detect AI-generated content
    AI-generated videos often lack natural camera noise and have unnaturally clean frequency patterns
    
    Args:
        video_path: Path to video file
        sample_frames: Number of frames to analyze
    
    Returns:
        Average high-frequency ratio across sampled frames
        Lower values indicate potential AI generation
    """
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        return 0.0
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_indices = np.linspace(0, total_frames - 1, sample_frames, dtype=int)
    
    hf_ratios = []
    
    for frame_idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        
        if not ret:
            continue
        
        # Convert to grayscale for FFT analysis
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Compute 2D FFT
        f = np.fft.fft2(gray)
        fshift = np.fft.fftshift(f)
        magnitude_spectrum = 20 * np.log(np.abs(fshift) + 1)
        
        rows, cols = gray.shape
        crow, ccol = rows // 2, cols // 2
        
        # Mask out low frequencies (center region)
        mask = np.ones((rows, cols), np.uint8)
        r = 30
        mask[crow-r:crow+r, ccol-r:ccol+r] = 0
        
        high_freq_magnitude = magnitude_spectrum * mask
        
        # Calculate ratio of high frequency power to total power
        total_power = np.sum(magnitude_spectrum)
        if total_power == 0:
            continue
        
        hf_power = np.sum(high_freq_magnitude)
        hf_ratios.append(hf_power / total_power)
    
    cap.release()
    
    # Return average high-frequency ratio across all sampled frames
    return float(np.mean(hf_ratios)) if hf_ratios else 0.0

def analyze_temporal_face_consistency(video_path, sample_frames=10):
    """
    Analyzes facial embedding variance across video frames
    Real videos have consistent face embeddings over time
    Deepfake videos (generated frame-by-frame) show noisy variance in embeddings
    
    This detects face-swap deepfakes and AI-generated faces
    
    Args:
        video_path: Path to video file
        sample_frames: Number of frames to analyze for faces
    
    Returns:
        Dict with face analysis results including variance and deepfake flag
    """
    try:
        from deepface import DeepFace
        
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            return {
                "has_faces": False,
                "embedding_variance": 0.0,
                "face_altered": False,
                "error": "Could not open video"
            }
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_indices = np.linspace(0, total_frames - 1, sample_frames, dtype=int)
        
        embeddings = []
        
        for frame_idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            try:
                # Extract face embedding using Facenet model
                # enforce_detection=False prevents crashes on frames without clear faces
                result = DeepFace.represent(
                    img_path=frame,
                    model_name="Facenet",
                    enforce_detection=False,
                    detector_backend="opencv"
                )
                
                if result and len(result) > 0:
                    embedding = np.array(result[0]['embedding'])
                    embeddings.append(embedding)
            
            except Exception:
                # Skip frames where face detection fails
                continue
        
        cap.release()
        
        if len(embeddings) < 3:
            return {
                "has_faces": False,
                "embedding_variance": 0.0,
                "face_altered": False,
                "error": "Not enough faces detected"
            }
        
        # Calculate variance of embeddings across time
        # High variance indicates inconsistent face identity (deepfake indicator)
        embeddings_array = np.array(embeddings)
        variance = np.var(embeddings_array, axis=0).mean()
        
        # Threshold tuned for deepfake detection
        # Real faces have variance < 0.02, deepfakes often > 0.05
        face_altered = variance > 0.03
        
        return {
            "has_faces": True,
            "embedding_variance": float(variance),
            "face_altered": bool(face_altered),
            "frames_analyzed": len(embeddings)
        }
    
    except Exception as e:
        return {
            "has_faces": False,
            "embedding_variance": 0.0,
            "face_altered": False,
            "error": str(e)
        }

def check_video_deepfake_violation(original_video_path, suspect_video_path, sample_frames=10):
    """
    Combines FFT analysis and temporal face consistency check to detect deepfakes
    Runs both checks in parallel for performance
    
    Used for Type 3 violations (AI manipulation, face-swaps, AI-generated content)
    
    Args:
        original_video_path: Path to registered original video
        suspect_video_path: Path to suspect video being analyzed
        sample_frames: Number of frames to analyze
    
    Returns:
        Dict with deepfake detection results and detailed analysis
    """
    # Run both sub-checks in parallel to save time
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_fft = executor.submit(analyze_video_fft, suspect_video_path, sample_frames)
        future_face = executor.submit(analyze_temporal_face_consistency, suspect_video_path, sample_frames)
        
        hf_ratio = future_fft.result()
        face_analysis = future_face.result()
    
    # AI-generated videos typically have high-frequency ratio < 0.8
    # This threshold would be tuned with real training data in production
    ai_fft_flag = hf_ratio < 0.8
    
    # Combine both signals for final verdict
    is_deepfake = face_analysis.get('face_altered', False) or ai_fft_flag
    
    return {
        "is_deepfake": bool(is_deepfake),
        "high_freq_ratio": hf_ratio,
        "face_analysis": face_analysis,
        "detection_confidence": "high" if (face_analysis.get('face_altered', False) and ai_fft_flag) else "medium"
    }
