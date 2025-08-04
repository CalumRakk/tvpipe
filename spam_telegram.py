import logging
import random
from pathlib import Path
from time import sleep

from pyrogram.errors.exceptions import PeerFlood

from proyect_x.logging_config import setup_logging
from proyect_x.uploader.send_video import get_client_started
from proyect_x.uploader.settings import get_settings
from proyect_x.utils import sleep_progress
from spam_telegram_utils import (
    has_user_been_messaged,
    has_user_been_peerfood,
    load_sent_user_ids,
    load_sent_user_ids_peerfood,
    mark_user_as_messaged,
    mark_user_as_peerfood,
)


def generar_mensaje(user_name, link):
    saludos = [
        f"Hola 👋 {user_name}",
        f"¡Hola {user_name}! 👋",
        f"Hey {user_name}",
        f"Saludos {user_name} 👋",
        f"{user_name},",
    ]

    cuerpo = [
        "el grupo anterior fue eliminado.",
        "ya no usamos el grupo anterior.",
        "el grupo anterior fue cerrado.",
        "el grupo anterior ya no está disponible.",
        "el grupo anterior fue dado de baja.",
    ]

    contenido = [
        "Ahora compartimos todo en 👉 @DESAFIO_SIGLO_XXI",
        "Todo el contenido ahora está en 👉 @DESAFIO_SIGLO_XXI",
        "Estamos usando un nuevo grupo 👉 @DESAFIO_SIGLO_XXI",
        "Ahora usamos 👉 @DESAFIO_SIGLO_XXI",
        "Nos mudamos a 👉 @DESAFIO_SIGLO_XXI",
    ]

    enlaces = [
        f"Únete aquí: {link}",
        f"Aquí el enlace directo: {link}",
        f"Puedes unirte aquí: {link}",
        f"Este es el enlace para entrar: {link}",
        f"Enlace para unirte: {link}",
    ]

    return f"{random.choice(saludos)}, {random.choice(cuerpo)} {random.choice(contenido)}\n{random.choice(enlaces)}"


if __name__ == "__main__":
    setup_logging(f"logs/{Path(__file__).stem}.log")
    logger = logging.getLogger(__name__)
    LINK = "https://t.me/+Jthh698ZVqQ4OGIx"
    config = get_settings(env_path=Path(".env/.upload_episode.test.env"))
    CHAT_ID = -1001207188185
    client = get_client_started(config)

    sent_cache = load_sent_user_ids()
    user_peerfood = load_sent_user_ids_peerfood()
    for usermember in client.get_chat_members(CHAT_ID):  # type: ignore
        user = usermember.user
        user_id = user.id
        if has_user_been_messaged(user_id, sent_cache) or has_user_been_peerfood(
            user_id, sent_cache
        ):
            logger.info(f"Already messaged user {user_id}, skipping.")
            continue
        elif "Deleted Account" in user.mention:
            continue

        logger.info(f"Sending message to user {user_id}...")
        message_text = generar_mensaje(user.first_name, LINK)
        try:
            msg = client.send_message(user_id, message_text)
        except PeerFlood:
            logger.info(f"PeerFlood for user {user_id},{user.first_name}, skipping.")
            sleep(random.randint(1, 3))
            mark_user_as_peerfood(user_id, sent_cache)
            continue

        mark_user_as_messaged(user_id, sent_cache)

        sleep_progress(random.randint(30, 60))
