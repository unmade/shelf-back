from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

from app import config, crud, db
from app.storage import storage

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models import Namespace

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
        root_dir = storage.mkdir(ns.path)
        trash_dir = storage.mkdir(Path(ns.path).joinpath(config.TRASH_FOLDER_NAME))
        root = crud.file.create(db_session, root_dir, ns.id, rel_to=ns.path)
        db_session.flush()
        crud.file.create(
            db_session, trash_dir, ns.id, rel_to=ns.path, parent_id=root.id
        )
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

    if names := names_from_storage.difference(names_from_db):
        crud.file.bulk_create(
            db_session,
            (files[name] for name in names),
            namespace_id=namespace.id,
            parent_id=parent.id,
            rel_to=namespace.path,
        )
        crud.file.inc_folder_size(
            db_session,
            namespace.id,
            path=rel_path,
            size=sum(files[name].size for name in names),
        )

    subdirs = (f for f in storage.iterdir(path) if f.is_dir())
    for dir_path in subdirs:
        _scandir(db_session, namespace, dir_path.path)


if __name__ == "__main__":
    cli()
