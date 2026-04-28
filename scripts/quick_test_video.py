import os
import sys
sys.path.append('../backend')

from video_hash_logic import compute_video_phash, add_to_index, search_index
import glob

def quick_test_video_pipeline():
    """
    Quick test of video hash computation and FAISS search
    Skips OCR and deepfake checks to avoid model downloads
    """
    
    print("=" * 80)
    print("QUICK VIDEO HASH TEST (No OCR/Deepfake)")
    print("=" * 80)
    print()
    
    # Step 1: Test hash computation on original
    print("STEP 1: COMPUTING HASH FOR ORIGINAL VIDEO")
    print("-" * 80)
    
    original_path = "../data/test_video_dataset/originals/Volleyball_original.mp4"
    
    if not os.path.exists(original_path):
        print(f"ERROR: Original video not found at {original_path}")
        print("Please run generate_test_videos.py first!")
        return
    
    hash_vector, frame_hashes = compute_video_phash(original_path, interval_seconds=3)
    
    if hash_vector is None:
        print("ERROR: Failed to compute hash")
        return
    
    print(f"✓ Computed hash from {len(frame_hashes)} keyframes")
    print(f"  Sample frame hash: {frame_hashes[0]}")
    print()
    
    # Step 2: Add to FAISS index
    print("STEP 2: ADDING TO FAISS INDEX")
    print("-" * 80)
    
    faiss_id = add_to_index(hash_vector)
    print(f"✓ Added to index with FAISS ID: {faiss_id}")
    print()
    
    # Step 3: Test against variants
    print("STEP 3: TESTING VARIANTS (HASH DISTANCE ONLY)")
    print("-" * 80)
    
    test_variants = [
        ("type1_trimmed/Volleyball_trimmed.mp4", "Trimmed (should be < 8)"),
        ("type1_compressed/Volleyball_compressed.mp4", "Compressed (should be < 8)"),
        ("type1_cropped/Volleyball_cropped.mp4", "Cropped (should be 8-20)"),
        ("type2_text_overlay/Volleyball_text.mp4", "Text Overlay (should be 8-20)"),
        ("type2_logo_overlay/Volleyball_logo.mp4", "Logo (should be 8-20)"),
        ("type3_color_graded/Volleyball_color.mp4", "Color Graded (should be 10-25)"),
        ("type4_mixed_trim_text/Volleyball_mixed.mp4", "Mixed (should be 8-20)"),
    ]
    
    for variant_path, description in test_variants:
        full_path = f"../data/test_video_dataset/{variant_path}"
        
        if not os.path.exists(full_path):
            print(f"⚠ SKIPPED: {variant_path} (file not found)")
            continue
        
        print(f"\nTesting: {os.path.basename(variant_path)}")
        print(f"Expected: {description}")
        
        # Compute hash
        variant_hash, _ = compute_video_phash(full_path, interval_seconds=3)
        
        if variant_hash is None:
            print(f"✗ Failed to compute hash")
            continue
        
        # Search FAISS
        matches = search_index(variant_hash, top_k=1)
        
        if not matches:
            print(f"✗ No match found")
            continue
        
        distance = matches[0]["distance"]
        
        # Classify based on distance
        if distance < 8:
            classification = "Type 1 (Exact/Near Copy)"
        elif distance < 25:
            classification = "Type 2/3 (Modified - needs OCR/Deepfake check)"
        else:
            classification = "Clear (Too different)"
        
        print(f"✓ Distance: {distance:.2f}")
        print(f"  Classification: {classification}")
    
    print()
    
    # Step 4: Test videos_to_test if available
    print("STEP 4: TESTING VIDEOS_TO_TEST (IF AVAILABLE)")
    print("-" * 80)
    
    videos_to_test_dir = "../data/videos_to_test"
    
    if not os.path.exists(videos_to_test_dir):
        print(f"⚠ videos_to_test folder not found!")
        print("Run generate_videos_to_test.py to create test variants.")
    else:
        test_files = glob.glob(os.path.join(videos_to_test_dir, "*.mp4"))
        
        if not test_files:
            print(f"⚠ No videos found in {videos_to_test_dir}")
        else:
            print(f"Found {len(test_files)} test videos\n")
            
            for test_file in sorted(test_files)[:5]:  # Test first 5 only
                filename = os.path.basename(test_file)
                
                print(f"\nTesting: {filename}")
                
                variant_hash, _ = compute_video_phash(test_file, interval_seconds=3)
                
                if variant_hash is None:
                    print(f"✗ Failed to compute hash")
                    continue
                
                matches = search_index(variant_hash, top_k=1)
                
                if not matches:
                    print(f"✗ No match found")
                    continue
                
                distance = matches[0]["distance"]
                
                if distance < 8:
                    classification = "Type 1 (Exact/Near Copy)"
                elif distance < 25:
                    classification = "Type 2/3 (Modified)"
                else:
                    classification = "Clear (Too different)"
                
                print(f"✓ Distance: {distance:.2f}")
                print(f"  Classification: {classification}")
    
    print()
    print("=" * 80)
    print("QUICK TEST COMPLETE")
    print("=" * 80)
    print("\nNOTE: This test only checks hash distances.")
    print("For full OCR/Deepfake analysis, use the frontend or wait for model downloads.")
    print()

if __name__ == "__main__":
    quick_test_video_pipeline()
