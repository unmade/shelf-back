from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from ..main import ARQContext


async def process_blob_content(ctx: ARQContext, blob_id: UUID) -> None:
    blob_content_processor = ctx["usecases"].blob_content_processor
    await blob_content_processor.process(blob_id)
