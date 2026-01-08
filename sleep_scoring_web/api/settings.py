"""
User settings API endpoints for persisting preferences.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sleep_scoring_web.api.deps import get_current_user, get_db
from sleep_scoring_web.db.models import User, UserSettings
from sleep_scoring_web.schemas.enums import (
    ActivityDataPreference,
    AlgorithmType,
    SleepPeriodDetectorType,
)


router = APIRouter(prefix="/settings", tags=["settings"])

# Type aliases for dependency injection
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


# =============================================================================
# Pydantic Models
# =============================================================================


class UserSettingsResponse(BaseModel):
    """Response model for user settings."""

    # Study settings
    sleep_detection_rule: str | None = None
    night_start_hour: str | None = None
    night_end_hour: str | None = None

    # Data settings
    device_preset: str | None = None
    epoch_length_seconds: int | None = None
    skip_rows: int | None = None

    # Display preferences
    preferred_display_column: str | None = None
    view_mode_hours: int | None = None
    default_algorithm: str | None = None

    # Extra settings
    extra_settings: dict[str, Any] | None = None

    class Config:
        from_attributes = True


class UserSettingsUpdate(BaseModel):
    """Request model for updating user settings."""

    # Study settings
    sleep_detection_rule: str | None = None
    night_start_hour: str | None = None
    night_end_hour: str | None = None

    # Data settings
    device_preset: str | None = None
    epoch_length_seconds: int | None = None
    skip_rows: int | None = None

    # Display preferences
    preferred_display_column: str | None = None
    view_mode_hours: int | None = None
    default_algorithm: str | None = None

    # Extra settings (for flexibility)
    extra_settings: dict[str, Any] | None = None


# =============================================================================
# Default Settings
# =============================================================================


def get_default_settings() -> UserSettingsResponse:
    """Get default settings for a new user."""
    return UserSettingsResponse(
        sleep_detection_rule=SleepPeriodDetectorType.get_default(),
        night_start_hour="21:00",
        night_end_hour="09:00",
        device_preset="actigraph",
        epoch_length_seconds=60,
        skip_rows=10,
        preferred_display_column=ActivityDataPreference.AXIS_Y,
        view_mode_hours=24,
        default_algorithm=AlgorithmType.get_default(),
        extra_settings={},
    )


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("", response_model=UserSettingsResponse)
async def get_settings(
    db: DbSession,
    current_user: CurrentUser,
) -> UserSettingsResponse:
    """
    Get current user's settings.

    Returns default settings if no settings have been saved yet.
    """
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()

    if settings is None:
        return get_default_settings()

    return UserSettingsResponse(
        sleep_detection_rule=settings.sleep_detection_rule,
        night_start_hour=settings.night_start_hour,
        night_end_hour=settings.night_end_hour,
        device_preset=settings.device_preset,
        epoch_length_seconds=settings.epoch_length_seconds,
        skip_rows=settings.skip_rows,
        preferred_display_column=settings.preferred_display_column,
        view_mode_hours=settings.view_mode_hours,
        default_algorithm=settings.default_algorithm,
        extra_settings=settings.extra_settings_json,
    )


@router.put("", response_model=UserSettingsResponse)
async def update_settings(
    settings_data: UserSettingsUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> UserSettingsResponse:
    """
    Update current user's settings.

    Creates settings record if it doesn't exist.
    Only updates fields that are provided (non-None).
    """
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()

    if settings is None:
        # Create new settings record with defaults merged with provided values
        defaults = get_default_settings()
        settings = UserSettings(
            user_id=current_user.id,
            sleep_detection_rule=settings_data.sleep_detection_rule or defaults.sleep_detection_rule,
            night_start_hour=settings_data.night_start_hour or defaults.night_start_hour,
            night_end_hour=settings_data.night_end_hour or defaults.night_end_hour,
            device_preset=settings_data.device_preset or defaults.device_preset,
            epoch_length_seconds=settings_data.epoch_length_seconds or defaults.epoch_length_seconds,
            skip_rows=settings_data.skip_rows if settings_data.skip_rows is not None else defaults.skip_rows,
            preferred_display_column=settings_data.preferred_display_column or defaults.preferred_display_column,
            view_mode_hours=settings_data.view_mode_hours or defaults.view_mode_hours,
            default_algorithm=settings_data.default_algorithm or defaults.default_algorithm,
            extra_settings_json=settings_data.extra_settings or defaults.extra_settings,
        )
        db.add(settings)
    else:
        # Update existing settings (only non-None values)
        update_data = settings_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                if field == "extra_settings":
                    settings.extra_settings_json = value
                else:
                    setattr(settings, field, value)

    await db.commit()
    await db.refresh(settings)

    return UserSettingsResponse(
        sleep_detection_rule=settings.sleep_detection_rule,
        night_start_hour=settings.night_start_hour,
        night_end_hour=settings.night_end_hour,
        device_preset=settings.device_preset,
        epoch_length_seconds=settings.epoch_length_seconds,
        skip_rows=settings.skip_rows,
        preferred_display_column=settings.preferred_display_column,
        view_mode_hours=settings.view_mode_hours,
        default_algorithm=settings.default_algorithm,
        extra_settings=settings.extra_settings_json,
    )


@router.delete("", status_code=204)
async def reset_settings(
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """
    Reset user settings to defaults.

    Deletes the settings record, so next GET will return defaults.
    """
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()

    if settings:
        await db.delete(settings)
        await db.commit()
