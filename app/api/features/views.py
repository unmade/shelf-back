from __future__ import annotations

from fastapi import APIRouter

from app import config

from .schemas import Feature, FeatureName, ListFeatureResponse

router = APIRouter()


@router.get("/list", response_model=ListFeatureResponse)
async def list_all():
    """Return a list of available features."""
    return ListFeatureResponse.construct(
        items=[
            Feature.construct(
                name=FeatureName.sign_up_disabled,  # type: ignore[arg-type]
                value=config.FEATURES_SIGN_UP_DISABLED,
            ),
            Feature.construct(
                name=FeatureName.upload_file_max_size,  # type: ignore[arg-type]
                value=config.FEATURES_UPLOAD_FILE_MAX_SIZE,
            ),
        ],
    )
