from pydantic import BaseModel


class TurnRequest(BaseModel):
    content: str
