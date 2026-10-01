"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-30

The initial migration creates the whole schema directly from the SQLAlchemy
metadata in app.models, guaranteeing it matches the models exactly. Future
migrations should be generated with ``alembic revision --autogenerate``.
"""
from alembic import op

import app.models  # noqa: F401  (register models on Base.metadata)
from app.database import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)