from __future__ import annotations

import asyncio
from pathlib import Path

import typer
import uvloop

from app import actions, crud, db

cli = typer.Typer()

uvloop.install()


@cli.command()
def createsuperuser(
    username: str = typer.Option(
        ...,
        help="username",
        envvar="SHELF_SUPERUSER_USERNAME",
        prompt=True
    ),
    password: str = typer.Option(
        ...,
        help="password",
        envvar="SHELF_SUPERUSER_PASSWORD",
        prompt=True,
        confirmation_prompt=True,
        hide_input=True,
    ),
) -> None:
    """Create a new super user with namespace, home and trash directories."""
    async def _createuser(username: str, password: str):
        async with db.create_client() as conn:
            await actions.create_account(conn, username, password, superuser=True)

    asyncio.run(_createuser(username, password))
    typer.echo("User created successfully.")


@cli.command()
def reconcile(namespace: str) -> None:
    """Reconcile storage and database for a given namespace."""
    async def _reconcile():
        async with db.create_client(max_concurrency=None) as db_client:
            ns = await crud.namespace.get(db_client, namespace)
            await actions.reconcile(db_client, ns)

    asyncio.run(_reconcile())


@cli.command()
def migrate(schema: Path) -> None:
    """Apply target schema to a database."""
    async def run_migration(schema: str) -> None:
        async with db.create_client() as conn:
            await db.migrate(conn, schema)

    with open(schema.expanduser().resolve(), 'r') as f:
        schema_declaration = f.read()

    asyncio.run(run_migration(schema_declaration))


if __name__ == "__main__":
    cli()
