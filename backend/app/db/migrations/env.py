from alembic import context
from sqlalchemy import create_engine, schema

import app.db.models  # noqa: F401  (registers every table)
from app.core.config import get_settings
from app.db.base import Base

target_metadata = Base.metadata
SCHEMAS = {"nexus", "staging", "legacy_ilms"}


def include_name(name, type_, parent_names):  # noqa: ANN001, ANN201
    if type_ == "schema":
        return name in SCHEMAS
    return True


def run_migrations_online() -> None:
    # Migrations always run as the schema owner, never as the application role.
    engine = create_engine(get_settings().owner_database_url)
    with engine.connect() as connection:
        connection.execute(schema.CreateSchema("nexus", if_not_exists=True))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
            version_table_schema="nexus",
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
