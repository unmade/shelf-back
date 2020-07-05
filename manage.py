from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

from app import config, crud, db

if TYPE_CHECKING:
    from app.models.namespace import Namespace

cli = typer.Typer()


@cli.command()
def createuser(
    username: str = typer.Option(..., prompt=True),
    password: str = typer.Option(
        ..., prompt=True, confirmation_prompt=True, hide_input=True,
    ),
):
    with db.SessionManager() as db_session:
        user = crud.user.create(db_session, username, password)
        crud.namespace.create(db_session, owner_id=user.id)
        db_session.commit()
    typer.echo("User created successfully")


@cli.command()
def filescan():
    with db.SessionManager() as db_session:
        namespaces = crud.namespace.all(db_session)
        for namespace in namespaces:
            path = config.STATIC_DIR.joinpath(namespace.name)
            _scandir(db_session, namespace, path)
        db_session.commit()


def _scandir(db_session, namespace: Namespace, path: Path):
    rel_path = path.relative_to(config.STATIC_DIR.joinpath(namespace.name))

    files = {file.name: file for file in path.iterdir()}
    files_db = crud.file.ls(db_session, namespace.id, rel_path)

    names_from_storage = set(files.keys())
    names_from_db = (file.name for file in files_db)

    if diff := names_from_storage.difference(names_from_db):
        parent = crud.file.get(db_session, namespace.id, path=rel_path)
        parent_id = parent.id if parent else None
        for name in diff:
            crud.file.create_from_path(
                db_session,
                files[name],
                namespace_id=namespace.id,
                parent_id=parent_id,
                rel_to=config.STATIC_DIR.joinpath(namespace.name),
            )
        db_session.flush()

    subdirs = [p for p in path.iterdir() if p.is_dir()]
    for dir_path in subdirs:
        _scandir(db_session, namespace, dir_path)


if __name__ == "__main__":
    cli()
