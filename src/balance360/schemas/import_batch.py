from pydantic import BaseModel


class ImportBatchCreate(BaseModel):
    filename: str

class ImportBatchUpdate(BaseModel):
    filename: str|None = None