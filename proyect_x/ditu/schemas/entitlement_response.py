from typing import List, TypedDict


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


class EntitlementChannelResponse(TypedDict):
    resultCode: str
    message: str
    errorDescription: str
    resultObj: ResultObjEntitlement
    systemTime: int
