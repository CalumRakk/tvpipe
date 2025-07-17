from datetime import datetime, time, timedelta
from pathlib import Path

from create_thumbnail_with_watermaker import add_watermark_to_image
from logging_config import setup_logging
from send_video import main as send_video_to_telegram
from yt_dlp_ffmpeg import RELEASE_MODE, main_loop

if __name__ == "__main__":
    setup_logging(f"logs/{Path(__file__).stem}.log")

    # --- Configuracion de la serie y calidades ---
    serie_name = "desafio siglo xxi 2025"
    qualities = [720, 360]
    output_folder = Path("output")
    mode = RELEASE_MODE.AUTO

    # --- Configuracion de Telegram ---
    chat_id = "me"
    forward_chat_ids = [-1001446012480]
    thumbnail_output = "thumbnail_watermarked.jpg"
    watermark_text = "Visita https://t.me/eldesafio2"
    for episode_dled in main_loop(serie_name, qualities, output_folder, mode):
        videos = episode_dled["videos"]
        thumbnail_path = episode_dled["thumbnail"]
        episode_number = episode_dled["episode_number"]
        print(f"Descargado episodio {episode_number} de {serie_name}")

        caption = f"Capítulo {episode_number} - Desafío Siglo XXI\n\n"
        video_paths = [str(file) for file in videos]
        add_watermark_to_image(str(thumbnail_path), watermark_text, thumbnail_output)
        send_video_to_telegram(
            video_paths=video_paths,
            caption=caption,
            chat_id=chat_id,
            thumbnail_path=thumbnail_output,
            forward=forward_chat_ids,
        )
        print(f"Archivos finales: {episode_dled}")
