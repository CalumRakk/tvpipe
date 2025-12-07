import logging
from pathlib import Path

from proyect_x.config import get_config
from proyect_x.logging_config import setup_logging
from proyect_x.yt_downloader.client import YtDlpClient
from proyect_x.yt_downloader.processing import download_thumbnail, merge_video_audio
from proyect_x.yt_downloader.runner import get_episode_number_from_title

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

        # Seleccionar Calidad
        quality_pref = str(yt_config.qualities[0]) if yt_config.qualities else "1080p"
        logger.info(f"Buscando calidad preferida: {quality_pref}")

        video_stream, audio_stream = client.select_best_pair(
            meta, quality_preference=quality_pref, require_mp4=False
        )

        # Preparar rutas
        temp_dir = yt_config.download_folder / "TEMP"
        temp_dir.mkdir(parents=True, exist_ok=True)

        vid_path = (
            temp_dir
            / f"DEBUG_{yt_config.serie_slug}_{episode_num}_{video_stream.format_id}.{video_stream.ext}"
        )
        aud_path = (
            temp_dir
            / f"DEBUG_{yt_config.serie_slug}_{episode_num}_{audio_stream.format_id}.{audio_stream.ext}"
        )

        final_filename = f"DEBUG_{yt_config.serie_slug}.capitulo.{episode_num}.mp4"
        final_path = yt_config.download_folder / final_filename

        # Descargar Streams
        logger.info(f"Descargando Video ({video_stream.height}p)...")
        client.download_stream(video_stream, vid_path, TEST_URL)

        logger.info(f"Descargando Audio ({audio_stream.acodec})...")
        client.download_stream(audio_stream, aud_path, TEST_URL)

        # Procesamiento
        logger.info("Fusionando audio y video...")
        merge_video_audio(vid_path, aud_path, final_path)

        # Miniatura
        thumb_path = (
            yt_config.download_folder
            / f"DEBUG_{yt_config.serie_slug}.capitulo.{episode_num}.jpg"
        )
        download_thumbnail(meta.thumbnail_url, thumb_path)

        logger.info(f"PRUEBA EXITOSA.")
        logger.info(f"Video guardado en: {final_path}")
        logger.info(f"Miniatura guardada en: {thumb_path}")

    except Exception as e:
        logger.error(f"Error durante la prueba: {e}", exc_info=True)


if __name__ == "__main__":
    debug_single_download()
