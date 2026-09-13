"""Guard the authoritative Stage 2 delivery documents against known regressions."""
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_stage2_documents_reject_known_stale_implementation_claims():
    documents = "\n".join((
        read("README.md"),
        read("docs/05_Engineering_Architecture.md"),
        read("docs/06_API_Contract.md"),
    ))
    stale_claims = (
        "Memory、LLM 规划、Agent Lab、异步 202、Celery/Redis/SSE 都留给后续阶段",
        "尚无 vector 列或 Memory 功能",
        "memory and LLM action-cognition APIs are not implemented",
        "cancellation and budgets are not implemented in this phase",
        "anonymous endpoint has no observable side effect on memory state",
    )

    for stale in stale_claims:
        assert stale not in documents


def test_stage2_documents_name_the_delivered_schema_api_and_commit_boundary():
    architecture = read("docs/05_Engineering_Architecture.md")
    api_contract = read("docs/06_API_Contract.md")
    authoritative = architecture + "\n" + api_contract + "\n" + read("README.md")

    assert "0004" in authoritative
    assert "GET /api/npcs/{npc_id}/memory-explanations" in authoritative
    assert "post-commit" in architecture
    assert "Project the committed turn into cognition (post-commit, best-effort)" in api_contract


def test_current_state_records_stage2_task5_incremental_rereview_complete():
    current = read("CURRENT_STATE.md")

    assert "| 9 | ✅ | Codex |" in current
    assert "| 10 | ✅ | Codex |" in current
    assert "增量 re-review：**PASS — Critical 0 / Important 0**" in current
    assert "Step 10 final fix round 1 进行中" not in current
    assert "段 2 未开始" not in current
    assert "停在 Step 8" not in current
