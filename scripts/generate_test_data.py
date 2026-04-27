import os
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import random

SEED_DIR = "../data/seed_images"
OUT_DIR = "../data/test_dataset"

# Create output subdirectories
categories = [
    "originals", 
    "type1_cropped", 
    "type1_compressed", 
    "type2_text_overlay", 
    "type2_watermarked", 
    "type3_ai_simulated",
    "type4_mixed_crop_text",
    "type4_mixed_compress_watermark"
]

for cat in categories:
    os.makedirs(os.path.join(OUT_DIR, cat), exist_ok=True)

def process_images():
    valid_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    images = [f for f in os.listdir(SEED_DIR) if os.path.splitext(f)[1].lower() in valid_extensions]
    
    if not images:
        print(f"No images found in {SEED_DIR}! Please add some starting images there.")
        return

    print(f"Found {len(images)} seed images. Generating variations...")

    for filename in images:
        filepath = os.path.join(SEED_DIR, filename)
        base_name, ext = os.path.splitext(filename)
        
        try:
            with Image.open(filepath) as img:
                img = img.convert("RGB")
                width, height = img.size
                
                # 0. Save Original
                img.save(os.path.join(OUT_DIR, "originals", f"{base_name}_original.jpg"), quality=100)
                
                # 1. Cropped (Type 1) - Crop 15% off the edges
                crop_margin_w = int(width * 0.15)
                crop_margin_h = int(height * 0.15)
                cropped = img.crop((crop_margin_w, crop_margin_h, width - crop_margin_w, height - crop_margin_h))
                cropped.save(os.path.join(OUT_DIR, "type1_cropped", f"{base_name}_cropped.jpg"), quality=95)
                
                # 2. Compressed (Type 1) - Save with terrible JPEG quality
                img.save(os.path.join(OUT_DIR, "type1_compressed", f"{base_name}_compressed.jpg"), quality=15)
                
                # 3. Text Overlay (Type 2)
                txt_img = img.copy()
                draw = ImageDraw.Draw(txt_img)
                # We try to make the text big enough to be seen
                font_size = max(20, int(height * 0.05))
                try:
                    # Might fail if Arial is not found, fallback to default
                    font = ImageFont.truetype("Arial.ttf", font_size)
                except IOError:
                    font = ImageFont.load_default()
                    
                text_content = f"@FakeSportsHub_{random.randint(100, 999)}"
                draw.text((int(width*0.05), int(height*0.85)), text_content, fill="white", font=font, stroke_width=2, stroke_fill="black")
                txt_img.save(os.path.join(OUT_DIR, "type2_text_overlay", f"{base_name}_text.jpg"), quality=95)
                
                # 4. Watermarked (Type 2) - Large semi-transparent text across the middle
                watermark = img.copy()
                overlay = Image.new('RGBA', watermark.size, (255,255,255,0))
                draw_ov = ImageDraw.Draw(overlay)
                try:
                    font_wm = ImageFont.truetype("Arial.ttf", int(height * 0.1))
                except IOError:
                    font_wm = ImageFont.load_default()
                
                draw_ov.text((int(width*0.2), int(height*0.4)), "UNAUTHORIZED BETTING PROMO", fill=(255, 0, 0, 128), font=font_wm)
                watermark.paste(overlay, (0,0), overlay)
                watermark = watermark.convert("RGB")
                watermark.save(os.path.join(OUT_DIR, "type2_watermarked", f"{base_name}_watermark.jpg"), quality=95)
                
                # 5. AI Simulated / Filtered (Type 3) - Heavily process to simulate 'regeneration'
                ai_sim = img.copy()
                ai_sim = ImageEnhance.Color(ai_sim).enhance(2.5) 
                ai_sim = ai_sim.filter(ImageFilter.EDGE_ENHANCE_MORE)
                ai_sim = ImageEnhance.Contrast(ai_sim).enhance(1.3)
                ai_sim.save(os.path.join(OUT_DIR, "type3_ai_simulated", f"{base_name}_ai_sim.jpg"), quality=90)
                
                # 6. Mixed 1 (Type 4) - Cropped AND Text Overlay
                mixed_crop = cropped.copy()
                draw_mixed = ImageDraw.Draw(mixed_crop)
                mc_width, mc_height = mixed_crop.size
                font_size_mc = max(20, int(mc_height * 0.05))
                try:
                    font_mc = ImageFont.truetype("Arial.ttf", font_size_mc)
                except IOError:
                    font_mc = ImageFont.load_default()
                draw_mixed.text((int(mc_width*0.05), int(mc_height*0.85)), text_content, fill="yellow", font=font_mc, stroke_width=2, stroke_fill="black")
                mixed_crop.save(os.path.join(OUT_DIR, "type4_mixed_crop_text", f"{base_name}_mixed1.jpg"), quality=95)
                
                # 7. Mixed 2 (Type 4) - Watermarked AND Terrible Compression
                mixed_wm = watermark.copy() # Already has watermark
                mixed_wm.save(os.path.join(OUT_DIR, "type4_mixed_compress_watermark", f"{base_name}_mixed2.jpg"), quality=10) # 10 is very bad quality
                
        except Exception as e:
            print(f"Failed processing {filename}: {e}")

    print("Done! Check the data/test_dataset directory for your generated test files.")

if __name__ == "__main__":
    process_images()
