import os
import sys
sys.path.append('../backend')

from video_api import register_video_asset, analyze_suspect_video
import glob

class MockUploadFile:
    """Mock UploadFile for testing without FastAPI"""
    def __init__(self, filepath):
        self.file = open(filepath, 'rb')
        self.filename = os.path.basename(filepath)

def test_video_pipeline():
    """
    Complete test of video detection pipeline
    Tests both test_dataset and videos_to_test folders
    """
    
    print("=" * 80)
    print("VIDEO DETECTION PIPELINE TEST")
    print("=" * 80)
    print()
    
    # Step 1: Register original video
    print("STEP 1: REGISTERING ORIGINAL VIDEO")
    print("-" * 80)
    
    original_path = "../data/test_video_dataset/originals/Volleyball_original.mp4"
    
    if not os.path.exists(original_path):
        print(f"ERROR: Original video not found at {original_path}")
        print("Please run generate_test_videos.py first!")
        return
    
    original_file = MockUploadFile(original_path)
    reg_result = register_video_asset(original_file, "Official Sports League")
    
    print(f"✓ Registered: {reg_result.asset_id}")
    print(f"  Duration: {reg_result.duration:.2f}s")
    print(f"  FPS: {reg_result.fps}")
    print(f"  Resolution: {reg_result.resolution}")
    print(f"  Hash: {reg_result.avg_phash}")
    print()
    
    # Step 2: Test against test_dataset variants
    print("STEP 2: TESTING AGAINST TEST_DATASET VARIANTS")
    print("-" * 80)
    
    test_variants = [
        ("type1_trimmed/Volleyball_trimmed.mp4", "Should detect: Type 1 (Trimmed)"),
        ("type1_compressed/Volleyball_compressed.mp4", "Should detect: Type 1 (Compressed)"),
        ("type1_cropped/Volleyball_cropped.mp4", "Should detect: Type 1 or 2 (Cropped)"),
        ("type2_text_overlay/Volleyball_text.mp4", "Should detect: Type 2 (Text Overlay)"),
        ("type2_logo_overlay/Volleyball_logo.mp4", "Should detect: Type 2 (Logo)"),
        ("type3_color_graded/Volleyball_color.mp4", "Should detect: Type 3 (Color Graded)"),
        ("type4_mixed_trim_text/Volleyball_mixed.mp4", "Should detect: Type 2 or 4 (Mixed)"),
    ]
    
    for variant_path, expected in test_variants:
        full_path = f"../data/test_video_dataset/{variant_path}"
        
        if not os.path.exists(full_path):
            print(f"⚠ SKIPPED: {variant_path} (file not found)")
            continue
        
        print(f"\nTesting: {os.path.basename(variant_path)}")
        print(f"Expected: {expected}")
        
        result = analyze_suspect_video(full_path, os.path.basename(variant_path))
        
        verdict = result.get('verdict', 'unknown')
        violation_type = result.get('violation_type', 'N/A')
        distance = result.get('hamming_distance_estimate', 'N/A')
        
        if verdict == 'suspicious':
            print(f"✓ DETECTED: {violation_type}")
            print(f"  Distance: {distance}")
            
            if 'ocr_findings' in result and result['ocr_findings'].get('text_added'):
                print(f"  OCR Found: {result['ocr_findings']['new_words_extracted']}")
            
            if 'deepfake_findings' in result and result['deepfake_findings'].get('is_deepfake'):
                print(f"  Deepfake Confidence: {result['deepfake_findings'].get('detection_confidence', 'N/A')}")
        else:
            print(f"✗ NOT DETECTED: {verdict}")
            if distance != 'N/A':
                print(f"  Distance: {distance}")
    
    print()
    
    # Step 3: Test against videos_to_test (different manipulations)
    print("STEP 3: TESTING AGAINST VIDEOS_TO_TEST (DIFFERENT MANIPULATIONS)")
    print("-" * 80)
    
    videos_to_test_dir = "../data/videos_to_test"
    
    if not os.path.exists(videos_to_test_dir):
        print(f"⚠ videos_to_test folder not found!")
        print("Run generate_videos_to_test.py to create test variants.")
        print()
    else:
        test_files = glob.glob(os.path.join(videos_to_test_dir, "*.mp4"))
        
        if not test_files:
            print(f"⚠ No videos found in {videos_to_test_dir}")
            print("Run generate_videos_to_test.py first!")
        else:
            print(f"Found {len(test_files)} test videos\n")
            
            for test_file in sorted(test_files):
                filename = os.path.basename(test_file)
                
                # Determine expected behavior based on filename
                if "text" in filename.lower():
                    expected = "Type 2 (Text)"
                elif "watermark" in filename.lower():
                    expected = "Type 2 (Watermark)"
                elif "desaturated" in filename.lower() or "filter" in filename.lower():
                    expected = "Type 3 (Filter)"
                elif "rotated" in filename.lower() or "crop" in filename.lower():
                    expected = "Type 1 or 2 (Structural change)"
                elif "mirror" in filename.lower() or "flip" in filename.lower():
                    expected = "Type 1 (Mirrored)"
                elif "speed" in filename.lower():
                    expected = "Type 1 (Speed change)"
                elif "combo" in filename.lower():
                    expected = "Type 2 or 3 (Multiple)"
                else:
                    expected = "Unknown"
                
                print(f"\nTesting: {filename}")
                print(f"Expected: {expected}")
                
                result = analyze_suspect_video(test_file, filename)
                
                verdict = result.get('verdict', 'unknown')
                violation_type = result.get('violation_type', 'N/A')
                distance = result.get('hamming_distance_estimate', 'N/A')
                
                if verdict == 'suspicious':
                    print(f"✓ DETECTED: {violation_type}")
                    print(f"  Distance: {distance}")
                    
                    if 'ocr_findings' in result and result['ocr_findings'].get('text_added'):
                        words = result['ocr_findings']['new_words_extracted']
                        print(f"  OCR Found: {words[:5]}...")  # Show first 5 words
                    
                    if 'deepfake_findings' in result:
                        df = result['deepfake_findings']
                        if df.get('is_deepfake'):
                            print(f"  Deepfake: YES (confidence: {df.get('detection_confidence', 'N/A')})")
                            print(f"  FFT Ratio: {df.get('high_freq_ratio', 'N/A'):.3f}")
                elif verdict == 'clear':
                    print(f"✗ NOT DETECTED: Marked as clear")
                    if distance != 'N/A':
                        print(f"  Distance: {distance} (too high or too low)")
                else:
                    print(f"⚠ ERROR: {result.get('message', 'Unknown error')}")
    
    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print("\nSUMMARY:")
    print("- test_dataset variants: Known manipulations from generate_test_videos.py")
    print("- videos_to_test variants: Different manipulations to validate detection")
    print("\nIf videos_to_test variants are detected, your pipeline is working correctly!")
    print("If they're NOT detected, the system may be overfitting to test_dataset patterns.")
    print()

if __name__ == "__main__":
    test_video_pipeline()
