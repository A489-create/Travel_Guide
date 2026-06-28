"""add conversation current_plan_id

Revision ID: 359ccc1432fa
Revises: 9a11aba01b42
Create Date: 2026-06-27 23:56:18.360449

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '359ccc1432fa'
down_revision: Union[str, Sequence[str], None] = '9a11aba01b42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 注意：已移除 autogenerate 误判的 5 处 drop_index（idx_conv_user_updated /
    # idx_ke_dest_type / idx_ke_embedding / idx_msg_conv_id / idx_tp_user_created），
    # 这些索引在 init_schema 中手动创建（含 ivfflat 向量索引），不可删除。
    op.add_column('conversations', sa.Column('current_plan_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_conversations_current_plan_id',
        'conversations',
        'travel_plans',
        ['current_plan_id'],
        ['id'],
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_conversations_current_plan_id', 'conversations', type_='foreignkey')
    op.drop_column('conversations', 'current_plan_id')
    # ### end Alembic commands ###
