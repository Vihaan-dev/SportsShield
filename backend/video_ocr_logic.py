import cv2
import numpy as np

# Lazy load EasyOCR to avoid startup delays
_reader = None

def get_reader():
    """
    Lazy singleton for EasyOCR reader
    Only loads when first OCR operation is performed to save memory and startup time
    """
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(['en'])
    return _reader

def extract_text_from_frames(video_path, sample_frames=5):
    """
    Extracts text from multiple frames in a video
    Samples frames evenly throughout the video to catch text overlays
    
    Args:
        video_path: Path to video file
        sample_frames: Number of frames to sample for text extraction
    
    Returns:
        Set of lowercase words found across all sampled frames
    """
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        return set()
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Calculate frame indices to sample evenly throughout video
    frame_indices = np.linspace(0, total_frames - 1, sample_frames, dtype=int)
    
    text_set = set()
    reader = get_reader()
    
    for frame_idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        
        if not ret:
            continue
        
        # Convert BGR to RGB for EasyOCR
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Extract text from this frame
        results = reader.readtext(rgb_frame)
        
        for res in results:
            # res is tuple: (bbox, text, confidence)
            words = res[1].lower().split()
            text_set.update(words)
    
    cap.release()
    return text_set

def check_video_ocr_violation(original_video_path, suspect_video_path, sample_frames=5):
    """
    Compares text found in suspect video against original video
    Detects unauthorized watermarks, handles, captions, or promotional text
    
    This is used for Type 2 violations where someone adds their branding to stolen content
    
    Args:
        original_video_path: Path to registered original video
        suspect_video_path: Path to suspect video being analyzed
        sample_frames: Number of frames to sample from each video
    
    Returns:
        Dict with 'text_added' boolean and 'new_words_extracted' list
    """
    original_text = extract_text_from_frames(original_video_path, sample_frames)
    suspect_text = extract_text_from_frames(suspect_video_path, sample_frames)
    
    # Find words present in suspect but not in original
    added_text = suspect_text - original_text
    
    # Flag as violation if any new text was added
    is_violation = len(added_text) > 0
    
    return {
        "text_added": is_violation,
        "new_words_extracted": list(added_text)
    }
