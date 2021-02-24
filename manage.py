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
    """Create a new user with namespace, home and trash directories."""
    async def _createuser(username: str, password: str):
        conn = await edgedb.async_connect(dsn=config.EDGEDB_DSN)
        try:
            await actions.create_account(conn, username, password)
        finally:
            await conn.aclose()

    asyncio.run(_createuser(username, password))
    typer.echo("User created successfully.")


@cli.command()
def reconcile(namespace: str) -> None:
    """Reconcile storage and database for all namespaces."""
    async def _reconcile():
        conn = await edgedb.async_connect(dsn=config.EDGEDB_DSN)
        try:
            ns = await crud.namespace.get(conn, namespace)
            await actions.reconcile(conn, ns, ".")
        finally:
            await conn.aclose()

    asyncio.run(_reconcile())


@cli.command()
def migrate(schema: Path) -> None:
    """Apply target schema to a database."""
    async def run_migration(schema: str) -> None:
        conn = await edgedb.async_connect(dsn=config.EDGEDB_DSN)
        try:
            await db.migrate(conn, schema)
        finally:
            await conn.aclose()

    with open(schema.expanduser().resolve(), 'r') as f:
        schema_declaration = f.read()

    asyncio.run(run_migration(schema_declaration))


if __name__ == "__main__":
    cli()
