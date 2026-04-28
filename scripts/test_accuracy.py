"""
Accuracy test script for the Digital Asset Protection pipeline.
Registers original assets, then runs every test image through /detect
and measures classification accuracy per category.
"""
import os
import glob
import requests
import time

BASE_URL = "http://127.0.0.1:8000"
DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "test_dataset")

# Expected violation types per folder.
# type4 folders contain mixed modifications, we accept EITHER constituent type.
EXPECTED = {
    "type1_compressed": ["Type 1"],
    "type1_cropped": ["Type 1"],
    "type2_text_overlay": ["Type 2"],
    "type2_watermarked": ["Type 2"],
    "type3_ai_simulated": ["Type 3"],
    "type4_mixed_crop_text": ["Type 1", "Type 2"],           # crop + text → either is acceptable
    "type4_mixed_compress_watermark": ["Type 1", "Type 2"],  # compress + watermark → either is acceptable
}


def canonical_violation_type(label: str) -> str:
    if not label:
        return "Clear"

    if "Type 1" in label:
        return "Type 1"
    if "Type 2" in label:
        return "Type 2"
    if "Type 3" in label:
        return "Type 3"
    if "clear" in label.lower():
        return "Clear"
    return label


def matches_expected(predicted_label: str, accepted_types) -> bool:
    canonical_label = canonical_violation_type(predicted_label)
    return canonical_label in accepted_types


def register_originals():
    originals_dir = os.path.join(DATASET_DIR, "originals")
    files = sorted(glob.glob(os.path.join(originals_dir, "*.*")))
    print(f"📦 Registering {len(files)} original images...")
    
    for file_path in files:
        success = False
        for attempt in range(3):
            try:
                with open(file_path, "rb") as f:
                    res = requests.post(
                        f"{BASE_URL}/register",
                        data={"owner": "Accuracy Tester"},
                        files={"file": (os.path.basename(file_path), f, "image/jpeg")},
                        timeout=30
                    )
                if res.status_code == 200:
                    print(f"  ✅ Registered {os.path.basename(file_path)}")
                    success = True
                    break
                else:
                    print(f"  ⚠️ Attempt {attempt+1} failed for {os.path.basename(file_path)}: {res.status_code}")
            except Exception as e:
                print(f"  ⚠️ Attempt {attempt+1} error for {os.path.basename(file_path)}: {e}")
            time.sleep(1)
        
        if not success:
            print(f"  ❌ Failed to register {os.path.basename(file_path)} after 3 attempts.")
        time.sleep(1) # Small gap for sequential processing safety on Mac


def run_tests():
    folders = sorted([f for f in os.listdir(DATASET_DIR) 
                      if os.path.isdir(os.path.join(DATASET_DIR, f)) and f != "originals"])
    
    total = 0
    correct = 0
    results_by_folder = {}

    for folder in folders:
        folder_path = os.path.join(DATASET_DIR, folder)
        files = sorted(glob.glob(os.path.join(folder_path, "*.*")))
        
        accepted_types = EXPECTED.get(folder, ["Type 1"])
        results_by_folder[folder] = {"total": 0, "correct": 0, "expected": accepted_types, "details": []}
        
        print(f"\n{'─'*60}")
        print(f"📂 {folder}  (Expected: {' or '.join(accepted_types)})")
        print(f"{'─'*60}")
        
        for file_path in files:
            total += 1
            results_by_folder[folder]["total"] += 1
            fname = os.path.basename(file_path)
            
            with open(file_path, "rb") as f:
                try:
                    res = requests.post(f"{BASE_URL}/detect", files={"file": (fname, f, "image/jpeg")})
                    
                    if res.status_code == 200:
                        data = res.json()
                        violation_type = data.get("violation_type", "Clear")
                        scores = data.get("classification_scores", {})
                        
                        # Check the canonical class rather than the exact descriptive label.
                        is_correct = matches_expected(violation_type, accepted_types)
                        canonical_type = canonical_violation_type(violation_type)
                        
                        if is_correct:
                            correct += 1
                            results_by_folder[folder]["correct"] += 1
                        
                        status = "✅" if is_correct else "❌"
                        score_str = "  ".join([f"{k.split('-')[0].strip()}: {v:.2f}" for k, v in scores.items()])
                        print(f"  {status} {fname:<28} → {canonical_type}")
                        if scores:
                            print(f"     Scores: {score_str}")
                        
                        results_by_folder[folder]["details"].append({
                            "file": fname,
                            "predicted": canonical_type,
                            "correct": is_correct,
                            "scores": scores,
                        })
                    else:
                        print(f"  ❌ HTTP {res.status_code}: {res.text[:80]}")
                except Exception as e:
                    print(f"  ❌ Exception: {e}")

    # Summary
    print(f"\n{'═'*60}")
    print(f"{'ACCURACY SUMMARY':^60}")
    print(f"{'═'*60}")
    
    for folder, stats in results_by_folder.items():
        acc = (stats["correct"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        bar = "█" * int(acc / 5) + "░" * (20 - int(acc / 5))
        print(f"  {folder:<40} {bar} {stats['correct']}/{stats['total']} ({acc:.0f}%)")
        
    overall = (correct / total) * 100 if total > 0 else 0
    print(f"\n  {'OVERALL PIPELINE ACCURACY':<40} {correct}/{total}  ({overall:.1f}%)")
    print(f"{'═'*60}\n")
    
    return overall


if __name__ == "__main__":
    print("🔬 Starting Accuracy Test Suite\n")
    register_originals()
    time.sleep(2)
    accuracy = run_tests()
    
    if accuracy >= 80:
        print("🎉 Pipeline accuracy is GOOD (≥80%)")
    elif accuracy >= 60:
        print("⚠️  Pipeline accuracy is MODERATE (60-80%). Consider threshold tuning.")
    else:
        print("🚨 Pipeline accuracy is LOW (<60%). Needs significant improvement.")
