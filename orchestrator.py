from pathlib import Path

from proyect_x.logging_config import setup_logging
from proyect_x.uploader.send_video import send_videos_as_media_group
from proyect_x.uploader.settings import get_settings as get_upload_settings
from proyect_x.yt_downloader.config.settings import get_settings as get_yt_settings
from proyect_x.yt_downloader.runner import main_loop
from scripts.create_thumbnail_with_watermaker import add_watermark_to_image

if __name__ == "__main__":
    setup_logging(f"logs/{Path(__file__).stem}.log")

    # --- Configuracion de la serie y calidades ---
    config_yt = get_yt_settings(env_path=Path(".env/.download_video.env"))
    config_upload = get_upload_settings(env_path=Path(".env/.upload_episode.env"))

    watermark_text = "Visita https://t.me/eldesafio3"
    for episode_dled in main_loop(config_yt):
        videos = episode_dled["videos"]
        thumbnail_path = episode_dled["thumbnail"]
        episode_number = episode_dled["episode_number"]

        print(f"Descargado episodio {episode_number} de {config_yt.serie_name}")

        caption = f"Capítulo {episode_number} - Desafío Siglo XXI\n\n"
        video_paths = [str(file) for file in videos]
        add_watermark_to_image(
            str(thumbnail_path), watermark_text, "thumbnail_watermarked.jpg"
        )  # type: ignore

        send_videos_as_media_group(
            video_paths, "thumbnail_watermarked.jpg", episode_number, config_upload
        )
        print(f"Archivos finales: {episode_dled}")
