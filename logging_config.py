import logging
import os


def logger_formatter() -> logging.Formatter:
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%d-%m-%Y %I:%M:%S %p",
    )
    return formatter


def handler_stream(formatter: logging.Formatter) -> logging.StreamHandler:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    return console_handler


def handler_file(path: str, formatter: logging.Formatter) -> logging.FileHandler:
    file_handler = logging.FileHandler(path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    return file_handler


def setup_logging(path: str) -> None:
    """Configura el logging básico para la aplicación."""
    default_formatter = logger_formatter()
    running_under_supervisord = any(
        key in os.environ
        for key in [
            "SUPERVISOR_PROCESS_NAME",
            "SUPERVISOR_ENABLED",
            "SUPERVISOR_GROUP_NAME",
        ]
    )
    handlers = [handler_stream(default_formatter)]

    if not running_under_supervisord:
        # Solo usa FileHandler si NO estamos bajo supervisord
        handlers.append(handler_file(path, default_formatter))

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=handlers,
    )

    # Silenciar loggers de librerías de terceros
    libraries_to_silence = [
        "urllib3",
        "seleniumwire",
        "selenium",
        "undetected_chromedriver",
        "hpack",
        "peewee",
    ]
    for lib_name in libraries_to_silence:
        logging.getLogger(lib_name).setLevel(logging.CRITICAL)
