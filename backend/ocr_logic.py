_reader = None  # Lazy singleton

def get_reader():
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(['en'])
    return _reader

def extract_text(image_path: str) -> set:
    """
    Extracts text from an image and returns a set of lowercase words.
    Using a set makes it easy to compute set differences.
    """
    results = get_reader().readtext(image_path)
    text_set = set()
    for res in results:
        # res is a tuple: (bbox, text, confidence)
        words = res[1].lower().split()
        text_set.update(words)
    return text_set

def check_ocr_violation(original_image_path: str, suspect_image_path: str) -> dict:
    """
    Compares text found in the suspect image against the original.
    If the suspect has new text (handles, watermarks, ads), it flags an OCR violation.
    """
    original_text = extract_text(original_image_path)
    suspect_text = extract_text(suspect_image_path)
    
    # Find words in suspect that aren't in original
    added_text = suspect_text - original_text
    
    # We require the added text to be somewhat substantial or specific
    # For now, any new word flags it, but you can add logic to ignore short generic words.
    is_violation = len(added_text) > 0
    
    return {
        "text_added": is_violation,
        "new_words_extracted": list(added_text)
    }
