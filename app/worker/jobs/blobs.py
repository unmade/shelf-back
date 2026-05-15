from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from ..main import ARQContext


async def process_blob_content(ctx: ARQContext, blob_id: UUID) -> None:
    blob_content_processor = ctx["usecases"].blob_content_processor
    await blob_content_processor.process(blob_id)


async def process_blob_jobs(ctx: ARQContext, ids: Sequence[UUID]) -> None:
    blob_service = ctx["usecases"].blob
    await blob_service.process_blob_jobs(ids)
