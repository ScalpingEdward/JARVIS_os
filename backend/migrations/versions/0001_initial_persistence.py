"""Initial persistent JARVIS tables.

Revision ID: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("memories", sa.Column("id", sa.String(36), primary_key=True), sa.Column("content", sa.Text(), nullable=False), sa.Column("category", sa.String(100), nullable=False), sa.Column("tags", sa.JSON(), nullable=False), sa.Column("priority", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_memories_category", "memories", ["category"])
    op.create_table("agents", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(100), nullable=False), sa.Column("role", sa.String(100), nullable=False), sa.Column("capabilities", sa.JSON(), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("tasks", sa.Column("id", sa.String(36), primary_key=True), sa.Column("title", sa.String(200), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("priority", sa.Integer(), nullable=False), sa.Column("required_capabilities", sa.JSON(), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("assigned_agent_id", sa.String(36), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("worker_runs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("task_id", sa.String(36), nullable=False), sa.Column("worker_name", sa.String(100), nullable=False), sa.Column("provider", sa.String(50), nullable=False), sa.Column("external_run_id", sa.String(255), nullable=True), sa.Column("status", sa.String(30), nullable=False), sa.Column("result", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    op.drop_table("worker_runs")
    op.drop_table("tasks")
    op.drop_table("agents")
    op.drop_index("ix_memories_category", table_name="memories")
    op.drop_table("memories")
