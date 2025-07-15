from pathlib import Path

import requests

from series_manager.yt_dlp_tools import (
    download_audio,
    download_video,
    get_episode_number,
    get_metadata,
    merge_with_ffmpeg,
)

if __name__ == "__main__":
    config = {
        "SERIE_NAME": "desafio siglo xxi 2025",
        "URL": "https://www.youtube.com/watch?v=707aqENykIA",
        "QUALITIES": [720],
        "OUTPUT_FOLDER": Path("output"),
    }
    filename_template = "{serie_name_normalized}.capitulo.{number}.avance.yt.{quality}p{ext}"  # ext debe tener el punto

    video_paths = download_video(config)
    audio_path = download_audio(config)

    video_title = get_metadata(config["URL"])["title"]
    number = get_episode_number(video_title)
    serie_name_normalized = config["SERIE_NAME"].replace(" ", ".").lower()
    for quality, video_path in video_paths:
        ext = Path(video_path).suffix
        filename = filename_template.format(
            serie_name_normalized=serie_name_normalized,
            number=number,
            quality=quality,
            ext=ext,
        )
        output = str(config["OUTPUT_FOLDER"] / filename)
        merge_with_ffmpeg(video_path, audio_path, output)

    info = get_metadata(config["URL"])
    thumbnail = info.get("thumbnail", "")
    filename = f"{serie_name_normalized}.capitulo.{number}.avance.yt.thumbnail.jpg"
    output = config["OUTPUT_FOLDER"] / filename
    if not output.exists():
        response = requests.get(thumbnail)
        with open(output, "wb") as f:
            f.write(response.content)

    # cleanup([video_path, audio_path])
    print("✅ Proceso completado.")
