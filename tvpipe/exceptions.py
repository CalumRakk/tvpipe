class TVPipeError(Exception):
    """Clase base para todas las excepciones del proyecto."""

    pass


# Excepciones de Descarga
class DownloadError(TVPipeError):
    """Fallo general en la descarga de archivos."""

    pass


class EpisodeNotFoundError(TVPipeError):
    """No se encontró el episodio o los metadatos son inválidos."""

    pass


# Excepciones de Telegram
class TelegramError(TVPipeError):
    """Clase base para errores de Telegram."""

    pass


class TelegramConnectionError(TelegramError):
    """Problemas de red o sesión perdida con Telegram."""

    pass


class ContentNotFoundError(TelegramError):
    """El mensaje/video buscado en Telegram no existe (fue borrado)."""

    pass


class UploadError(TelegramError):
    """Fallo al subir un archivo."""

    pass
