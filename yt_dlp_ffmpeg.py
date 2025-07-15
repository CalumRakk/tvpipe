import concurrent.futures
from datetime import datetime, time, timedelta
from pathlib import Path

import requests

from logging_config import setup_logging
from utils.yt_dlp_tools import (
    already_downloaded_today,
    download_media_item,
    get_download_jobs,
    get_episode_number,
    get_episode_of_the_day,
    get_metadata,
    merge_with_ffmpeg,
    register_download,
    sleep_progress,
)

if __name__ == "__main__":
    setup_logging("logs/descarga_capitulo_del_dia.log")
    nine_pm_today = datetime.combine(datetime.now().date(), time(21, 30))
    while True:
        today = datetime.now()
        if today.weekday() >= 5:
            print("Hoy es fin de semana. No hay capítulo.")
            exit(0)
        elif already_downloaded_today():
            print("✅ El capítulo de hoy ya fue descargado.")
            exit(0)

        if today < nine_pm_today:
            print(
                f"El capítulo de hoy aun no ha comenzado. Siguiente descarga en {nine_pm_today - today}"
            )
            difference = nine_pm_today - today
            seconds = difference.total_seconds()
            sleep_progress(seconds)
            continue

        url = get_episode_of_the_day()
        if url is None:
            sleep_progress(120)
            continue

        config = {
            "SERIE_NAME": "desafio siglo xxi 2025",
            "URL": url,
            "QUALITIES": [720, 360],
            "OUTPUT_FOLDER": Path("output"),
        }
        filename_template = "{serie_name_normalized}.capitulo.{number}.yt.{quality}p{ext}"  # ext debe tener el punto

        # Crear carpetas de salida si no existen
        temp_folder = config["OUTPUT_FOLDER"] / "TEMP"
        temp_folder.mkdir(parents=True, exist_ok=True)
        config["OUTPUT_FOLDER"].mkdir(exist_ok=True)

        # 1. PREPARAR TRABAJOS (JOBS)
        download_jobs = get_download_jobs(config)

        # 2. EJECUTAR DESCARGAS EN PARALELO
        downloaded_files = {}
        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
            print(f"🚀 Iniciando {len(download_jobs)} descargas en paralelo...")

            future_to_job = {
                executor.submit(
                    download_media_item, url, job["format_id"], temp_folder
                ): job
                for job in download_jobs
            }

            for future in concurrent.futures.as_completed(future_to_job):
                job = future_to_job[future]
                try:
                    filepath = future.result()
                    if job["type"] == "audio":
                        downloaded_files["audio"] = filepath
                    else:
                        if "videos" not in downloaded_files:
                            downloaded_files["videos"] = {}
                        downloaded_files["videos"][job["quality"]] = filepath
                except Exception as exc:
                    print(
                        f"Falló la descarga para {job['type']} {job['quality']}: {exc}"
                    )

        video_title = get_metadata(config["URL"])["title"]
        number = get_episode_number(video_title)
        serie_name_normalized = config["SERIE_NAME"].replace(" ", ".").lower()

        audio_path = downloaded_files["audio"]
        for quality, video_path in downloaded_files["videos"].items():
            ext = Path(video_path).suffix
            filename = filename_template.format(
                serie_name_normalized=serie_name_normalized,
                number=number,
                quality=quality,
                ext=ext,
            )
            output = str(config["OUTPUT_FOLDER"] / filename)
            merge_with_ffmpeg(video_path, audio_path, output)

        register_download(number)

        info = get_metadata(config["URL"])
        thumbnail = info.get("thumbnail", "")
        filename = f"{serie_name_normalized}.capitulo.{number}.yt.thumbnail.jpg"
        output = config["OUTPUT_FOLDER"] / filename
        if not output.exists():
            response = requests.get(thumbnail)
            with open(output, "wb") as f:
                f.write(response.content)

        # cleanup([video_path, audio_path])
        print("✅ Proceso completado.")
        break
