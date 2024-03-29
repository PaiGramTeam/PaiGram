"""channel_alias

Revision ID: cb37027ecae8
Revises: 89dcb9109475
Create Date: 2024-03-10 17:08:14.167818

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "cb37027ecae8"
down_revision = "89dcb9109475"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "channel_alias",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chat_id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_general_ci",
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("channel_alias")
    # ### end Alembic commands ###
