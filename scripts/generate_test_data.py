import json
import os
import random
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageOps

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

SEED_DIR = os.path.join(PROJECT_ROOT, "data", "seed_images")
OUT_DIR = os.path.join(PROJECT_ROOT, "data", "test_dataset")
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.json")

CATEGORIES = [
    "originals",
    "type1_cropped",
    "type1_compressed",
    "type2_text_overlay",
    "type2_watermarked",
    "type3_ai_simulated",
    "type4_mixed_crop_text",
    "type4_mixed_compress_watermark",
]


def ensure_output_dirs():
    os.makedirs(OUT_DIR, exist_ok=True)
    for category in CATEGORIES:
        category_dir = os.path.join(OUT_DIR, category)
        os.makedirs(category_dir, exist_ok=True)
        for entry in os.listdir(category_dir):
            entry_path = os.path.join(category_dir, entry)
            if os.path.isfile(entry_path):
                os.remove(entry_path)


def load_font(size):
    font_candidates = [
        "Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for font_path in font_candidates:
        try:
            return ImageFont.truetype(font_path, size)
        except IOError:
            continue
    return ImageFont.load_default()


def save_jpeg(image, path, quality):
    image.save(path, quality=quality, optimize=True)


def apply_random_crop(image, rng):
    width, height = image.size
    crop_ratio = rng.uniform(0.03, 0.09)
    crop_margin_w = max(1, int(width * crop_ratio))
    crop_margin_h = max(1, int(height * crop_ratio))
    return image.crop((crop_margin_w, crop_margin_h, width - crop_margin_w, height - crop_margin_h))


def add_text_overlay(image, rng, accent_color):
    width, height = image.size
    text_image = image.convert("RGBA")
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    font_size = max(20, int(height * rng.uniform(0.045, 0.075)))
    font = load_font(font_size)
    text_content = f"@FakeSportsHub_{rng.randint(100, 999)}"
    x_pos = int(width * rng.uniform(0.04, 0.12))
    y_pos = int(height * rng.uniform(0.80, 0.90))
    banner_height = max(font_size + 16, int(height * 0.12))
    banner_top = max(0, y_pos - 10)
    banner_bottom = min(height, banner_top + banner_height)
    draw.rectangle((0, banner_top, width, banner_bottom), fill=(12, 12, 12, 88))
    draw.text((x_pos, y_pos), text_content, fill=accent_color, font=font, stroke_width=2, stroke_fill="black")
    return Image.alpha_composite(text_image, overlay).convert("RGB")


def add_watermark(image, rng):
    width, height = image.size
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    watermark_text = rng.choice([
        "UNAUTHORIZED BETTING PROMO",
        "SAMPLE REPOST",
        "PROMOTIONAL CONTENT",
    ])
    font = load_font(max(24, int(height * rng.uniform(0.08, 0.12))))
    opacity = rng.randint(110, 165)
    angle = rng.choice([0, 15, 20])

    for row in range(-1, 3):
        for col in range(-1, 3):
            x_pos = int(width * (0.1 + 0.28 * col))
            y_pos = int(height * (0.18 + 0.24 * row))
            layer = Image.new("RGBA", image.size, (255, 255, 255, 0))
            layer_draw = ImageDraw.Draw(layer)
            layer_draw.text((x_pos, y_pos), watermark_text, fill=(255, 0, 0, opacity), font=font)
            rotated = layer.rotate(angle, resample=Image.Resampling.BICUBIC)
            overlay = Image.alpha_composite(overlay, rotated)

    watermarked = image.convert("RGBA")
    watermarked = Image.alpha_composite(watermarked, overlay)
    return watermarked.convert("RGB")


def simulate_ai_image(image, rng):
    transformed = image.copy()
    ops = [
        lambda im: ImageEnhance.Color(im).enhance(rng.uniform(1.7, 3.0)),
        lambda im: ImageEnhance.Contrast(im).enhance(rng.uniform(1.2, 1.8)),
        lambda im: ImageEnhance.Sharpness(im).enhance(rng.uniform(1.4, 2.5)),
        lambda im: ImageOps.autocontrast(im),
        lambda im: ImageOps.posterize(im, rng.choice([3, 4])),
        lambda im: ImageOps.solarize(im, threshold=rng.randint(72, 140)),
        lambda im: im.filter(ImageFilter.EDGE_ENHANCE_MORE),
        lambda im: im.filter(ImageFilter.DETAIL),
        lambda im: im.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.6, 1.4))),
    ]

    transformed = ops[0](transformed)
    transformed = ops[1](transformed)
    transformed = ops[2](transformed)

    remaining_ops = ops[3:]
    rng.shuffle(remaining_ops)
    for op in remaining_ops[: rng.randint(2, 3)]:
        transformed = op(transformed)

    return transformed


