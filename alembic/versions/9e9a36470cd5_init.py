"""init

Revision ID: 9e9a36470cd5
Revises:
Create Date: 2022-09-01 16:55:20.372560

"""
import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision = "9e9a36470cd5"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "question",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("text", sqlmodel.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_general_ci",
    )
    op.create_table(
        "user",
        sa.Column(
            "region",
            sa.Enum("NULL", "HYPERION", "HOYOLAB", name="regionenum"),
            nullable=True,
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("yuanshen_uid", sa.Integer(), nullable=True),
        sa.Column("genshin_uid", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_general_ci",
    )
    op.create_table(
        "admin",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.user_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_general_ci",
    )
    op.create_table(
        "answer",
        sa.Column("question_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("text", sqlmodel.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["question.id"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_general_ci",
    )
    op.create_table(
        "hoyoverse_cookies",
        sa.Column("cookies", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "STATUS_SUCCESS",
                "INVALID_COOKIES",
                "TOO_MANY_REQUESTS",
                name="cookiesstatusenum",
            ),
            nullable=True,
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.user_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_general_ci",
    )
    op.create_table(
        "mihoyo_cookies",
        sa.Column("cookies", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "STATUS_SUCCESS",
                "INVALID_COOKIES",
                "TOO_MANY_REQUESTS",
                name="cookiesstatusenum",
            ),
            nullable=True,
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.user_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_general_ci",
    )
    op.create_table(
        "sign",
        sa.Column(
            "time_created",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("time_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "STATUS_SUCCESS",
                "INVALID_COOKIES",
                "ALREADY_CLAIMED",
                "GENSHIN_EXCEPTION",
                "TIMEOUT_ERROR",
                "BAD_REQUEST",
                "FORBIDDEN",
                name="signstatusenum",
            ),
            nullable=True,
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.user_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_general_ci",
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("sign")
    op.drop_table("mihoyo_cookies")
    op.drop_table("hoyoverse_cookies")
    op.drop_table("answer")
    op.drop_table("admin")
    op.drop_table("user")
    op.drop_table("question")
    # ### end Alembic commands ###
