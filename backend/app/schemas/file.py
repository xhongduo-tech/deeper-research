from datetime import datetime
from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    id: int
    filename: str
    original_name: str
    file_type: str
    file_size: int
    created_at: datetime

    model_config = {"from_attributes": True}
