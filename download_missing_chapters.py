import logging
from pathlib import Path

from logging_config import setup_logging
from orchestrator import add_watermark_to_image, send_video_to_telegram
from series_manager.yt_dlp_tools import is_episode_downloaded
from yt_dlp_ffmpeg import (
    download_thumbnail,
    get_download_jobs,
    get_episode_number,
    get_metadata,
    merge_files,
    parallel_download,
    prepare_folders,
    register_download,
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    setup_logging(f"logs/{Path(__file__).stem}.log")
    serie_name = "desafio siglo xxi 2025"
    qualities = [720, 360]
    output_folder = Path("output")

    chat_id = "me"
    thumbnail_output = "thumbnail_watermarked.jpg"
    watermark_text = "Visita https://t.me/eldesafio2"

    URLs = [
        "https://www.youtube.com/watch?v=kz_FqZxo5gM",
        "https://www.youtube.com/watch?v=Ho4LmkE2fBA",
        "https://www.youtube.com/watch?v=Z-rketUJeRg&",
        "https://www.youtube.com/watch?v=IeHwWQlma3c",
        "https://www.youtube.com/watch?v=IeHwWQlma3c",
        "https://www.youtube.com/watch?v=O5k23V64diw",
        "https://www.youtube.com/watch?v=HHwdtMdZqNQB",
        "https://www.youtube.com/watch?v=oIstUSFJrV8",
        "https://www.youtube.com/watch?v=m84l-rUzWVI",
    ]

    for url in URLs:

        # --- DESCARGA DEL CAPÍTULO ---
        video_title = get_metadata(url)["title"]
        number = get_episode_number(video_title)
        if is_episode_downloaded(number):
            logger.info(f"✅ El capítulo {number} ya fue descargado.")
            continue

        logger.info(f"Iniciando descarga: {url}")

        temp_folder = prepare_folders(output_folder)

        download_jobs = get_download_jobs(url, qualities)
        downloaded_files = parallel_download(download_jobs, temp_folder)

        serie_name_final = serie_name.replace(" ", ".").lower()

        videos = merge_files(
            downloaded_files,
            output_folder,
            serie_name_final,
            number,
        )
        thumbnail_path = download_thumbnail(url, output_folder, serie_name_final)
        episode_dled = {
            "videos": videos,
            "thumbnail": thumbnail_path,
            "episode_number": number,
        }
        logger.info("✅ Descarga del capítulo  completada.")

        # --- SUBIDA DEL CAPÍTULO ---

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
        )
        print(f"Archivos finales: {episode_dled}")

        register_download(number)
