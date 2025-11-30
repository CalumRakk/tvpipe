import logging
import time
from typing import Generator

from proyect_x.config import DownloaderConfig
from proyect_x.services.caracoltv import CaracolTV
from proyect_x.services.register import RegistryManager

from .client import YtDlpClient
from .models import DownloadedEpisode
from .processing import download_thumbnail, merge_video_audio
from .services.scheduling import get_episode_url

logger = logging.getLogger(__name__)


def get_episode_number_from_title(title: str) -> str:
    import re

    match = re.search(r"ap[íi]tulo\s+(\d+)", title, re.IGNORECASE)
    return match.group(1) if match else "00"


def main_loop(
    config: DownloaderConfig, registry: RegistryManager, schedule: CaracolTV
) -> Generator[DownloadedEpisode, None, None]:

    client = YtDlpClient()

    temp_dir = config.download_folder / "TEMP"
    temp_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Iniciando bucle principal de descargas (Refactorizado)")

    while True:
        try:
            # 1. Obtener URL
            url = get_episode_url(config, registry, schedule)
            if not url:
                time.sleep(60)
                continue

            # 2. Obtener Metadatos (Pydantic)
            meta = client.get_metadata(url)
            episode_num = get_episode_number_from_title(meta.title)

            # 3. Estrategia de Selección
            # Iteramos sobre las calidades de config (ej: ["best", "360"])
            quality_pref = str(config.qualities[0]) if config.qualities else "1080p"

            video_stream, audio_stream = client.select_best_pair(
                meta, quality_preference=quality_pref, require_mp4=config.output_as_mp4
            )

            # 4. Descarga secuencial.
            vid_path = (
                temp_dir
                / f"{config.serie_slug}_{episode_num}_{video_stream.format_id}.{video_stream.ext}"
            )
            aud_path = (
                temp_dir
                / f"{config.serie_slug}_{episode_num}_{audio_stream.format_id}.{audio_stream.ext}"
            )

            client.download_stream(video_stream, vid_path)
            client.download_stream(audio_stream, aud_path)

            # 5. Procesamiento
            final_filename = f"{config.serie_slug}.capitulo.{episode_num}.mp4"
            final_path = config.download_folder / final_filename

            merge_video_audio(vid_path, aud_path, final_path)

            # Miniatura
            thumb_path = (
                config.download_folder
                / f"{config.serie_slug}.capitulo.{episode_num}.jpg"
            )
            download_thumbnail(meta.thumbnail_url, thumb_path)

            # 6. Yield Resultado
            yield DownloadedEpisode(
                episode_number=episode_num,
                video_path=final_path,
                thumbnail_path=thumb_path,
            )

            logger.info(f"Ciclo terminado para episodio {episode_num}")

        except Exception as e:
            logger.error(f"Error en el ciclo de descarga: {e}", exc_info=True)
            time.sleep(30)
