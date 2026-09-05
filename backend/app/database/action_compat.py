"""Temporary action-name adapter for the legacy database constraints."""


def to_persistence_action_type(action_type: str) -> str:
    return "social" if action_type == "talk" else action_type


def to_public_action_type(action_type: str) -> str:
    return "talk" if action_type == "social" else action_type
