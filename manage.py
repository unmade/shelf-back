from __future__ import annotations

import asyncio

import typer
import uvloop

from app import config
from app.app.users.domain import User
from app.infrastructure.database.edgedb.db import EdgeDBDatabase
from app.infrastructure.provider import Provider
from app.infrastructure.storage import FileSystemStorage, S3Storage

cli = typer.Typer()

uvloop.install()


def _create_database():
    return EdgeDBDatabase(
        dsn=config.DATABASE_DSN,
        max_concurrency=1,
        tls_ca_file=config.DATABASE_TLS_CA_FILE,
        tls_security=config.DATABASE_TLS_SECURITY,
    )


def _create_storage():
    if config.STORAGE_TYPE == config.StorageType.s3:
        return S3Storage(
            location=config.STORAGE_LOCATION,
        )
    return FileSystemStorage(location=config.STORAGE_LOCATION)


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
        storage = _create_storage()
        async with _create_database() as database:
            provider = Provider(database=database, storage=storage)
            services = provider.services
            try:
                user = await services.user.create(username, password, superuser=True)
            except User.AlreadyExists:
                if not exist_ok:
                    raise
                typer.echo("User already exists, skipping...")
            else:
                await services.namespace.create(user.username, owner_id=user.id)
                typer.echo("User created successfully.")

    print("error")
    asyncio.run(_createuser(username, password))


@cli.command()
def reindex(namespace: str) -> None:
    """Reindex files in the storage for a given namespace."""
    async def _reindex():
        storage = _create_storage()
        async with _create_database() as database:
            provider = Provider(database=database, storage=storage)
            usecases = provider.usecases
            await usecases.namespace.reindex(namespace)

    asyncio.run(_reindex())


@cli.command()
def reindex_content(namespace: str) -> None:
    """
    Restore additional information about files, such as file fingerprints and content
    metadata.
    """
    async def _reindex_content():
        storage = _create_storage()
        async with _create_database() as database:
            provider = Provider(database=database, storage=storage)
            usecases = provider.usecases
            await usecases.namespace.reindex_contents(namespace)

    asyncio.run(_reindex_content())


@cli.command()
def migrate() -> None:
    """Apply target schema to a database."""
    async def run_migration() -> None:
        async with _create_database() as database:
            await database.migrate()

    asyncio.run(run_migration())


if __name__ == "__main__":
    cli()
