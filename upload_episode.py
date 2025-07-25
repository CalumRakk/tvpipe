from pathlib import Path

from proyect_x.logging_config import setup_logging
from proyect_x.uploader.send_video import send_videos_as_media_group
from proyect_x.uploader.settings import get_settings

if __name__ == "__main__":
    setup_logging(f"logs/{Path(__file__).stem}.log")
    config = get_settings(env_path=Path(".env/.upload_episode.test.env"))
    thumbnail_path = r"output\test\desafío.2025.capitulo.17.yt.thumbnail.jpg"
    video_paths = [
        r"output\test\desafío.2025.capitulo.17.yt.144p.mp4",
        r"output\test\desafío.2025.capitulo.17.yt.240p.mp4",
    ]
    send_videos_as_media_group(video_paths, thumbnail_path, "16", config)
