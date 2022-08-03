from __future__ import annotations

import asyncio
from pathlib import Path

import typer
import uvloop

from app import actions, crud, db, errors

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
    exist_ok: bool = typer.Option(
        False,
        "--exist-ok",
        help="""
            If set to False and a user with a given username already exists,
            then raise an exception
        """,
    ),
) -> None:
    """Create a new super user with namespace, home and trash directories."""
    async def _createuser(username: str, password: str):
        async with db.create_client() as conn:
            try:
                await actions.create_account(conn, username, password, superuser=True)
            except errors.UserAlreadyExists:
                if not exist_ok:
                    raise
                typer.echo("User already exists, skipping...")
            else:
                typer.echo("User created successfully.")

    asyncio.run(_createuser(username, password))


@cli.command()
def reindex(namespace: str) -> None:
    """Reindex files in the storage for a given namespace."""
    async def _reindex():
        async with db.create_client(max_concurrency=None) as db_client:
            ns = await crud.namespace.get(db_client, namespace)
            await actions.reindex(db_client, ns)

    asyncio.run(_reindex())


@cli.command()
def reindex_content(namespace: str) -> None:
    """
    Restore additional information about files, such as file fingerprints and content
    metadata.
    """
    async def _reindex_content():
        async with db.create_client(max_concurrency=None) as db_client:
            ns = await crud.namespace.get(db_client, namespace)
            await actions.reindex_files_content(db_client, ns)

    asyncio.run(_reindex_content())


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
