from pathlib import Path

from scripts.create_thumbnail_with_watermaker import add_watermark_to_image

from proyect_x.logging_config import setup_logging
from proyect_x.shared.download_register import RegistryManager
from proyect_x.uploader import send_video
from proyect_x.uploader.settings import get_settings as get_upload_settings
from proyect_x.yt_downloader.config.settings import get_settings as get_yt_settings
from proyect_x.yt_downloader.runner import main_loop

if __name__ == "__main__":
    setup_logging(f"logs/{Path(__file__).stem}.log")

    # --- Configuracion de la serie y calidades ---
    config_yt = get_yt_settings(env_path=Path(".env/.download_video.env"))
    config_upload = get_upload_settings(env_path=Path(".env/.upload_episode.env"))

    watermark_text = "https://t.me/DESAFIO_SIGLO_XXI"
    register = RegistryManager()
    for episode_dled in main_loop(config_yt):
        videos = episode_dled.video_paths
        thumbnail_path = episode_dled.thumbnail_path
        episode_number = episode_dled.episode_number

        print(
            f"Archivos procesados para episodio {episode_number}. Iniciando flujo de publicación..."
        )
        try:
            for video_path in videos:
                register.register_episode_downloaded(episode_number, video_path)

            add_watermark_to_image(
                str(thumbnail_path), watermark_text, "thumbnail_watermarked.jpg"
            )

            # Subida
            video_paths = [str(file) for file in videos]
            send_video.send_videos_as_media_group(
                video_paths, "thumbnail_watermarked.jpg", episode_number, config_upload
            )

            register.register_episode_publication(episode_number)
            print(f"Publicación del episodio {episode_number} completada.")

        except Exception as e:
            print(f"Error registrando la descarga: {e}")
            raise e
