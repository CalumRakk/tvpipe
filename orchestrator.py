from datetime import datetime, time
from pathlib import Path

from create_thumbnail_with_watermaker import main as create_thumbnail_main
from logging_config import setup_logging
from send_video import main as send_video_to_telegram
from yt_dlp_ffmpeg import main_loop

if __name__ == "__main__":
    setup_logging("logs/descarga_capitulo_del_dia.log")

    # --- Configuracion de la serie y calidades ---
    serie_name = "desafio siglo xxi 2025"
    qualities = [240, 144]
    output_folder = Path("output")
    nine_pm_today = datetime.combine(datetime.now().date(), time(21, 30))

    # --- Configuracion de Telegram ---
    caption = "Capítulo 9 - Desafío Siglo XXI\n\n"
    chat_id = "me"
    thumbnail_path = "thumbnail_watermarked.jpg"
    watermark_text = "Visita https://t.me/eldesafio2"
    for final_files in main_loop(serie_name, qualities, output_folder, nine_pm_today):
        video_paths = [str(file) for file in final_files]
        create_thumbnail_main(
            video_path=video_paths[-1],
            output_image=thumbnail_path,
            watermark_text=watermark_text,
        )
        send_video_to_telegram(
            video_paths=video_paths,
            caption=caption,
            chat_id=chat_id,
            thumbnail_path=thumbnail_path,
        )
        print(f"Archivos finales: {final_files}")
        break
