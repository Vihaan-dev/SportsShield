"""
OCR-based watermark/text detection module.
Uses EasyOCR (lazy-loaded) for text extraction, plus a lightweight 
pixel-diff approach that catches semi-transparent watermarks that
OCR engines often miss.
"""
import cv2
import numpy as np

# Disabled EasyOCR entirely to prevent macOS segmentation faults.
# We rely on the structural pixel-differencing approach below.


def detect_overlay_via_pixel_diff(original_path: str, suspect_path: str) -> dict:
    """
    Detects added overlays by aligning suspect to original and comparing 
    only the overlapping regions (intersection).
    """
    img_orig = cv2.imread(original_path)
    img_susp = cv2.imread(suspect_path)
    if img_orig is None or img_susp is None:
        return {"overlay_score": 0.0, "affected_area_pct": 0.0}

    # 1. Feature Alignment (ORB)
    orb = cv2.ORB_create(nfeatures=2000)
    kp1, des1 = orb.detectAndCompute(img_orig, None)
    kp2, des2 = orb.detectAndCompute(img_susp, None)

    aligned_susp = None
    if des1 is not None and des2 is not None:
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(des1, des2)
        if len(matches) > 15:
            src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
            M, _ = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
            if M is not None:
                aligned_susp = cv2.warpPerspective(img_susp, M, (img_orig.shape[1], img_orig.shape[0]))

    # 2. Template Matching Fallback
    if aligned_susp is None:
        s_gray = cv2.cvtColor(img_susp, cv2.COLOR_BGR2GRAY)
        o_gray = cv2.cvtColor(img_orig, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(o_gray, cv2.resize(s_gray, (int(s_gray.shape[1]*0.8), int(s_gray.shape[0]*0.8))), cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        if max_val < 0.5:
             # Just resize if alignment fails
             aligned_susp = cv2.resize(img_susp, (img_orig.shape[1], img_orig.shape[0]))
        else:
             aligned_susp = cv2.resize(img_susp, (img_orig.shape[1], img_orig.shape[0]))

    # 3. Intersection Diffing: Only look at non-zero pixels in aligned_susp
    # Convert to grayscale for diff
    gray_orig = cv2.cvtColor(img_orig, cv2.COLOR_BGR2GRAY)
    gray_susp = cv2.cvtColor(aligned_susp, cv2.COLOR_BGR2GRAY)
    
    # Create mask of where the suspect actually has pixels (ignores black bars from alignment/crop)
    mask = (gray_susp > 0).astype(np.uint8) * 255
    
    diff = cv2.absdiff(gray_orig, gray_susp)
    # Mask the diff so we only care about the overlap
    masked_diff = cv2.bitwise_and(diff, diff, mask=mask)
    
    # Sensitive Threshold: 20 (catches subtler watermarks, still ignores most compression noise)
    significant_change_mask = masked_diff > 20
    affected_pixels = np.sum(significant_change_mask)
    total_valid_pixels = np.sum(mask > 0)
    
    affected_area_pct = float(affected_pixels / total_valid_pixels) if total_valid_pixels > 0 else 0
    mean_change = float(np.mean(masked_diff[significant_change_mask]) / 255.0) if affected_pixels > 0 else 0
    
    # Score is high if area > 0.5%. Increase multipliers so smaller areas with
    # clear intensity produce higher overlay scores.
    overlay_score = min(1.0, (affected_area_pct * 7.0) + (mean_change * 2.0))
    
    return {
        "overlay_score": round(overlay_score, 4),
        "affected_area_pct": round(affected_area_pct * 100, 2),
        "mean_change_intensity": round(mean_change, 4),
    }


def check_ocr_violation(original_image_path: str, suspect_image_path: str) -> dict:
    """
    Watermark/text detection:
    Uses pixel-diff overlay detection (catches readable text, watermarks, and logos).
    (EasyOCR was removed due to Apple Silicon PyTorch segmentation faults).
    """
    # Pixel-diff overlay detection
    overlay_result = detect_overlay_via_pixel_diff(original_image_path, suspect_image_path)
    
    # An overlay affecting more than 0.4% of pixels with meaningful intensity suggests watermark/text
    # Lower thresholds to increase recall on subtle overlays while keeping precision reasonable.
    overlay_detected = overlay_result["affected_area_pct"] > 0.4 and overlay_result["mean_change_intensity"] > 0.04
    
    print(f"DEBUG OCR: Area={overlay_result['affected_area_pct']:.2f}%, Intensity={overlay_result['mean_change_intensity']:.4f} -> Detected={overlay_detected}")
    
    return {
        "text_added": overlay_detected,
        "ocr_detected": False,  # Disabled
        "overlay_detected": overlay_detected,
        "new_words_extracted": [],
        "overlay_analysis": overlay_result,
    }
