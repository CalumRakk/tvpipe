from typing import Dict, List, Literal, TypedDict

from .common import ChannelInfo, ProgramMetadata


class ProgramItem(TypedDict):
    id: str
    layout: Literal["CONTENT_ITEM"]
    metadata: ProgramMetadata
    channel: ChannelInfo


class ChannelItem(TypedDict):
    id: str
    layout: str
    metadata: Dict[str, int]
    containers: List[ProgramItem]


class ResultObj(TypedDict):
    total: int
    containers: List[ChannelItem]


class RawTVScheduleResponse(TypedDict):
    resultCode: str
    message: str
    errorDescription: str
    resultObj: ResultObj