def process_images():
    ensure_output_dirs()

    valid_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    images = [f for f in os.listdir(SEED_DIR) if os.path.splitext(f)[1].lower() in valid_extensions]

    if not images:
        print(f"No images found in {SEED_DIR}! Please add some starting images there.")
        return

    print(f"Found {len(images)} seed images. Generating varied test cases...")
    manifest = {"seeds": [], "files": []}

    for filename in sorted(images):
        filepath = os.path.join(SEED_DIR, filename)
        base_name, _ = os.path.splitext(filename)
        rng = random.Random(f"{base_name}:test-generation")

        try:
            with Image.open(filepath) as img:
                img = img.convert("RGB")
                width, height = img.size

                original_name = f"{base_name}_original.jpg"
                save_jpeg(img, os.path.join(OUT_DIR, "originals", original_name), quality=100)
                manifest["seeds"].append({"source": filename, "size": [width, height]})
                manifest["files"].append({"folder": "originals", "file": original_name, "source": filename, "variant": "original"})

                cropped = apply_random_crop(img, rng)
                crop_name = f"{base_name}_cropped.jpg"
                save_jpeg(cropped, os.path.join(OUT_DIR, "type1_cropped", crop_name), quality=rng.choice([88, 92, 96]))
                manifest["files"].append({"folder": "type1_cropped", "file": crop_name, "source": filename, "variant": "crop"})

                compressed_name = f"{base_name}_compressed.jpg"
                compressed = img.resize((max(64, int(width * rng.uniform(0.82, 0.95))), max(64, int(height * rng.uniform(0.82, 0.95)))), Image.Resampling.LANCZOS)
                compressed = compressed.resize((width, height), Image.Resampling.LANCZOS)
                save_jpeg(compressed, os.path.join(OUT_DIR, "type1_compressed", compressed_name), quality=rng.choice([12, 18, 24, 30]))
                manifest["files"].append({"folder": "type1_compressed", "file": compressed_name, "source": filename, "variant": "compression"})

                text_name = f"{base_name}_text.jpg"
                text_overlay = add_text_overlay(img, rng, accent_color=rng.choice(["white", "yellow", "#ffdd55"]))
                save_jpeg(text_overlay, os.path.join(OUT_DIR, "type2_text_overlay", text_name), quality=rng.choice([90, 94, 97]))
                manifest["files"].append({"folder": "type2_text_overlay", "file": text_name, "source": filename, "variant": "text"})

                watermark_name = f"{base_name}_watermark.jpg"
                watermarked = add_watermark(img, rng)
                save_jpeg(watermarked, os.path.join(OUT_DIR, "type2_watermarked", watermark_name), quality=rng.choice([90, 94, 97]))
                manifest["files"].append({"folder": "type2_watermarked", "file": watermark_name, "source": filename, "variant": "watermark"})

                ai_name = f"{base_name}_ai_sim.jpg"
                ai_sim = simulate_ai_image(img, rng)
                if rng.random() < 0.4:
                    ai_sim = ImageEnhance.Color(ai_sim).enhance(rng.uniform(0.75, 1.25))
                save_jpeg(ai_sim, os.path.join(OUT_DIR, "type3_ai_simulated", ai_name), quality=rng.choice([84, 88, 92]))
                manifest["files"].append({"folder": "type3_ai_simulated", "file": ai_name, "source": filename, "variant": "ai"})

                mixed_crop_name = f"{base_name}_mixed1.jpg"
                mixed_crop = add_text_overlay(cropped, rng, accent_color=rng.choice(["yellow", "white"]))
                save_jpeg(mixed_crop, os.path.join(OUT_DIR, "type4_mixed_crop_text", mixed_crop_name), quality=rng.choice([88, 92, 96]))
                manifest["files"].append({"folder": "type4_mixed_crop_text", "file": mixed_crop_name, "source": filename, "variant": "crop+text"})

                mixed_wm_name = f"{base_name}_mixed2.jpg"
                mixed_wm = add_watermark(img, rng)
                save_jpeg(mixed_wm, os.path.join(OUT_DIR, "type4_mixed_compress_watermark", mixed_wm_name), quality=rng.choice([8, 10, 12]))
                manifest["files"].append({"folder": "type4_mixed_compress_watermark", "file": mixed_wm_name, "source": filename, "variant": "watermark+compression"})

        except Exception as e:
            print(f"Failed processing {filename}: {e}")

    with open(MANIFEST_PATH, "w", encoding="utf-8") as manifest_file:
        json.dump(manifest, manifest_file, indent=2)

    print("Done! Check the data/test_dataset directory for your generated test files.")

if __name__ == "__main__":
    process_images()
