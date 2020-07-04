import itertools
from pathlib import Path

import typer

from app import config, db
from app.files import crud as files_crud
from app.files.models import File, Mount
from app.users import crud as users_crud
from app.users.models import User

cli = typer.Typer()


@cli.command()
def createuser(
    username: str = typer.Option(..., prompt=True),
    password: str = typer.Option(
        ..., prompt=True, confirmation_prompt=True, hide_input=True,
    ),
):
    with db.SessionManager() as db_session:
        user = users_crud.create(db_session, username, password)
        file = files_crud.create_file(db_session, type=0, name="", path="")
        files_crud.create_mount(db_session, user, file)
        db_session.commit()
    typer.echo("User created successfully")


@cli.command()
def filescan():
    with db.SessionManager() as db_session:
        dirs = (
            db_session.query(Mount.file_id, User.username)
            .join(User, File)
            .filter(Mount.home.is_(True))
            .all()
        )
        root_dir = Path(config.STATIC_DIR)
        for dir_id, namespace in dirs:
            namespace = root_dir.joinpath(namespace)
            _scandir(db_session, dir_id, namespace, namespace)
        db_session.commit()


def _scandir(db_session, parent_id, dirpath, namespace):
    files = {file.name: file for file in dirpath.iterdir()}
    names_from_storage = set(files.keys())
    names_from_db = itertools.chain.from_iterable(
        db_session.query(File.name).filter(File.parent_id == parent_id).all()
    )
    if (diff := names_from_storage.difference(names_from_db)) :  # noqa: E203
        for name in diff:
            files_crud.create_file_from_path(
                db_session, files[name], parent_id=parent_id, rel_to=namespace,
            )
        db_session.flush()

    subdirs = (
        db_session.query(File.id, File.path)
        .filter(File.parent_id == parent_id, File.is_dir.is_(True))
        .all()
    )
    for dir_id, dir_path in subdirs:
        _scandir(db_session, dir_id, namespace.joinpath(dir_path), namespace)


if __name__ == "__main__":
    cli()
