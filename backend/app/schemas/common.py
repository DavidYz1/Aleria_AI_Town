from typing import Generic, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    message: str = "ok"


class ErrorResponse(BaseModel):
    success: bool = False
    data: None = None
    message: str
