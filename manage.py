from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from app import crud, db
from app.storage import storage

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
            _scandir(db_session, namespace)
        db_session.commit()


def _scandir(db_session, namespace: Namespace, path: str = None):
    files = {f.name: f for f in storage.ls(namespace.name, path)}
    files_db = crud.file.ls(db_session, namespace.id, path)

    names_from_storage = set(files.keys())
    names_from_db = (f.name for f in files_db)

    if diff := names_from_storage.difference(names_from_db):
        parent = crud.file.get(db_session, namespace.id, path=path)
        parent_id = parent.id if parent else None
        for name in diff:
            crud.file.create(
                db_session, files[name], namespace_id=namespace.id, parent_id=parent_id,
            )
        db_session.flush()

    subdirs = (f for f in storage.ls(namespace.name, path) if f.is_dir())
    for dir_path in subdirs:
        _scandir(db_session, namespace, dir_path.path)


if __name__ == "__main__":
    cli()
