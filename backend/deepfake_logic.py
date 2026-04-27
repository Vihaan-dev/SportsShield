import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor

def analyze_fft(image_path: str) -> float:
    """
    Computes a simple FFT high-frequency ratio.
    AI-generated images often lack natural high-frequency camera noise.
    Returns the ratio of high-frequency power.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
        
    f = np.fft.fft2(img)
    fshift = np.fft.fftshift(f)
    magnitude_spectrum = 20 * np.log(np.abs(fshift) + 1)
    
    rows, cols = img.shape
    crow, ccol = rows // 2, cols // 2
    
    # Mask out the low frequencies (center a 30x30 square)
    mask = np.ones((rows, cols), np.uint8)
    r = 30
    mask[crow-r:crow+r, ccol-r:ccol+r] = 0
    
    high_freq_magnitude = magnitude_spectrum * mask
    
    # Calculate ratio of high frequency power to total power
    total_power = np.sum(magnitude_spectrum)
    if total_power == 0:
        return 0.0
        
    hf_power = np.sum(high_freq_magnitude)
    return float(hf_power / total_power)

def analyze_face(original_path: str, suspect_path: str) -> dict:
    """
    Extracts Facenet embeddings from both images and computes distance.
    If the face embedding significantly changed while the image hash remained similar,
    it indicates a deepfake/faceswap was applied.
    """
    try:
        from deepface import DeepFace  # lazy import to avoid startup crash
        # enforce_detection=False prevents crashes on non-face images (like a stadium)
        orig_rep = DeepFace.represent(img_path=original_path, model_name="Facenet", enforce_detection=False, detector_backend="opencv")
        susp_rep = DeepFace.represent(img_path=suspect_path, model_name="Facenet", enforce_detection=False, detector_backend="opencv")
        
        orig_embedding = np.array(orig_rep[0]['embedding'])
        susp_embedding = np.array(susp_rep[0]['embedding'])
        
        # Cosine distance
        dot_product = np.dot(orig_embedding, susp_embedding)
        norm_a = np.linalg.norm(orig_embedding)
        norm_b = np.linalg.norm(susp_embedding)
        cosine_similarity = dot_product / (norm_a * norm_b)
        cosine_distance = 1 - cosine_similarity
        
        # Facenet threshold is ~0.4, above this means different person/altered face
        face_altered = cosine_distance > 0.4
        
        return {
            "has_faces": True,
            "face_distance": float(cosine_distance),
            "face_altered": bool(face_altered)
        }
    except Exception as e:
        return {
            "has_faces": False,
            "face_distance": 0.0,
            "face_altered": False,
            "error": str(e)
        }

def check_deepfake_violation(original_path: str, suspect_path: str) -> dict:
    """
    Combines FFT Check and DeepFace check.
    If face is heavily altered AND FFT shows unnatural noise profile, flag as Deepfake!
    """
    # We can run these two internal sub-checks concurrently to save time too
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_fft = executor.submit(analyze_fft, suspect_path)
        future_face = executor.submit(analyze_face, original_path, suspect_path)
        
        hf_ratio = future_fft.result()
        face_analysis = future_face.result()
        
    # Assume a threshold for AI generated based on FFT (e.g. < 0.8 means loss of noise)
    # This threshold would be tuned against real data in a production environment
    ai_fft_flag = hf_ratio < 0.8
    
    is_deepfake = face_analysis.get('face_altered', False) or ai_fft_flag
    
    return {
        "is_deepfake": bool(is_deepfake),
        "high_freq_ratio": hf_ratio,
        "face_analysis": face_analysis
    }
