from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel


class UploadedVideo(BaseModel):
    file_id: str
    message_id: int
    chat_id: int
    file_path: Path
    file_name: str
    size_bytes: int
    width: int
    height: int
    duration: int
    caption: Optional[str] = None


class UploaderSessionInfo(BaseModel):
    id: int
    username: Optional[str]
    first_name: Optional[str]
    is_bot: bool


class UploadResult(BaseModel):
    session_info: UploaderSessionInfo
    uploaded_files: List[UploadedVideo]
    target_chat_ids: List[int]
    media_group_id: Optional[str] = None
