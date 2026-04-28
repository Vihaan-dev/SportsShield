import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import random

SEED_DIR = "../data/seed_videos"
OUT_DIR = "../data/videos_to_test"

# Create output directory for real testing variants
# These are DIFFERENT from test_dataset to validate the detection actually works
os.makedirs(OUT_DIR, exist_ok=True)

def add_different_text(frame, text, position="center"):
    """
    Adds text with different styling than test dataset
    Uses different positions, colors, and fonts to simulate real-world variations
    """
    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    
    height, width = frame.shape[:2]
    font_size = max(25, int(height * 0.06))
    
    try:
        font = ImageFont.truetype("Arial.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()
    
    # Different positions than test dataset
    if position == "center":
        text_position = (int(width * 0.3), int(height * 0.5))
    elif position == "top_left":
        text_position = (int(width * 0.1), int(height * 0.1))
    elif position == "bottom_right":
        text_position = (int(width * 0.6), int(height * 0.9))
    else:
        text_position = (int(width * 0.4), int(height * 0.7))
    
    # Different colors: yellow, cyan, green instead of white
    colors = ["yellow", "cyan", "lime", "magenta"]
    draw.text(text_position, text, fill=random.choice(colors), font=font, stroke_width=3, stroke_fill="black")
    
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

def add_different_watermark(frame):
    """
    Adds diagonal watermark across the frame
    Different from test dataset which uses corner rectangle
    """
    height, width = frame.shape[:2]
    overlay = frame.copy()
    
    # Draw diagonal line with text
    cv2.line(overlay, (0, 0), (width, height), (255, 255, 0), 5)
    
    # Add text along diagonal
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(overlay, "STOLEN CONTENT", 
                (int(width * 0.3), int(height * 0.5)), 
                font, 2, (0, 255, 255), 4)
    
    alpha = 0.5
    return cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

def apply_different_filter(frame):
    """
    Applies different color manipulation than test dataset
    Uses saturation reduction and blur instead of enhancement
    """
    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    
    # Desaturate instead of saturate
    pil_img = ImageEnhance.Color(pil_img).enhance(0.5)
    # Reduce brightness
    pil_img = ImageEnhance.Brightness(pil_img).enhance(0.8)
    # Add blur
    pil_img = pil_img.filter(ImageFilter.GaussianBlur(radius=2))
    
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

def apply_rotation_crop(frame, angle=5):
    """
    Rotates frame slightly and crops to remove black borders
    This is NOT in test dataset
    """
    height, width = frame.shape[:2]
    center = (width // 2, height // 2)
    
    # Rotate
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(frame, matrix, (width, height))
    
    # Crop to remove black borders
    crop_margin = int(min(width, height) * 0.1)
    cropped = rotated[crop_margin:height-crop_margin, crop_margin:width-crop_margin]
    
    return cropped

def apply_speed_change(frames, speed_factor=1.5):
    """
    Changes video speed by skipping frames
    Makes video faster (simulates someone speeding up stolen content)
    """
    step = int(speed_factor)
    return frames[::step]

def apply_mirror_flip(frame):
    """
    Horizontally flips the frame
    Common technique to avoid detection
    """
    return cv2.flip(frame, 1)

def process_videos_for_testing():
    """
    Generates completely different variants for real-world testing
    These should still be detected but use different manipulations than test_dataset
    """
    valid_extensions = {".mp4", ".avi", ".mov", ".mkv"}
    videos = [f for f in os.listdir(SEED_DIR) if os.path.splitext(f)[1].lower() in valid_extensions]
    
    if not videos:
        print(f"No videos found in {SEED_DIR}! Please add seed videos there.")
        return
    
    print(f"Found {len(videos)} seed videos. Generating DIFFERENT test variants...")
    print("These variants use different manipulations than test_dataset to validate detection.\n")
    
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
            
            # Read all frames
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
            
            # Variant 1: Different text overlay (center position, different color)
            try:
                text_content = f"REPOSTED BY @SportsThief{random.randint(1000, 9999)}"
                text_path = os.path.join(OUT_DIR, f"{base_name}_different_text.mp4")
                out = cv2.VideoWriter(text_path, fourcc, fps, (width, height))
                for frame in frames:
                    frame_with_text = add_different_text(frame, text_content, "center")
                    out.write(frame_with_text)
                out.release()
                print(f"  ✓ Different text overlay saved")
            except Exception as e:
                print(f"  ✗ Different text failed: {e}")
            
            # Variant 2: Diagonal watermark (completely different style)
            try:
                watermark_path = os.path.join(OUT_DIR, f"{base_name}_diagonal_watermark.mp4")
                out = cv2.VideoWriter(watermark_path, fourcc, fps, (width, height))
                for frame in frames:
                    frame_with_wm = add_different_watermark(frame)
                    out.write(frame_with_wm)
                out.release()
                print(f"  ✓ Diagonal watermark saved")
            except Exception as e:
                print(f"  ✗ Diagonal watermark failed: {e}")
            
            # Variant 3: Different color filter (desaturate + blur instead of enhance)
            try:
                filter_path = os.path.join(OUT_DIR, f"{base_name}_desaturated.mp4")
                out = cv2.VideoWriter(filter_path, fourcc, fps, (width, height))
                for frame in frames:
                    filtered = apply_different_filter(frame)
                    out.write(filtered)
                out.release()
                print(f"  ✓ Desaturated filter saved")
            except Exception as e:
                print(f"  ✗ Desaturated filter failed: {e}")
            
            # Variant 4: Rotated and cropped (NOT in test dataset)
            try:
                rotated_path = os.path.join(OUT_DIR, f"{base_name}_rotated_crop.mp4")
                # Get dimensions after rotation
                sample_rotated = apply_rotation_crop(frames[0], angle=5)
                rot_height, rot_width = sample_rotated.shape[:2]
                
                out = cv2.VideoWriter(rotated_path, fourcc, fps, (rot_width, rot_height))
                for frame in frames:
                    rotated = apply_rotation_crop(frame, angle=5)
                    out.write(rotated)
                out.release()
                print(f"  ✓ Rotated + cropped saved")
            except Exception as e:
                print(f"  ✗ Rotated + cropped failed: {e}")
            
            # Variant 5: Speed changed (1.5x faster by skipping frames)
            try:
                speed_frames = apply_speed_change(frames, speed_factor=1.5)
                speed_path = os.path.join(OUT_DIR, f"{base_name}_sped_up.mp4")
                out = cv2.VideoWriter(speed_path, fourcc, fps, (width, height))
                for frame in speed_frames:
                    out.write(frame)
                out.release()
                print(f"  ✓ Sped up version saved")
            except Exception as e:
                print(f"  ✗ Sped up failed: {e}")
            
            # Variant 6: Horizontally flipped (mirror)
            try:
                flip_path = os.path.join(OUT_DIR, f"{base_name}_mirrored.mp4")
                out = cv2.VideoWriter(flip_path, fourcc, fps, (width, height))
                for frame in frames:
                    flipped = apply_mirror_flip(frame)
                    out.write(flipped)
                out.release()
                print(f"  ✓ Mirrored version saved")
            except Exception as e:
                print(f"  ✗ Mirrored failed: {e}")
            
            # Variant 7: Heavy crop (30% from all sides instead of 15%)
            try:
                crop_margin_w = int(width * 0.30)
                crop_margin_h = int(height * 0.30)
                new_width = width - 2 * crop_margin_w
                new_height = height - 2 * crop_margin_h
                
                heavy_crop_path = os.path.join(OUT_DIR, f"{base_name}_heavy_crop.mp4")
                out = cv2.VideoWriter(heavy_crop_path, fourcc, fps, (new_width, new_height))
                for frame in frames:
                    cropped = frame[crop_margin_h:height-crop_margin_h, crop_margin_w:width-crop_margin_w]
                    out.write(cropped)
                out.release()
                print(f"  ✓ Heavy crop saved")
            except Exception as e:
                print(f"  ✗ Heavy crop failed: {e}")
            
            # Variant 8: Combo - Mirrored + Text + Desaturated
            try:
                combo_path = os.path.join(OUT_DIR, f"{base_name}_combo_attack.mp4")
                out = cv2.VideoWriter(combo_path, fourcc, fps, (width, height))
                combo_text = "STOLEN & REPOSTED"
                for frame in frames:
                    # Apply multiple transformations
                    processed = apply_mirror_flip(frame)
                    processed = apply_different_filter(processed)
                    processed = add_different_text(processed, combo_text, "bottom_right")
                    out.write(processed)
                out.release()
                print(f"  ✓ Combo attack saved")
            except Exception as e:
                print(f"  ✗ Combo attack failed: {e}")
            
            print(f"Completed processing {filename}\n")
            
        except Exception as e:
            print(f"Failed processing {filename}: {e}")
    
    print("=" * 60)
    print("Done! Check data/videos_to_test/ for your testing variants.")
    print("\nThese variants are DIFFERENT from test_dataset:")
    print("- Different text positions and colors")
    print("- Diagonal watermarks instead of corner logos")
    print("- Desaturation instead of color enhancement")
    print("- Rotation, mirroring, speed changes")
    print("- Heavier crops (30% vs 15%)")
    print("\nUse these to validate your detection pipeline actually works!")
    print("=" * 60)

if __name__ == "__main__":
    process_videos_for_testing()
