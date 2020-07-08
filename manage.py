from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

from app import crud, db
from app.storage import storage

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
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
        ns = crud.namespace.create(db_session, username, owner_id=user.id)
        storage_file = storage.mkdir(ns.path)
        crud.file.create(db_session, storage_file, ns.id, rel_to=ns.path)
        db_session.commit()
    typer.echo("User created successfully")


@cli.command()
def filescan():
    with db.SessionManager() as db_session:
        namespaces = crud.namespace.all(db_session)
        for namespace in namespaces:
            _scandir(db_session, namespace, Path(namespace.path))
        db_session.commit()


def _scandir(db_session: Session, namespace: Namespace, path: Path):
    files = {f.name: f for f in storage.iterdir(path)}

    rel_path = str(path.relative_to(namespace.path))
    parent = crud.file.get_folder(db_session, namespace.id, path=rel_path)
    assert parent is not None
    files_db = crud.file.list_folder_by_id(db_session, parent.id)

    names_from_storage = set(files.keys())
    names_from_db = (f.name for f in files_db)

    if names_from_storage.difference(names_from_db):
        crud.file.bulk_create(
            db_session,
            files.values(),
            namespace_id=namespace.id,
            parent_id=parent.id,
            rel_to=namespace.path,
        )
        crud.file.inc_folder_size(
            db_session,
            namespace.id,
            path=rel_path,
            size=sum(f.size for f in files.values() if not f.is_dir()),
        )

    subdirs = (f for f in storage.iterdir(path) if f.is_dir())
    for dir_path in subdirs:
        _scandir(db_session, namespace, dir_path.path)


if __name__ == "__main__":
    cli()
