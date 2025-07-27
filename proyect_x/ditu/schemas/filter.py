from typing import TypedDict

from proyect_x.ditu.schemas.common import ResultObjDash

from .container import ResultObjEntitlement, ResultObjFilter


class FilterResponse(TypedDict):
    resultCode: str
    message: str
    errorDescription: str
    resultObj: ResultObjFilter
    systemTime: int


class EntitlementLiveChannel(TypedDict):
    resultCode: str
    message: str
    errorDescription: str
    resultObj: ResultObjEntitlement
    systemTime: int


class DashManifestResponse(TypedDict):
    resultCode: str
    message: str
    errorDescription: str
    resultObj: ResultObjDash
    systemTime: int
