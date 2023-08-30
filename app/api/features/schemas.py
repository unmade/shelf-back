from __future__ import annotations

import enum

from pydantic import BaseModel


class FeatureName(enum.StrEnum):
    max_file_size_to_thumbnail = "max_file_size_to_thumbnail"
    sign_up_disabled = "sign_up_disabled"
    upload_file_max_size = "upload_file_max_size"


class Feature(BaseModel):
    name: FeatureName
    value: int | bool


class ListFeatureResponse(BaseModel):
    items: list[Feature]
