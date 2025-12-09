import logging
from pathlib import Path

from tvpipe.config import get_config
from tvpipe.logging_config import setup_logging
from tvpipe.utils import download_thumbnail
from tvpipe.yt_downloader.client import YtDlpClient
from tvpipe.yt_downloader.runner import get_episode_number_from_title

# --- CONFIGURACIÓN DE LA PRUEBA ---
TEST_URL = "https://www.youtube.com/watch?v=pfELv3BsuVQ"


def debug_single_download():
    setup_logging(f"logs/{Path(__file__).stem}.log")
    logger = logging.getLogger("DebugSingle")

    config = get_config("config.env")
    yt_config = config.youtube

    logger.info(f"--- Iniciando prueba de descarga para: {TEST_URL} ---")
    client = YtDlpClient()
    try:
        # Obtener Metadatos
        logger.info("Obteniendo metadatos...")
        meta = client.get_metadata(TEST_URL)
        episode_num = get_episode_number_from_title(meta.title)
        logger.info(f"Título detectado: {meta.title}")
        logger.info(f"Episodio detectado: {episode_num}")

        # Selecciona StreamPar
        quality_pref = str(yt_config.qualities[0]) if yt_config.qualities else "1080p"
        stream = client.select_best_pair(
            meta, quality_preference=quality_pref, require_mp4=False
        )

        # Crear nombre de archivo
        filename = config.youtube.generate_filename(episode_num, stream.height)
        output_path = config.youtube.download_folder / filename

        logger.info(f"Descargando Video ({stream.height}p)...")
        client.download_stream(stream, output_path, TEST_URL)

        thumb_path = output_path.with_suffix(".jpg")
        download_thumbnail(meta.thumbnail_url, thumb_path)

        logger.info(f"PRUEBA EXITOSA.")
        logger.info(f"Video guardado en: {output_path}")
        logger.info(f"Miniatura guardada en: {thumb_path}")

    except Exception as e:
        logger.error(f"Error durante la prueba: {e}", exc_info=True)


if __name__ == "__main__":
    debug_single_download()
