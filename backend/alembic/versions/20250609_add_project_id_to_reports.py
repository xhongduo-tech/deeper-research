"""add_project_id_to_reports

Revision ID: 20250609_add_project_id
Revises: e0d8347bf0e8
Create Date: 2026-06-09 10:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250609_add_project_id'
down_revision: Union[str, None] = 'e0d8347bf0e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('reports', sa.Column('project_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_reports_project_id'), 'reports', ['project_id'], unique=False)
    op.create_foreign_key('fk_reports_project_id', 'reports', 'projects', ['project_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_reports_project_id', 'reports', type_='foreignkey')
    op.drop_index(op.f('ix_reports_project_id'), table_name='reports')
    op.drop_column('reports', 'project_id')
