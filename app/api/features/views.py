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
                name=FeatureName.max_file_size_to_thumbnail,
                value=config.features.max_file_size_to_thumbnail,
            ),
            Feature(
                name=FeatureName.photos_library_path,
                value=config.features.photos_library_path,
            ),
            Feature(
                name=FeatureName.sign_up_enabled,
                value=config.features.sign_up_enabled,
            ),
            Feature(
                name=FeatureName.shared_links_enabled,
                value=config.features.shared_links_enabled,
            ),
            Feature(
                name=FeatureName.upload_file_max_size,
                value=config.features.upload_file_max_size,
            ),
            Feature(
                name=FeatureName.verification_required,
                value=config.features.verification_required,
            ),
        ],
    )
