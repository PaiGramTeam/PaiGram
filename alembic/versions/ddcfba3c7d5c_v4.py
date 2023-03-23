"""v4

Revision ID: ddcfba3c7d5c
Revises: 9e9a36470cd5
Create Date: 2023-02-11 17:07:18.170175

"""
import json
import logging
from base64 import b64decode

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy import text
from sqlalchemy.exc import NoSuchTableError

# revision identifiers, used by Alembic.
revision = "ddcfba3c7d5c"
down_revision = "9e9a36470cd5"
branch_labels = None
depends_on = None

old_cookies_database_name1 = b64decode("bWlob3lvX2Nvb2tpZXM=").decode()
old_cookies_database_name2 = b64decode("aG95b3ZlcnNlX2Nvb2tpZXM=").decode()
logger = logging.getLogger(__name__)


def upgrade() -> None:
    connection = op.get_bind()
    # ### commands auto generated by Alembic - please adjust! ###
    cookies_table = op.create_table(
        "cookies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
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
        sa.Column(
            "region",
            sa.Enum("NULL", "HYPERION", "HOYOLAB", name="regionenum"),
            nullable=True,
        ),
        sa.Column("is_share", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("index_user_account", "user_id", "account_id", unique=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_general_ci",
    )
    for old_cookies_database_name in (old_cookies_database_name1, old_cookies_database_name2):
        try:
            statement = f"SELECT * FROM {old_cookies_database_name};"  # skipcq: BAN-B608
            old_cookies_table_data = connection.execute(text(statement))
        except NoSuchTableError:
            logger.warning("Table '%s' doesn't exist", old_cookies_database_name)
            continue
        if old_cookies_table_data is None:
            logger.warning("Old Cookies Database is None")
            continue
        for row in old_cookies_table_data:
            try:
                user_id = row["user_id"]
                status = row["status"]
                cookies_row = row["cookies"]
                cookies_data = json.loads(cookies_row)
                account_id = cookies_data.get("account_id")
                if account_id is None:  # Cleaning Data 清洗数据
                    account_id = cookies_data.get("ltuid")
                else:
                    account_mid_v2 = cookies_data.get("account_mid_v2")
                    if account_mid_v2 is not None:
                        cookies_data.pop("account_id")
                        cookies_data.setdefault("account_uid_v2", account_id)
                if old_cookies_database_name == old_cookies_database_name1:
                    region = "HYPERION"
                else:
                    region = "HOYOLAB"
                if account_id is None:
                    logger.warning("Can not get user account_id, user_id :%s", user_id)
                    continue
                insert = cookies_table.insert().values(
                    user_id=int(user_id),
                    account_id=int(account_id),
                    status=status,
                    data=cookies_data,
                    region=region,
                    is_share=True,
                )
                with op.get_context().autocommit_block():
                    connection.execute(insert)
            except Exception as exc:  # pylint: disable=W0703
                logger.error(
                    "Process %s->cookies Exception", old_cookies_database_name, exc_info=exc
                )  # pylint: disable=W0703
    players_table = op.create_table(
        "players",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=True),
        sa.Column("player_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "region",
            sa.Enum("NULL", "HYPERION", "HOYOLAB", name="regionenum"),
            nullable=True,
        ),
        sa.Column("is_chosen", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("index_user_account_player", "user_id", "account_id", "player_id", unique=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_general_ci",
    )

    try:
        statement = "SELECT * FROM user;"
        old_user_table_data = connection.execute(text(statement))
    except NoSuchTableError:
        logger.warning("Table 'user' doesn't exist")
        return  # should not happen
    if old_user_table_data is not None:
        for row in old_user_table_data:
            try:
                user_id = row["user_id"]
                y_uid = row["yuanshen_uid"]
                g_uid = row["genshin_uid"]
                region = row["region"]
                if y_uid:
                    account_id = None
                    cookies_row = connection.execute(
                        cookies_table.select()
                        .where(cookies_table.c.user_id == user_id)
                        .where(cookies_table.c.region == "HYPERION")
                    ).first()
                    if cookies_row is not None:
                        account_id = cookies_row["account_id"]
                    insert = players_table.insert().values(
                        user_id=int(user_id),
                        player_id=int(y_uid),
                        is_chosen=(region == "HYPERION"),
                        region="HYPERION",
                        account_id=account_id,
                    )
                    with op.get_context().autocommit_block():
                        connection.execute(insert)
                if g_uid:
                    account_id = None
                    cookies_row = connection.execute(
                        cookies_table.select()
                        .where(cookies_table.c.user_id == user_id)
                        .where(cookies_table.c.region == "HOYOLAB")
                    ).first()
                    if cookies_row is not None:
                        account_id = cookies_row["account_id"]
                    insert = players_table.insert().values(
                        user_id=int(user_id),
                        player_id=int(g_uid),
                        is_chosen=(region == "HOYOLAB"),
                        region="HOYOLAB",
                        account_id=account_id,
                    )
                    with op.get_context().autocommit_block():
                        connection.execute(insert)
            except Exception as exc:  # pylint: disable=W0703
                logger.error("Process user->player Exception", exc_info=exc)
    else:
        logger.warning("Old User Database is None")

    users_table = op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False, primary_key=True),
        sa.Column(
            "permissions",
            sa.Enum("OWNER", "ADMIN", "PUBLIC", name="permissionsenum"),
            nullable=True,
        ),
        sa.Column("locale", sqlmodel.AutoString(), nullable=True),
        sa.Column("is_banned", sa.BigInteger(), nullable=True),
        sa.Column("ban_end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ban_start_time", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_general_ci",
    )

    try:
        statement = "SELECT * FROM admin;"
        old_user_table_data = connection.execute(text(statement))
    except NoSuchTableError:
        logger.warning("Table 'admin' doesn't exist")
        return  # should not happen
    if old_user_table_data is not None:
        for row in old_user_table_data:
            try:
                user_id = row["user_id"]
                insert = users_table.insert().values(
                    user_id=int(user_id),
                    permissions="ADMIN",
                )
                with op.get_context().autocommit_block():
                    connection.execute(insert)
            except Exception as exc:  # pylint: disable=W0703
                logger.error("Process admin->users Exception", exc_info=exc)
    else:
        logger.warning("Old User Database is None")

    op.create_table(
        "players_info",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("player_id", sa.BigInteger(), nullable=False),
        sa.Column("nickname", sqlmodel.AutoString(length=128), nullable=True),
        sa.Column("signature", sqlmodel.AutoString(length=255), nullable=True),
        sa.Column("hand_image", sa.Integer(), nullable=True),
        sa.Column("name_card", sa.Integer(), nullable=True),
        sa.Column("extra_data", sa.VARCHAR(length=512), nullable=True),
        sa.Column(
            "create_time",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("last_save_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_update", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("index_user_player", "user_id", "player_id", unique=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_general_ci",
    )

    op.drop_table(old_cookies_database_name1)
    op.drop_table(old_cookies_database_name2)
    op.drop_table("admin")
    context = op.get_context()
    if context.dialect.name == "sqlite":
        logger.warning(
            "The SQLite dialect does not support ALTER constraint operations, "
            "so you need to manually remove the constraint condition of `sign_ibfk_1` and delete the user table."
        )
        return
    op.drop_constraint("sign_ibfk_1", "sign", type_="foreignkey")
    op.drop_index("user_id", table_name="sign")
    op.drop_table("user")
    # ### end Alembic commands ###


def downgrade() -> None:
    op.create_table(
        "user",
        sa.Column("region", sa.Enum("NULL", "HYPERION", "HOYOLAB", name="regionenum"), nullable=True),
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("yuanshen_uid", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column("genshin_uid", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.PrimaryKeyConstraint("id"),
        mysql_collate="utf8mb4_general_ci",
        mysql_default_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_index("user_id", "user", ["user_id"], unique=False)
    op.create_table(
        "admin",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.user_id"], name="admin_ibfk_1"),
        sa.PrimaryKeyConstraint("id"),
        mysql_collate="utf8mb4_general_ci",
        mysql_default_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        old_cookies_database_name1,
        sa.Column("cookies", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("STATUS_SUCCESS", "INVALID_COOKIES", "TOO_MANY_REQUESTS", name="cookiesstatusenum"),
            nullable=True,
        ),
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.user_id"], name="mihoyo_cookies_ibfk_1"),
        sa.PrimaryKeyConstraint("id"),
        mysql_collate="utf8mb4_general_ci",
        mysql_default_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_table(
        old_cookies_database_name2,
        sa.Column("cookies", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("STATUS_SUCCESS", "INVALID_COOKIES", "TOO_MANY_REQUESTS", name="cookiesstatusenum"),
            nullable=True,
        ),
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.user_id"], name="hoyoverse_cookies_ibfk_1"),
        sa.PrimaryKeyConstraint("id"),
        mysql_collate="utf8mb4_general_ci",
        mysql_default_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_foreign_key("sign_ibfk_1", "sign", "user", ["user_id"], ["user_id"])
    op.create_index("user_id", "sign", ["user_id"], unique=False)
    op.drop_table("users")
    op.drop_table("players")
    op.drop_table("cookies")
    op.drop_table("players_info")
    # ### end Alembic commands ###
