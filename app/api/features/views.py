from __future__ import annotations

from fastapi import APIRouter

from app.config import config

from .schemas import Feature, FeatureName, ListFeatureResponse

router = APIRouter()


@router.get("/list")
async def list_all() -> ListFeatureResponse:
    """Return a list of available features."""
    return ListFeatureResponse(
        items=[
            Feature(
                name=FeatureName.sign_up_disabled,
                value=config.features.sign_up_disabled,
            ),
            Feature(
                name=FeatureName.upload_file_max_size,
                value=config.features.upload_file_max_size,
            ),
        ],
    )
