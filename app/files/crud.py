from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from sqlalchemy.orm import Session

from app.files.models import File, Mount


def create_file(db_session, type, name, path):
    file = File(type=type, name=name, path=path, size=0, mtime=0, is_dir=True,)

    db_session.add(file)
    db_session.flush()

    return file


def create_file_from_path(
    db_session: Session,
    path: Path,
    parent_id: Optional[int] = None,
    rel_to: Union[None, str, Path] = None,
) -> File:
    stat = path.lstat()
    file = File(
        parent_id=parent_id,
        type=0 if path.is_dir() else 1,
        name=path.name,
        path=str(path.relative_to(rel_to) if rel_to else path),
        size=stat.st_size,
        mtime=stat.st_mtime,
        is_dir=path.is_dir(),
    )
    db_session.add(file)

    return file


def create_mount(db_session, user, file):
    mount = Mount(user_id=user.id, file_id=file.id, home=file.name == "",)

    db_session.add(mount)
    db_session.flush()

    return mount


def ls_root(db_session, user, path):
    home = (
        db_session.query(Mount)
        .filter(Mount.user_id == user.id, Mount.home.is_(True))
        .first()
    )
    if path:
        parent_id = (
            db_session.query(File.id)
            .filter(File.parent_id == home.id, File.path == path)
            .first()[0]
        )
        return db_session.query(File).filter(File.parent_id == parent_id).all()
    return db_session.query(File).filter(File.parent_id == home.id).all()
