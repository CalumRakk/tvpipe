from typing import Dict, List, TypedDict

from .common import ChannelInfo
from .metadata import EmocionItem, ProgramMetadata


class Container(TypedDict):
    id: str
    layout: str
    metadata: Dict[str, int]
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
    assets: List


class ResultObj(TypedDict):
    total: int
    containers: List[Container]


class ResultObjFilter(TypedDict):
    total: int
    containers: List[ContainerFilter]


class AssetEntitlement(TypedDict):
    assetId: int
    videoType: str
    assetType: str
    assetName: str
    rights: str


class EntitlementEntitlement(TypedDict):
    isContentOOHBlocked: bool
    isPlatformBlacklisted: bool
    assets: List[AssetEntitlement]


class ContainerEntitlement(TypedDict):
    id: str
    layout: str
    metadata: dict  # Vacío en este ejemplo. Cambiar si llega con estructura.
    entitlement: EntitlementEntitlement


class ResultObjEntitlement(TypedDict):
    total: int
    containers: List[ContainerEntitlement]
