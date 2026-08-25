from pydantic import BaseModel


class DemoResetData(BaseModel):
    world_id: str
    world_tick: int
    player_location_id: str
    quest_status: str
