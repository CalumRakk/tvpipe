import os
import subprocess
from pathlib import Path

OUTPUT_VIDEO_DIR = Path("output_dash/video")
OUTPUT_AUDIO_DIR = "output_dash/audio"
FINAL_OUTPUT = "output_final.mp4"


video_segments = OUTPUT_VIDEO_DIR / "video_segments.txt"
with open(video_segments, "wt") as f:
    for index, segment in enumerate(OUTPUT_VIDEO_DIR.glob("*.mp4")):
        if segment.name == "init.mp4":
            continue
        f.write(f"file '{segment.name}'\n")

command_audio = "copy /b init.mp4+* output_audio.mp4"
command_video = "copy /b init.mp4+* output_video.mp4"


subprocess.run(command_audio, shell=True, cwd=OUTPUT_AUDIO_DIR)
subprocess.run(command_video, shell=True, cwd=OUTPUT_VIDEO_DIR)

subprocess.run(
    [
        "ffmpeg",
        "-loglevel",
        "error",
        "-i",
        os.path.join(OUTPUT_VIDEO_DIR, "output_video.mp4"),
        "-i",
        os.path.join(OUTPUT_AUDIO_DIR, "output_audio.mp4"),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-strict",
        "experimental",
        "-shortest",
        FINAL_OUTPUT,
        "-y",
    ],
    check=True,
)
