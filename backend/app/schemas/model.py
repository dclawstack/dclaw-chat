from pydantic import BaseModel


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str  # local | cloud
    description: str
    available: bool
