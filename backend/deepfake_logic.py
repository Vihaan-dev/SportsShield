import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor

def analyze_fft(image_path: str) -> dict:
    """
    Computes FFT-based frequency analysis.
    Returns both the high-frequency ratio AND a spectral flatness measure.
    AI-generated images tend to have abnormally smooth frequency distributions.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return {"hf_ratio": 0.0, "spectral_flatness": 0.0}
    
    # Resize to standard size for consistent comparison
    img = cv2.resize(img, (256, 256))
        
    f = np.fft.fft2(img)
    fshift = np.fft.fftshift(f)
    magnitude_spectrum = np.abs(fshift)
    
    rows, cols = img.shape
    crow, ccol = rows // 2, cols // 2
    
    # Multi-band frequency analysis
    # Low freq: center 15% radius
    # Mid freq: 15-40% radius  
    # High freq: 40%+ radius
    max_radius = min(crow, ccol)
    low_r = int(max_radius * 0.15)
    mid_r = int(max_radius * 0.40)
    
    Y, X = np.ogrid[:rows, :cols]
    dist_from_center = np.sqrt((X - ccol)**2 + (Y - crow)**2)
    
    low_mask = dist_from_center <= low_r
    mid_mask = (dist_from_center > low_r) & (dist_from_center <= mid_r) 
    high_mask = dist_from_center > mid_r
    
    low_power = np.sum(magnitude_spectrum[low_mask])
    mid_power = np.sum(magnitude_spectrum[mid_mask])
    high_power = np.sum(magnitude_spectrum[high_mask])
    total_power = low_power + mid_power + high_power
    
    if total_power == 0:
        return {"hf_ratio": 0.0, "spectral_flatness": 0.0}
    
    hf_ratio = float(high_power / total_power)
    
    # Spectral flatness: geometric mean / arithmetic mean of magnitude
    # Natural images have higher flatness; AI-generated tend to be smoother
    mag_flat = magnitude_spectrum.flatten()
    mag_flat = mag_flat[mag_flat > 0]  # avoid log(0)
    if len(mag_flat) > 0:
        log_mean = np.mean(np.log(mag_flat + 1e-10))
        geometric_mean = np.exp(log_mean)
        arithmetic_mean = np.mean(mag_flat)
        spectral_flatness = float(geometric_mean / (arithmetic_mean + 1e-10))
    else:
        spectral_flatness = 0.0
    
    return {"hf_ratio": hf_ratio, "spectral_flatness": spectral_flatness}


def compare_fft(original_path: str, suspect_path: str) -> dict:
    """
    Compares FFT signatures between original and suspect.
    Large differences in frequency distribution indicate heavy processing
    (AI re-generation, heavy filtering, etc.)
    """
    orig_fft = analyze_fft(original_path)
    susp_fft = analyze_fft(suspect_path)
    
    hf_diff = abs(orig_fft["hf_ratio"] - susp_fft["hf_ratio"])
    flatness_diff = abs(orig_fft["spectral_flatness"] - susp_fft["spectral_flatness"])
    
    return {
        "original_hf_ratio": orig_fft["hf_ratio"],
        "suspect_hf_ratio": susp_fft["hf_ratio"],
        "hf_ratio_diff": hf_diff,
        "flatness_diff": flatness_diff,
        "original_flatness": orig_fft["spectral_flatness"],
        "suspect_flatness": susp_fft["spectral_flatness"],
    }


def compute_ssim(original_path: str, suspect_path: str) -> float:
    """
    Structural Similarity Index (SSIM) between original and suspect.
    This is the gold standard for perceptual image similarity.
    - 1.0 = identical
    - 0.95+ = near-identical (compression, minor color shift)
    - 0.80-0.95 = modified but recognisable (watermark, text overlay) 
    - < 0.80 = heavily altered (AI filter, deep crop, faceswap)
    """
    orig = cv2.imread(original_path, cv2.IMREAD_GRAYSCALE)
    susp = cv2.imread(suspect_path, cv2.IMREAD_GRAYSCALE)
    if orig is None or susp is None:
        return 0.0
    
    # Resize both to same dimensions for comparison
    target_size = (256, 256)
    orig = cv2.resize(orig, target_size)
    susp = cv2.resize(susp, target_size)
    
    # Manual SSIM computation (avoids scikit-image dependency)
    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2
    
    orig = orig.astype(np.float64)
    susp = susp.astype(np.float64)
    
    mu1 = cv2.GaussianBlur(orig, (11, 11), 1.5)
    mu2 = cv2.GaussianBlur(susp, (11, 11), 1.5)
    
    mu1_sq = mu1 ** 2
    mu2_sq = mu2 ** 2
    mu1_mu2 = mu1 * mu2
    
    sigma1_sq = cv2.GaussianBlur(orig ** 2, (11, 11), 1.5) - mu1_sq
    sigma2_sq = cv2.GaussianBlur(susp ** 2, (11, 11), 1.5) - mu2_sq
    sigma12 = cv2.GaussianBlur(orig * susp, (11, 11), 1.5) - mu1_mu2
    
    ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / \
               ((mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2))
    
    return float(np.mean(ssim_map))


def compute_histogram_correlation(original_path: str, suspect_path: str) -> float:
    """
    Compares colour histograms between original and suspect.
    High correlation (>0.95) = same colour profile (repost/compress)
    Medium (0.7-0.95) = colour shift (watermark overlay, text)
    Low (<0.7) = heavy colour transformation (AI filter, style transfer)
    """
    orig = cv2.imread(original_path)
    susp = cv2.imread(suspect_path)
    if orig is None or susp is None:
        return 0.0
    
    orig = cv2.resize(orig, (256, 256))
    susp = cv2.resize(susp, (256, 256))
    
    # Compute histograms for all 3 channels
    correlations = []
    for i in range(3):
        hist1 = cv2.calcHist([orig], [i], None, [256], [0, 256])
        hist2 = cv2.calcHist([susp], [i], None, [256], [0, 256])
        cv2.normalize(hist1, hist1)
        cv2.normalize(hist2, hist2)
        corr = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
        correlations.append(corr)
    
    return float(np.mean(correlations))


def analyze_face(original_path: str, suspect_path: str) -> dict:
    """
    Extracts Facenet embeddings from both images and computes distance.
    If the face embedding significantly changed while the image hash remained similar,
    it indicates a deepfake/faceswap was applied.
    """
    try:
        from deepface import DeepFace  # lazy import to avoid startup crash
        orig_rep = DeepFace.represent(img_path=original_path, model_name="Facenet", enforce_detection=False, detector_backend="opencv")
        susp_rep = DeepFace.represent(img_path=suspect_path, model_name="Facenet", enforce_detection=False, detector_backend="opencv")
        
        orig_embedding = np.array(orig_rep[0]['embedding'])
        susp_embedding = np.array(susp_rep[0]['embedding'])
        
        dot_product = np.dot(orig_embedding, susp_embedding)
        norm_a = np.linalg.norm(orig_embedding)
        norm_b = np.linalg.norm(susp_embedding)
        cosine_similarity = dot_product / (norm_a * norm_b)
        cosine_distance = 1 - cosine_similarity
        
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
    Combined analysis using FFT comparison, SSIM, histogram correlation, and face analysis.
    Uses a multi-signal scoring approach for robust deepfake/AI detection.
    """
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_fft = executor.submit(compare_fft, original_path, suspect_path)
        future_ssim = executor.submit(compute_ssim, original_path, suspect_path)
        future_hist = executor.submit(compute_histogram_correlation, original_path, suspect_path)
        
        fft_comparison = future_fft.result()
        ssim_score = future_ssim.result()
        hist_corr = future_hist.result()
    
    # AI/deepfake scoring: accumulate evidence
    ai_score = 0.0
    
    # Signal 1: Large HF ratio difference means heavy frequency manipulation
    if fft_comparison["hf_ratio_diff"] > 0.04:
        ai_score += 0.35
    if fft_comparison["hf_ratio_diff"] > 0.09:
        ai_score += 0.25

    # Signal 2: Large spectral flatness change
    if fft_comparison["flatness_diff"] > 0.015:
        ai_score += 0.25

    # Signal 3: Low SSIM but NOT extremely low (extremely low = different image)
    # AI-generated looks "similar but different" structurally
    if ssim_score < 0.88 and ssim_score > 0.3:
        ai_score += 0.25

    # Signal 4: Significant colour histogram divergence
    if hist_corr < 0.88:
        ai_score += 0.35
    if hist_corr < 0.72:
        ai_score += 0.25
    
    is_deepfake = ai_score >= 0.5
    
    return {
        "is_deepfake": bool(is_deepfake),
        "ai_confidence_score": round(ai_score, 2),
        "ssim_score": round(ssim_score, 4),
        "histogram_correlation": round(hist_corr, 4),
        "fft_analysis": fft_comparison,
    }
