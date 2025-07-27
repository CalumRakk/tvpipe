from typing import List, Literal, Optional, TypedDict


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
