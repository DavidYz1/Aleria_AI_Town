"""Read compatibility for pre-0003 action names."""


def to_persistence_action_type(action_type: str) -> str:
    return "talk" if action_type == "social" else action_type


def to_public_action_type(action_type: str) -> str:
    return "talk" if action_type == "social" else action_type
