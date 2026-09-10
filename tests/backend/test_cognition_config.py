"""Catch unbounded request work accepted through configuration."""
import pytest
from pydantic import ValidationError
from backend.app.core.config import Settings


@pytest.mark.parametrize("field,value", [
    ("cognition_source_batch_size", 0), ("cognition_source_batch_size", 101),
    ("cognition_attention_budget", 0), ("cognition_attention_budget", 51),
    ("cognition_post_commit_budget_seconds", 0), ("cognition_post_commit_budget_seconds", 31),
])
def test_cognition_configuration_rejects_unbounded_work(field, value):
    with pytest.raises(ValidationError): Settings(_env_file=None, **{field: value})
