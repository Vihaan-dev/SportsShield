import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image
from dotenv import load_dotenv

# Load environment from the repository root and backend folder.
_ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT_DIR / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

_LOCK = threading.Lock()
_KEY_INDEX = 0


def _collect_api_keys() -> List[str]:
    keys: List[str] = []

    raw_keys = os.getenv("GEMINI_API_KEYS", "").strip()
    if raw_keys:
        keys.extend([key.strip() for key in raw_keys.split(",") if key.strip()])

    for index in range(1, 21):
        key = os.getenv(f"GEMINI_API_KEY_{index}", "").strip()
        if key:
            keys.append(key)

    single_key = os.getenv("GEMINI_API_KEY", "").strip()
    if single_key:
        keys.append(single_key)

    deduped: List[str] = []
    seen = set()
    for key in keys:
        if key not in seen:
            seen.add(key)
            deduped.append(key)
    return deduped


def _next_key_index(total_keys: int) -> int:
    global _KEY_INDEX
    with _LOCK:
        key_index = _KEY_INDEX % total_keys
        _KEY_INDEX = (_KEY_INDEX + 1) % total_keys
        return key_index


def _prepare_image(image_path: str) -> Image.Image:
    image = Image.open(image_path).convert("RGB")
    image.thumbnail((1024, 1024))
    return image


def _fallback_explanation(local_evidence: Dict[str, Any]) -> Dict[str, Any]:
    ai_confidence = float(local_evidence.get("ai_confidence_score", 0.0))
    ssim = float(local_evidence.get("ssim_score", 0.0))
    hist_corr = float(local_evidence.get("histogram_correlation", 0.0))
    explanation = (
        "The local vision pipeline flagged this as AI-generated because the suspect image keeps the same overall scene "
        f"but shows structural drift (SSIM {ssim:.3f}) and colour/frequency changes (histogram correlation {hist_corr:.3f}, "
        f"AI confidence {ai_confidence:.2f})."
    )
    return {
        "enabled": False,
        "provider": "local-fallback",
        "model": None,
        "api_key_index": None,
        "used_media": {"original": True, "suspect": True},
        "explanation": explanation,
        "status": "fallback",
    }


def generate_type3_explanation(
    original_path: str,
    suspect_path: str,
    local_evidence: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate a short human-readable explanation for Type 3 detections.
    Gemini is only used here, after the local model has already decided.
    """
    api_keys = _collect_api_keys()
    if not api_keys:
        return _fallback_explanation(local_evidence)

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.2"))
    max_output_tokens = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "220"))

    evidence_lines = [
        f"Local verdict: {local_evidence.get('violation_type', 'Type 3')}",
        f"Classification scores: {local_evidence.get('classification_scores', {})}",
        f"Distance: {local_evidence.get('distance')}",
        f"SSIM: {local_evidence.get('ssim_score')}",
        f"Histogram correlation: {local_evidence.get('histogram_correlation')}",
        f"AI confidence: {local_evidence.get('ai_confidence_score')}",
        f"OCR detected: {local_evidence.get('ocr_detected')}",
        f"Overlay detected: {local_evidence.get('overlay_detected')}",
        f"Overlay score: {local_evidence.get('overlay_score')}",
        f"CLIP status: {local_evidence.get('clip_status')}",
    ]

    prompt = (
        "You are writing a concise product explanation for an image security dashboard. "
        "Explain why the suspect image is likely AI-generated or deepfake altered. "
        "Use only the provided evidence and the original/suspect images. "
        "Keep it to 2-3 short sentences, plain English, and mention the strongest signals. "
        "Do not mention watermark or crop explanations unless the evidence clearly supports them.\n\n"
        + "\n".join(evidence_lines)
    )

    fallback = _fallback_explanation(local_evidence)

    try:
        import google.generativeai as genai
    except Exception as exc:
        fallback.update({"status": "gemini_unavailable", "error": str(exc)})
        return fallback

    last_error: Optional[str] = None
    start_index = _next_key_index(len(api_keys))

    for attempt in range(len(api_keys)):
        key_index = (start_index + attempt) % len(api_keys)
        api_key = api_keys[key_index]

        try:
            with _LOCK:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=(
                        "You explain AI-image detection results. Be concise, factual, and avoid speculation."
                    ),
                )
                original_image = _prepare_image(original_path)
                suspect_image = _prepare_image(suspect_path)
                response = model.generate_content(
                    [prompt, original_image, suspect_image],
                    generation_config={
                        "temperature": temperature,
                        "max_output_tokens": max_output_tokens,
                    },
                )

            text = getattr(response, "text", "") or ""
            text = " ".join(text.split())
            if not text:
                raise RuntimeError("Gemini returned an empty response")

            return {
                "enabled": True,
                "provider": "gemini",
                "model": model_name,
                "api_key_index": key_index,
                "used_media": {"original": True, "suspect": True},
                "explanation": text,
                "status": "ok",
            }
        except Exception as exc:
            last_error = str(exc)
            continue

    fallback.update({"status": "gemini_error", "error": last_error})
    return fallback
