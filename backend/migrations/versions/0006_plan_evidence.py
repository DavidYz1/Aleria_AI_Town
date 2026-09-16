"""Record which memories fed each planning decision.

Nullable with **no server default** on purpose: plans written before this
revision genuinely have no such record. Defaulting them to an empty array would
assert "this plan cited nothing", which is a claim the data cannot support and
which the UI would render as "referenced no memories" instead of "not recorded".
"""

from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_plans",
        sa.Column("evidence_memory_ids_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_plans", "evidence_memory_ids_json")
