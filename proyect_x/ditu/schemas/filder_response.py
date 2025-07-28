from typing import List, TypedDict

from proyect_x.ditu.schemas.common import ChannelInfo, ProgramMetadata


class Action(TypedDict):
    key: str
    uri: str
    targetType: str


class ContainerFilter(TypedDict):
    id: str
    layout: str
    actions: List[Action]
    metadata: ProgramMetadata
    channel: ChannelInfo
    assets: List


class ResultObjFilter(TypedDict):
    total: int
    containers: List[ContainerFilter]


class FilterResponse(TypedDict):
    resultCode: str
    message: str
    errorDescription: str
    resultObj: ResultObjFilter
    systemTime: int
