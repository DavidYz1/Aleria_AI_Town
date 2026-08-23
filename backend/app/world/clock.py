from backend.app.world.types import TimePhase


def _minutes(time: str) -> int:
    hour_text, minute_text = time.split(":", maxsplit=1)
    hour, minute = int(hour_text), int(minute_text)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"invalid world time: {time}")
    return hour * 60 + minute


def advance_clock(day: int, time: str) -> tuple[int, str]:
    total = _minutes(time) + 60
    next_day = day + total // (24 * 60)
    next_minutes = total % (24 * 60)
    return next_day, f"{next_minutes // 60:02d}:{next_minutes % 60:02d}"


def get_time_phase(time: str) -> TimePhase:
    minute = _minutes(time)
    if 6 * 60 <= minute < 12 * 60:
        return "morning"
    if 12 * 60 <= minute < 18 * 60:
        return "day"
    if 18 * 60 <= minute < 22 * 60:
        return "evening"
    return "night"
