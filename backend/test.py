from video_api import analyze_suspect_video

# Test with text overlay variant
result = analyze_suspect_video(
    "../data/test_video_dataset/type2_text_overlay/Volleyball_text.mp4",
    "Volleyball_text.mp4"
)
print(result)
