from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb

from app.app.files.domain import MountPoint, Path
from app.app.files.repositories.mount import IMountRepository

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath
    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext

__all__ = ["MountRepository"]


def _from_db(ns_path, obj) -> MountPoint:
    shared_file = obj.member.share.file
    return MountPoint(
        display_name=obj.display_name,
        source=MountPoint.Source(
            ns_path=shared_file.namespace.path,
            path=shared_file.path,
        ),
        folder=MountPoint.ContainingFolder(
            ns_path=ns_path,
            path=obj.parent.path,
        ),
    )


class MountRepository(IMountRepository):
    def __init__(self, db_context: EdgeDBContext):
        self.db_context = db_context

    @property
    def conn(self) -> EdgeDBAnyConn:
        return self.db_context.get()

    async def get_closest(self, ns_path: AnyPath, path: AnyPath) -> MountPoint:
        query = """
            WITH
                namespace := (SELECT Namespace FILTER .path = <str>$ns_path),
            SELECT (
                SELECT
                    ShareMountPoint
                FILTER
                    .parent.path IN {array_unpack(<array<str>>$parents)}
                    AND .parent.namespace = namespace
            ) {
                display_name,
                parent: {
                    path
                },
                member: {
                    share: {
                        file: {
                            path,
                            namespace: {
                                path
                            },
                        },
                    },
                },
            }
            FILTER
                .display_name in {array_unpack(<array<str>>$names)}
            ORDER BY
                .parent.path DESC
            LIMIT 1
        """

        path = Path(path)
        parents = list(path.parents)

        try:
            obj = await self.conn.query_required_single(
                query,
                ns_path=str(ns_path),
                parents=[str(p) for p in parents],
                names=[path.name] + [p.name for p in parents],
            )
        except edgedb.NoDataError as exc:
            raise MountPoint.NotFound() from exc

        return _from_db(ns_path, obj)
