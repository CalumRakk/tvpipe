from typing import List, Literal, Optional, Sequence, TypedDict, Union

from typing_extensions import NotRequired

QualityAlias = Literal["best", "medium", "low"]
KLabel = Literal[
    "2k", "4k", "5k", "6k", "8k"
]  # Resoluciones típicas en YouTube para etiquetas "k"
KLABEL_MAP = {
    "2k": 2560,
    "4k": 3840,
    "5k": 5120,
    "6k": 6144,
    "8k": 7680,
}

YOUTUBE_VIDEO_CODECS = {
    "avc1",  # H.264 (forma única)
    "vp9",  # VP9 (forma corta)
    "vp09",  # VP9 (forma larga, e.g. vp09.00.51.08)
    "av01",  # AV1 (forma única)
}
YOUTUBE_AUDIO_CODECS = {
    "mp4a",  # AAC (Advanced Audio Coding) → mp4a.40.2, mp4a.40.5, etc.
    "opus",  # Opus (en contenedor .webm)
    "vorbis",  # Vorbis (raro, usado en algunos videos viejos o bajos)
    "mp3",  # MP3 (extremadamente raro, pero técnicamente posible)
}

QUALITY = Union[QualityAlias, KLabel, int, str]


class DownloadJob(TypedDict):
    quality: Union[int, str]
    combinations: list[tuple[str, str]]
    url: str
    output_as_mp4: bool


class Fragment(TypedDict):
    """
    Representa un fragmento de un archivo de video/audio descargado por partes.
    """

    url: str  # URL del fragmento
    duration: float  # Duración del fragmento en segundos


class HttpHeaders(TypedDict, total=False):
    """
    Cabeceras HTTP utilizadas por el downloader para realizar la petición.
    """

    Accept: str
    Accept_Language: str
    Sec_Fetch_Mode: str
    User_Agent: str  # en yt-dlp aparece como "User-Agent"


class Format(TypedDict, total=False):
    """
    Representa **parcial** de un formato disponible del video o audio extraído con yt-dlp.
    """

    format_id: str  # ID del formato, ej: "140"
    format_note: Optional[str]  # Nota descriptiva, ej: "medium"
    ext: str  # Extensión del archivo, ej: "mp4"
    protocol: str  # Protocolo usado, ej: "https", "m3u8"
    acodec: str  # Códec de audio, ej: "mp4a.40.2"
    vcodec: str  # Códec de video, ej: "avc1.640028"
    url: str  # URL directa del recurso
    width: Optional[int]  # Ancho en píxeles, ej: 1280
    height: Optional[int]  # Alto en píxeles, ej: 720
    fps: Optional[float]  # Frames por segundo, ej: 29.97
    rows: Optional[int]  # Solo para storyboards
    columns: Optional[int]  # Solo para storyboards
    fragments: Optional[List[Fragment]]  # Lista de fragmentos si es segmentado
    audio_ext: Optional[str]  # Extensión de audio separada, ej: "m4a"
    video_ext: Optional[str]  # Extensión de video separada, ej: "mp4"
    vbr: Union[int, float, None]  # Bitrate de video aproximado
    abr: Union[int, float, None]  # Bitrate de audio aproximado
    tbr: Optional[float]  # Bitrate total
    resolution: Optional[str]  # Resolución como string, ej: "1280x720"
    aspect_ratio: Optional[float]  # Relación de aspecto
    filesize_approx: Optional[int]  # Tamaño estimado en bytes
    filesize: Optional[int]  # Tamaño exacto en bytes
    asr: Optional[int]  # Sample rate del audio, ej: 44100
    format: Optional[str]  # Descripción del formato completa
    http_headers: Optional[HttpHeaders]  # Cabeceras HTTP usadas
    manifest_url: Optional[str]  # URL de manifiesto (m3u8, dash)
    language: Optional[str]  # Idioma del audio, ej: "es"
    preference: Optional[int]  # Preferencia interna de yt-dlp
    quality: Optional[Union[int, float]]  # Calidad numérica
    has_drm: Optional[bool]  # Indica si tiene DRM
    audio_channels: Optional[int]  # Nº de canales de audio, ej: 2
    container: Optional[str]  # Contenedor, ej: "mp4"
    dynamic_range: Optional[str]  # Rango dinámico, ej: "SDR"
    downloader_options: Optional[dict]  # Opciones usadas por el downloader
    format_index: Optional[int]  # Índice del formato
    source_preference: Optional[int]  # Preferencia del origen (ej: youtube-dash)
    __needs_testing: Optional[bool]  # Interno de yt-dlp


class FormatSimple(TypedDict):
    """
    Representacion **parcial** de un formato especifico descargado.
    Contiene varios campos de format e incluye filepath del formato descargado.
    """

    format_id: str
    format_index: Optional[int]
    url: str
    manifest_url: str
    tbr: str
    ext: str
    fps: str
    protocol: str
    format: str  # 229 - 426x240
    filepath: str  # output\TEMP\nDL0xP1tWFY_229+140-drc_426x240.f229.mp4
    has_drm: bool
    width: Optional[int]
    height: Optional[int]
    vcodec: str
    acodec: str


class RequestedDownload(TypedDict):
    """
    Representa un archivo descargado (video, audio o combinado) **parcial***.
    Este objeto aparece dentro de `requested_downloads` como el primer elemento.
    """

    requested_formats: List[FormatSimple]  # Lista de formatos combinados
    format: str  # 229 - 426x240+140-drc - audio only (medium, DRC)
    format_id: str  # ID del formato combinado, ej: "137+140"
    ext: str  # Extensión final, ej: "mp4"
    protocol: str  # Protocolo de descarga, ej: "https"
    format_note: str  # Nota descriptiva, ej: "medium, DRC"
    filesize_approx: int  # Tamaño estimado en bytes 65002949
    tbr: Optional[float]  # Bitrate total
    width: int  # Ancho en píxeles, ej: 1280
    height: int  # Alto en píxeles, ej: 720
    resolution: str  # Resolución como string, ej: "1280x720"

    container: str  # Contenedor, ej: "mp4"
    http_headers: Optional[HttpHeaders]  # Cabeceras usadas en la descarga

    filename: NotRequired[
        str
    ]  # Ruta final del archivo descargado, ej: "output\\TEMP\\nDL0xP1tWFY_229+140-drc_426x240.mp4"
    filepath: NotRequired[
        str
    ]  # Ruta completa del archivo, ej: "D:\\rua\\de\\output\\TEMP\\nDL0xP1tWFY_229+140-drc_426x240.mp4"


class YtDlpResponse(TypedDict):
    """
    Representación *parcial* de la respuesta de yt-dlp --dump-json.
    Contiene información del video y los formatos descargados o disponibles.
    """

    id: str
    title: str
    formats: List[Format]
    requested_downloads: List[RequestedDownload]
    DownloadJob: (
        DownloadJob  # Información del job de descarga. Campo personalizado del script.
    )


class DownloadJobResult(TypedDict):
    download_job: DownloadJob
    ytdlp_response: YtDlpResponse
