import logging
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from tvpipe.config import AppConfig, get_config
from tvpipe.logging_config import setup_logging
from tvpipe.services.caracoltv import CaracolTVSchedule
from tvpipe.services.program_monitor import ProgramMonitor
from tvpipe.services.publisher import EpisodePublisher
from tvpipe.services.register import RegistryManager
from tvpipe.services.telegram import TelegramService
from tvpipe.services.telegram.schemas import UploadedVideo
from tvpipe.services.watermark import WatermarkService
from tvpipe.services.youtube.client import YtDlpClient
from tvpipe.services.youtube.service import YouTubeFetcher
from tvpipe.services.youtube.strategies import CaracolDesafioParser
from tvpipe.utils import sleep_progress

logger = logging.getLogger("Orchestrator")


def should_skip_weekends() -> bool:
    """Helper para lógica de fines de semana."""
    return datetime.now().weekday() >= 5


def wait_end_of_day():
    """Duerme hasta las 23:59:59."""
    now = datetime.now()
    end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59)
    diff = (end_of_day - now).total_seconds()
    if diff > 0:
        logger.info("Esperando hasta el fin del día...")
        sleep_progress(diff)


@contextmanager
def add_watermark_to_image(
    iamge_path: Path, watermark_text: str, watermark_service: WatermarkService
):
    temp_dir = tempfile.TemporaryDirectory()
    try:
        watermarked_thumb = Path(temp_dir.name) / Path("thumbnail_watermarked.jpg")
        watermark_service.add_watermark_to_image(
            str(iamge_path), watermark_text, str(watermarked_thumb)
        )
        yield watermarked_thumb
    finally:
        temp_dir.cleanup()


def get_or_upload_video(
    video_path: Path,
    thumbnail_path: Path,
    config: AppConfig,
    register: RegistryManager,
    tg_service: TelegramService,
) -> UploadedVideo:
    """
    Intenta recuperar el video del caché (registro + validación en TG).
    Si no existe o no es válido, lo sube y registra el evento.
    """
    if register.was_video_uploaded(video_path):
        data = register.get_video_uploaded(video_path)
        chat_id = data["chat_id"]
        message_id = data["message_id"]

        if tg_service.exists_video_in_chat(chat_id, message_id):
            logger.info(f"Video reutilizado desde caché: {video_path.name}")
            return tg_service.fetch_video_uploaded(chat_id, message_id)
        else:
            logger.warning(
                f"Entrada de caché inválida para {video_path.name}. Limpiando registro."
            )
            register.remove_video_entry(video_path)

    logger.info(f"🚀 Subiendo archivo nuevo: {video_path.name}")
    uploaded_video = tg_service.upload_video(
        video_path=video_path,
        thumbnail_path=thumbnail_path,
        target_chat_id=config.telegram.chat_id_temporary,
        caption=video_path.name,
    )

    register.register_video_uploaded(
        uploaded_video.message_id, uploaded_video.chat_id, video_path
    )

    return uploaded_video


def run_orchestrator():
    setup_logging(f"logs/{Path(__file__).stem}.log")
    config = get_config("config.env")

    register = RegistryManager()

    # Servicios
    tg_service = TelegramService(
        session_name=config.telegram.session_name,
        api_id=config.telegram.api_id,
        api_hash=config.telegram.api_hash,
        workdir=config.telegram.to_telegram_working,
    )

    schedule_client = CaracolTVSchedule()
    monitor = ProgramMonitor(schedule_client, "desafio")
    watermark_service = WatermarkService()

    publisher = EpisodePublisher(
        config=config.telegram,
        client=tg_service,
    )
    yt_client = YtDlpClient()
    desafio_strategy = CaracolDesafioParser()
    downloader = YouTubeFetcher(
        config.youtube, register, desafio_strategy, client=yt_client
    )

    logger.info(">>> SISTEMA INICIADO: Orquestador en control <<<")

    while True:
        try:
            # Si `config.youtube.url` está definido, se trata de un modo manual.
            if not config.youtube.url:
                # Comprobación de fin de semana
                if config.youtube.skip_weekends and should_skip_weekends():
                    logger.info("Es fin de semana. No hay emisión.")
                    wait_end_of_day()
                    continue

                # Comprobacion de Horario
                if monitor.should_wait():
                    monitor.wait_until_release()
                    continue

                episode_meta = downloader.fetch_episode()
                if not episode_meta:
                    logger.info("Video no disponible aún. Reintentando en 2 minutos...")
                    sleep_progress(120)
                    continue
            else:
                episode_meta = downloader.fetch_episode()
                if episode_meta is None:
                    raise Exception("No se pudo descargar el episodio.")

            logger.info(f"Procesando episodio: {episode_meta.title}")

            # Descarga de video
            ep_dled = downloader.download_episode(episode_meta)
            register.register_downloads(ep_dled.episode_number, ep_dled.video_paths)

            # Descarga de thumbnail
            thumbnail_path = downloader.download_thumbnail(episode_meta)

            with add_watermark_to_image(
                thumbnail_path, "https://t.me/DESAFIO_SIGLO_XXI", watermark_service
            ) as watermarked_thumb:
                ready_to_publish_list = []
                for video_path in ep_dled.video_paths:
                    if register.was_video_uploaded(video_path):
                        data = register.get_video_uploaded(video_path)
                        chat_id = data["chat_id"]
                        message_id = data["message_id"]
                        if tg_service.exists_video_in_chat(chat_id, message_id):
                            logger.info("Video reutilizado desde caché.")
                            uploaded_video = tg_service.fetch_video_uploaded(
                                chat_id, message_id
                            )
                            ready_to_publish_list.append(uploaded_video)
                            continue
                        else:
                            logger.info(
                                "Entrada de caché inválida. Limpiando registro."
                            )
                            register.remove_video_entry(video_path)

                    uploaded_video = tg_service.upload_video(
                        video_path=video_path,
                        thumbnail_path=watermarked_thumb,
                        target_chat_id=config.telegram.chat_id_temporary,
                        caption=video_path.name,
                    )
                    ready_to_publish_list.append(uploaded_video)
                    chat_id = uploaded_video.chat_id
                    message_id = uploaded_video.message_id
                    register.register_video_uploaded(message_id, chat_id, video_path)

                succes = publisher.publish(
                    ep_dled.episode_number, ready_to_publish_list
                )
                if succes:
                    register.register_episode_publication(ep_dled.episode_number)
                    logger.info(f"Episodio {ep_dled.episode_number} publicado.")
                else:
                    logger.error("No se pudo publicar el episodio.")

            if config.youtube.url:
                logger.info("Modo manual finalizado.")
                break
        except KeyboardInterrupt:
            logger.info("Deteniendo orquestador por solicitud del usuario.")
            break
        except Exception as e:
            logger.error(f"Error crítico en el bucle principal: {e}", exc_info=True)
            sleep_progress(60)


if __name__ == "__main__":
    run_orchestrator()
