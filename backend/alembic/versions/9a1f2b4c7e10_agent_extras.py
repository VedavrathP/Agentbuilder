"""add channels, skills, interaction_rules, scheduling FK to agents

Revision ID: 9a1f2b4c7e10
Revises: 3248209124e7
Create Date: 2026-05-30 12:55:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9a1f2b4c7e10"
down_revision: Union[str, None] = "3248209124e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "channels",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "agents",
        sa.Column(
            "skills",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "agents",
        sa.Column(
            "interaction_rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "agents",
        sa.Column("default_workflow_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("schedule_input", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_agents_default_workflow",
        "agents",
        "workflows",
        ["default_workflow_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_agents_default_workflow", "agents", type_="foreignkey")
    op.drop_column("agents", "schedule_input")
    op.drop_column("agents", "default_workflow_id")
    op.drop_column("agents", "interaction_rules")
    op.drop_column("agents", "skills")
    op.drop_column("agents", "channels")
