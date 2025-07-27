from datetime import datetime
from typing import Dict, List, Literal, Optional, TypedDict

from pydantic import BaseModel


class ChannelInfo(TypedDict):
    channelId: int
    channelName: str


class CopyProtection(TypedDict):
    securityCode: str
    securityOption: str


class ExtendedMetadata(TypedDict, total=False):
    contentType: str
    contentSubType: str
    tagValue: Optional[str]
    linearDescriptionFormat: Optional[List[str]]


class RawProgramMetadata(TypedDict):
    contentId: int  # ID interno del contenido/programa
    externalId: str  # ID externo o de referencia del sistema fuente
    contentType: Literal["PROGRAM"]  # Tipo de contenido (usualmente "PROGRAM")
    title: str  # Título del programa o emisión
    longDescription: str  # Descripción larga del contenido
    shortDescription: str  # Descripción breve del contenido
    startTime: int  # Hora de inicio (milisegundos UNIX)
    airingStartTime: int  # Hora de inicio real de transmisión (milisegundos UNIX)
    airingEndTime: int  # Hora de fin real de transmisión (milisegundos UNIX)
    duration: int  # Duración en minutos del programa
    episodeNumber: int  # Número del episodio (si aplica)
    season: int  # Número de la temporada (si aplica)
    episodeId: int  # ID del episodio (puede coincidir con episodeNumber)
    episodeTitle: str  # Título del episodio (si tiene)
    isGeoBlocked: bool  # Indica si tiene restricción geográfica
    isRecordable: bool  # Indica si el contenido puede ser grabado
    isStartOver: bool  # Permite volver al inicio del programa
    isCatchUp: bool  # Permite ver el programa después de emitido (modo "catch-up")
    isPlatformBlacklisted: (
        bool  # Indica si el contenido está bloqueado en alguna plataforma
    )
    isCopyProtected: bool  # Si tiene protección contra copia
    copyProtections: List[CopyProtection]  # Lista de reglas de protección contra copia
    pcLevel: int  # Nivel de control parental
    pcExtendedRatings: List[
        str
    ]  # Clasificaciones extendidas (ej. "V" = violencia, "SX" = sexo)
    extendedMetadata: ExtendedMetadata  # Otros metadatos como tipo/subtipo y tags


class EmocionItem(TypedDict):
    id: str
    layout: Literal["CONTENT_ITEM"]
    metadata: RawProgramMetadata
    channel: ChannelInfo


class RawChannelContainer(TypedDict):
    id: str
    layout: Literal["CHANNEL_ITEM"]
    metadata: Dict[str, int]  # channelId
    containers: List[EmocionItem]


class ResultObject(TypedDict):
    total: int
    containers: List[RawChannelContainer]


class RawTVScheduleResponse(TypedDict):
    resultCode: str
    message: str
    errorDescription: str
    resultObj: ResultObject


class SimpleSchedule(BaseModel):
    contentId: int
    title: str
    shortDescription: str

    airingStartTime: int
    airingEndTime: int
    duration: int

    episodeId: int
    episodeTitle: str
    episodeNumber: int
    season: int

    @property
    def content_id(self) -> int:
        return self.content_id

    @property
    def episode_id(self) -> int:
        return self.episodeId

    @property
    def episode_number_str(self) -> int:
        return self.episodeNumber

    @property
    def episode_title(self) -> str:
        return self.episodeTitle.strip()

    @property
    def short_description(self) -> str:
        return self.shortDescription.strip()

    @property
    def start_time(self) -> datetime:
        return datetime.fromtimestamp(self.airingStartTime / 1000)

    @property
    def end_time(self) -> datetime:
        return datetime.fromtimestamp(self.airingEndTime / 1000)

    @property
    def start_time_as_12hours(self) -> str:
        return self.start_time.strftime("%I:%M %p")

    @property
    def end_time_as_12hours(self) -> str:
        return self.end_time.strftime("%I:%M %p")
