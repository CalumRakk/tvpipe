from typing import TypedDict


class ResultObjDash(TypedDict):
    src: str
    token: str


class DashManifestResponse(TypedDict):
    resultCode: str
    message: str
    errorDescription: str
    resultObj: ResultObjDash
    systemTime: int
