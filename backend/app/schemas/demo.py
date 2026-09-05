from pydantic import BaseModel


class DemoResetData(BaseModel):
    world_id: str
    clock_tick: int
    player_location_id: str
    quest_status: str
