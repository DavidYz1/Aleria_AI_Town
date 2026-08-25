from typing import Literal

from pydantic import BaseModel


class HealthData(BaseModel):
    status: Literal["ok"] = "ok"
    database: Literal["ok"] = "ok"
    chat_provider: str
