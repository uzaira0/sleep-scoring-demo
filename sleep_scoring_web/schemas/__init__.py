"""
Pydantic schemas for the Sleep Scoring Web API.

This package contains all Pydantic models that serve as the
single source of truth for both API validation and OpenAPI generation.
"""

from .enums import (
    AlgorithmType,
    FileStatus,
    MarkerCategory,
    MarkerType,
    NonwearAlgorithm,
    SleepPeriodDetectorType,
    UserRole,
    VerificationStatus,
)
from .models import (
    ActivityDataColumnar,
    ActivityDataResponse,
    FileInfo,
    FileListResponse,
    FileUploadResponse,
    ManualNonwearPeriod,
    MarkerResponse,
    MarkerUpdateRequest,
    SleepMetrics,
    SleepPeriod,
    UserCreate,
    UserRead,
    UserUpdate,
)

__all__ = [
    # Models
    "ActivityDataColumnar",
    "ActivityDataResponse",
    # Enums
    "AlgorithmType",
    "FileInfo",
    "FileListResponse",
    "FileStatus",
    "FileUploadResponse",
    "ManualNonwearPeriod",
    "MarkerCategory",
    "MarkerResponse",
    "MarkerType",
    "MarkerUpdateRequest",
    "NonwearAlgorithm",
    "SleepMetrics",
    "SleepPeriod",
    "SleepPeriodDetectorType",
    "UserCreate",
    "UserRead",
    "UserRole",
    "UserUpdate",
    "VerificationStatus",
]
