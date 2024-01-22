from __future__ import annotations

import functools

import typer
import uvloop

from app.app.users.domain import User
from app.config import config
from app.infrastructure.context import AppContext

cli = typer.Typer()


def async_to_sync(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return uvloop.run(func(*args, **kwargs))
    return wrapper


@cli.command()
@async_to_sync
async def createsuperuser(
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
    config.database = config.database.with_pool_size(1)
    async with AppContext(config) as ctx:
        try:
            await ctx.usecases.user.create_superuser(username, password)
        except User.AlreadyExists:
            if not exist_ok:
                raise
            typer.echo("User already exists, skipping...")
        else:
            typer.echo("User created successfully.")


@cli.command()
@async_to_sync
async def reindex(namespace: str) -> None:
    """Reindex files in the storage for a given namespace."""
    config.database = config.database.with_pool_size(1)
    async with AppContext(config) as ctx:
        await ctx.usecases.namespace.reindex(namespace)


@cli.command()
@async_to_sync
async def reindex_content(namespace: str) -> None:
    """
    Restore additional information about files, such as file fingerprints and content
    metadata.
    """
    config.database = config.database.with_pool_size(1)
    async with AppContext(config) as ctx:
        await ctx.usecases.namespace.reindex_contents(namespace)


@cli.command()
@async_to_sync
async def migrate() -> None:
    """Apply target schema to a database."""
    config.database = config.database.with_pool_size(1)
    async with AppContext(config) as ctx:
        await ctx._infra.database.migrate()


if __name__ == "__main__":
    cli()
