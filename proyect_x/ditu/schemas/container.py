from typing import Dict, List, TypedDict

from .common import ChannelInfo
from .metadata import EmocionItem, ProgramMetadata


class Container(TypedDict):
    id: str
    layout: str  # Ej: "CHANNEL_ITEM"
    metadata: Dict[str, int]  # channelId
    containers: List[EmocionItem]


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
    assets: List  # Puedes definir esto si llegan datos


class ResultObj(TypedDict):
    total: int
    containers: List[Container]


class ResultObjFilter(TypedDict):
    total: int
    containers: List[ContainerFilter]
