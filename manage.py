from __future__ import annotations

import asyncio
from pathlib import Path

import edgedb
import typer

from app import actions, config, crud, db

cli = typer.Typer()


@cli.command()
def createuser(
    username: str = typer.Option(..., prompt=True),
    password: str = typer.Option(
        ..., prompt=True, confirmation_prompt=True, hide_input=True,
    ),
) -> None:
    """Creates a new user, namespace, home and trash directories."""
    async def _createuser(username: str, password: str):
        conn = await edgedb.async_connect(dsn=config.EDGEDB_DSN)
        await actions.create_account(conn, username, password)
        await conn.aclose()

    asyncio.run(_createuser(username, password))
    typer.echo("User created successfully.")


@cli.command()
def reconcile() -> None:
    """Reconciles storage and database for all namespaces."""
    with db.SessionManager() as db_session:
        namespaces = crud.namespace.all(db_session)
        for namespace in namespaces:
            actions.reconcile(db_session, namespace, ".")
        db_session.commit()


@cli.command()
def migrate(schema: Path) -> None:
    """Apply target schema to a database."""
    async def run_migration(schema: str) -> None:
        conn = await edgedb.async_connect(dsn=config.EDGEDB_DSN)
        await db.migrate(conn, schema)
        await conn.aclose()

    with open(schema.resolve(), 'r') as f:
        schema_declaration = f.read()

    asyncio.run(run_migration(schema_declaration))


if __name__ == "__main__":
    cli()
