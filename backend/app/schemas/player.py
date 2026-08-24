from pydantic import BaseModel, ConfigDict, Field


class PlayerTravelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_location_id: str = Field(
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )


class PlayerData(BaseModel):
    id: str
    location_id: str
    location_name: str
