from __future__ import annotations

import functools

import click
import uvloop

from app.app.users.domain import User
from app.config import config
from app.infrastructure.context import AppContext


def async_to_sync(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return uvloop.run(func(*args, **kwargs))
    return wrapper


@click.group()
def cli():
    pass


@cli.command()
@click.option(
    "--username",
    envvar="SHELF_SUPERUSER_USERNAME",
    type=str,
    prompt=True,
    help="username",
    required=True,
)
@click.option(
    "--password",
    envvar="SHELF_SUPERUSER_PASSWORD",
    type=str,
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="password",
    required=True,
)
@click.option(
    "--exist-ok",
    is_flag=True,
    default=False,
    help="Whether to raise and exception if a user already exists.",
)
@async_to_sync
async def createsuperuser(username, password, exist_ok):
    """Create a new super user with namespace, home and trash directories."""
    config.database = config.database.with_pool_size(1)
    async with AppContext(config) as ctx:
        try:
            await ctx.usecases.user.create_superuser(username, password)
        except User.AlreadyExists:
            if not exist_ok:
                raise
            click.echo("User already exists, skipping...")
        else:
            click.echo("User created successfully.")


@cli.command()
@click.argument("namespace", type=str)
@async_to_sync
async def reindex(namespace: str) -> None:
    """Reindex files in the storage for a given namespace."""
    config.database = config.database.with_pool_size(1)
    async with AppContext(config) as ctx:
        await ctx.usecases.namespace.reindex(namespace)


@cli.command()
@click.argument("namespace", type=str)
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
