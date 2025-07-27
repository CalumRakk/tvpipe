from typing import TypedDict

from .container import ResultObjFilter


class FilterResponse(TypedDict):
    resultCode: str
    message: str
    errorDescription: str
    resultObj: ResultObjFilter
    systemTime: int
