import logging
from datetime import datetime
from pathlib import Path

from decouple import Config, RepositoryEnv, UndefinedValueError

from logging_config import setup_logging

setup_logging(f"logs/{Path(__file__).stem}.log")
logger = logging.getLogger(__name__)
config = Config(repository=RepositoryEnv(".env"))

# --- Configuración de Telegram ---

API_HASH = str(config("API_HASH"))
API_ID = int(config("API_ID"))
CHAT_ID = int(config("CHAT_ID"))
PROJECT_NAME = str(config("PROJECT_NAME"))

# --- CONFIGURACIÓN DE YOUTUBE ---
try:
    YOUTUBE_RELEASE_TIME = str(config("YOUTUBE_RELEASE_TIME"))
except UndefinedValueError:
    YOUTUBE_RELEASE_TIME = "9:30 PM"
    logger.error(
        f"No se encontró la variable YOUTUBE_RELEASE_TIME en el archivo .env. Usando el valor por defecto: {YOUTUBE_RELEASE_TIME}"
    )
YOUTUBE_RELEASE_TIME = datetime.strptime(YOUTUBE_RELEASE_TIME, "%I:%M %p").time()

# --- Configuración de captura de stream ---
try:
    STREAM_CAPTURE_START_TIME = str(config("START_STREAM_CAPTURE"))
except UndefinedValueError:
    STREAM_CAPTURE_START_TIME = "7:55 PM"
    logger.error(
        f"No se encontró la variable START_STREAM_CAPTURE en el archivo .env. Usando el valor por defecto: {STREAM_CAPTURE_START_TIME }"
    )
STREAM_CAPTURE_START_TIME = datetime.strptime(
    STREAM_CAPTURE_START_TIME, "%I:%M %p"
).time()

try:
    STREAM_CAPTURE_END_TIME = str(config("END_STREAM_CAPTURE"))
except UndefinedValueError:
    STREAM_CAPTURE_END_TIME = "09:45 PM"
    logger.error(
        f"No se encontró la variable END_STREAM_CAPTURE en el archivo .env. Usando el valor por defecto: {STREAM_CAPTURE_END_TIME }"
    )
STREAM_CAPTURE_END_TIME = datetime.strptime(STREAM_CAPTURE_END_TIME, "%I:%M %p").time()

# --- Validaciones ---
if STREAM_CAPTURE_END_TIME <= STREAM_CAPTURE_START_TIME:
    logger.warning(
        f"STREAM_CAPTURE_END_TIME ({STREAM_CAPTURE_END_TIME}) debe ser posterior a STREAM_CAPTURE_START_TIME ({STREAM_CAPTURE_START_TIME}). Ajusta la configuración."
    )
    raise ValueError("Hora de fin de captura debe ser posterior a la hora de inicio.")
