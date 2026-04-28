import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import random

SEED_DIR = "../data/seed_videos"
OUT_DIR = "../data/test_video_dataset"

# Create output subdirectories for different video manipulation types
categories = [
    "originals",
    "type1_trimmed",           # First/last 10% removed
    "type1_compressed",        # Low quality re-encode
    "type1_cropped",           # 15% crop on all sides
    "type2_text_overlay",      # Watermark/handle added
    "type2_logo_overlay",      # Fake logo in corner
    "type3_color_graded",      # Heavy color manipulation (simulates AI filter)
    "type4_mixed_trim_text",   # Trimmed + text overlay
]

for cat in categories:
    os.makedirs(os.path.join(OUT_DIR, cat), exist_ok=True)

def add_text_to_frame(frame, text, position="bottom_left"):
    """
    Adds text overlay to a video frame
    Used for simulating unauthorized watermarks and social media handles
    """
    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    
    height, width = frame.shape[:2]
    font_size = max(20, int(height * 0.04))
    
    try:
        font = ImageFont.truetype("Arial.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()
    
    if position == "bottom_left":
        text_position = (int(width * 0.05), int(height * 0.85))
    elif position == "top_right":
        text_position = (int(width * 0.65), int(height * 0.05))
    else:
        text_position = (int(width * 0.05), int(height * 0.05))
    
    draw.text(text_position, text, fill="white", font=font, stroke_width=2, stroke_fill="black")
    
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

def add_logo_overlay(frame):
    """
    Adds a semi-transparent colored rectangle in corner to simulate fake logo/branding
    Used for Type 2 violations (unauthorized branding)
    """
    height, width = frame.shape[:2]
    overlay = frame.copy()
    
    logo_width = int(width * 0.15)
    logo_height = int(height * 0.08)
    
    cv2.rectangle(overlay, 
                  (width - logo_width - 20, 20), 
                  (width - 20, 20 + logo_height), 
                  (0, 0, 255), 
                  -1)
    
    cv2.putText(overlay, "FAKE", 
                (width - logo_width, 20 + logo_height - 10), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    alpha = 0.6
    return cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

def apply_color_grade(frame):
    """
    Applies heavy color grading to simulate AI-generated or heavily filtered content
    Used for Type 3 violations (AI manipulation detection)
    """
    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    
    pil_img = ImageEnhance.Color(pil_img).enhance(2.0)
    pil_img = ImageEnhance.Contrast(pil_img).enhance(1.4)
    pil_img = pil_img.filter(ImageFilter.EDGE_ENHANCE_MORE)
    
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

def process_videos():
    """
    Main function to generate test video variants from seed videos
    Creates multiple manipulation types to test the detection pipeline
    """
    valid_extensions = {".mp4", ".avi", ".mov", ".mkv"}
    videos = [f for f in os.listdir(SEED_DIR) if os.path.splitext(f)[1].lower() in valid_extensions]
    
    if not videos:
        print(f"No videos found in {SEED_DIR}! Please add seed videos there.")
        return
    
    print(f"Found {len(videos)} seed videos. Generating variations...")
    
    for filename in videos:
        filepath = os.path.join(SEED_DIR, filename)
        base_name, ext = os.path.splitext(filename)
        
        try:
            cap = cv2.VideoCapture(filepath)
            
            if not cap.isOpened():
                print(f"Failed to open {filename}")
                continue
            
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            
            print(f"Processing {filename} ({total_frames} frames, {fps} fps, {width}x{height})")
            
            # Read all frames into memory for processing
            frames = []
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(frame)
            cap.release()
            
            if len(frames) == 0:
                print(f"No frames read from {filename}")
                continue
            
            # 0. Save Original
            try:
                original_path = os.path.join(OUT_DIR, "originals", f"{base_name}_original.mp4")
                out = cv2.VideoWriter(original_path, fourcc, fps, (width, height))
                for frame in frames:
                    out.write(frame)
                out.release()
                print(f"  ✓ Original saved")
            except Exception as e:
                print(f"  ✗ Original failed: {e}")
            
            # 1. Trimmed (Type 1) - Remove first and last 10% of frames
            try:
                trim_start = int(len(frames) * 0.1)
                trim_end = int(len(frames) * 0.9)
                trimmed_frames = frames[trim_start:trim_end]
                
                trimmed_path = os.path.join(OUT_DIR, "type1_trimmed", f"{base_name}_trimmed.mp4")
                out = cv2.VideoWriter(trimmed_path, fourcc, fps, (width, height))
                for frame in trimmed_frames:
                    out.write(frame)
                out.release()
                print(f"  ✓ Trimmed version saved")
            except Exception as e:
                print(f"  ✗ Trimmed failed: {e}")
            
            # 2. Compressed (Type 1) - Re-encode with very low quality
            try:
                compressed_path = os.path.join(OUT_DIR, "type1_compressed", f"{base_name}_compressed.mp4")
                out = cv2.VideoWriter(compressed_path, fourcc, fps, (width, height))
                for frame in frames:
                    # Simulate compression by adding noise and reducing quality
                    noisy = cv2.add(frame, np.random.randint(0, 20, frame.shape, dtype=np.uint8))
                    out.write(noisy)
                out.release()
                print(f"  ✓ Compressed version saved")
            except Exception as e:
                print(f"  ✗ Compressed failed: {e}")
            
            # 3. Cropped (Type 1) - Crop 15% from all edges
            try:
                crop_margin_w = int(width * 0.15)
                crop_margin_h = int(height * 0.15)
                new_width = width - 2 * crop_margin_w
                new_height = height - 2 * crop_margin_h
                
                cropped_path = os.path.join(OUT_DIR, "type1_cropped", f"{base_name}_cropped.mp4")
                out = cv2.VideoWriter(cropped_path, fourcc, fps, (new_width, new_height))
                for frame in frames:
                    cropped = frame[crop_margin_h:height-crop_margin_h, crop_margin_w:width-crop_margin_w]
                    out.write(cropped)
                out.release()
                print(f"  ✓ Cropped version saved")
            except Exception as e:
                print(f"  ✗ Cropped failed: {e}")
            
            # 4. Text Overlay (Type 2) - Add watermark text to every frame
            try:
                text_content = f"@FakeSportsHub_{random.randint(100, 999)}"
                text_path = os.path.join(OUT_DIR, "type2_text_overlay", f"{base_name}_text.mp4")
                out = cv2.VideoWriter(text_path, fourcc, fps, (width, height))
                for frame in frames:
                    frame_with_text = add_text_to_frame(frame, text_content, "bottom_left")
                    out.write(frame_with_text)
                out.release()
                print(f"  ✓ Text overlay version saved")
            except Exception as e:
                print(f"  ✗ Text overlay failed: {e}")
            
            # 5. Logo Overlay (Type 2) - Add fake logo/branding
            try:
                logo_path = os.path.join(OUT_DIR, "type2_logo_overlay", f"{base_name}_logo.mp4")
                out = cv2.VideoWriter(logo_path, fourcc, fps, (width, height))
                for frame in frames:
                    frame_with_logo = add_logo_overlay(frame)
                    out.write(frame_with_logo)
                out.release()
                print(f"  ✓ Logo overlay version saved")
            except Exception as e:
                print(f"  ✗ Logo overlay failed: {e}")
            
            # 6. Color Graded (Type 3) - Heavy color manipulation simulating AI filter
            try:
                color_path = os.path.join(OUT_DIR, "type3_color_graded", f"{base_name}_color.mp4")
                out = cv2.VideoWriter(color_path, fourcc, fps, (width, height))
                for frame in frames:
                    graded = apply_color_grade(frame)
                    out.write(graded)
                out.release()
                print(f"  ✓ Color graded version saved")
            except Exception as e:
                print(f"  ✗ Color graded failed: {e}")
            
            # 7. Mixed (Type 4) - Trimmed + Text Overlay
            try:
                mixed_path = os.path.join(OUT_DIR, "type4_mixed_trim_text", f"{base_name}_mixed.mp4")
                out = cv2.VideoWriter(mixed_path, fourcc, fps, (width, height))
                for frame in trimmed_frames:
                    frame_with_text = add_text_to_frame(frame, text_content, "top_right")
                    out.write(frame_with_text)
                out.release()
                print(f"  ✓ Mixed version saved")
            except Exception as e:
                print(f"  ✗ Mixed failed: {e}")
            
            print(f"Completed processing {filename}\n")
            
        except Exception as e:
            print(f"Failed processing {filename}: {e}")
    
    print("Done! Check data/test_video_dataset/ for generated test videos.")

if __name__ == "__main__":
    process_videos()
