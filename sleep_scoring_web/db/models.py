"""
SQLAlchemy ORM models for Sleep Scoring Web.

Database schema matches the plan document with tables for:
- Users (authentication and roles)
- Files (uploaded activity data files)
- RawActivityData (epoch-level activity data)
- Markers (sleep and nonwear markers)
- UserAnnotations (for multi-user consensus)
- SleepMetrics (calculated metrics per period)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class User(Base):
    """User model for authentication."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="annotator")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    uploaded_files: Mapped[list[File]] = relationship("File", back_populates="uploaded_by")
    annotations: Mapped[list[UserAnnotation]] = relationship("UserAnnotation", back_populates="user")


class File(Base):
    """Uploaded activity data file."""

    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    original_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_type: Mapped[str] = mapped_column(String(50), default="csv")
    participant_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    uploaded_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    uploaded_by: Mapped[User | None] = relationship("User", back_populates="uploaded_files")
    activity_data: Mapped[list[RawActivityData]] = relationship("RawActivityData", back_populates="file", cascade="all, delete-orphan")
    markers: Mapped[list[Marker]] = relationship("Marker", back_populates="file", cascade="all, delete-orphan")
    annotations: Mapped[list[UserAnnotation]] = relationship("UserAnnotation", back_populates="file", cascade="all, delete-orphan")
    sleep_metrics: Mapped[list[SleepMetric]] = relationship("SleepMetric", back_populates="file", cascade="all, delete-orphan")


class RawActivityData(Base):
    """Raw activity data per epoch."""

    __tablename__ = "raw_activity_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    epoch_index: Mapped[int] = mapped_column(Integer, nullable=False)
    axis_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    axis_y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    axis_z: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vector_magnitude: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    file: Mapped[File] = relationship("File", back_populates="activity_data")

    __table_args__ = (
        Index("ix_raw_activity_data_file_timestamp", "file_id", "timestamp"),
        Index("ix_raw_activity_data_file_epoch", "file_id", "epoch_index"),
    )


class Marker(Base):
    """Sleep or nonwear marker."""

    __tablename__ = "markers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    analysis_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    marker_category: Mapped[str] = mapped_column(String(50), nullable=False)  # sleep, nonwear
    marker_type: Mapped[str] = mapped_column(String(50), nullable=False)  # MAIN_SLEEP, NAP, etc.
    start_timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    end_timestamp: Mapped[float | None] = mapped_column(Float, nullable=True)
    period_index: Mapped[int] = mapped_column(Integer, default=1)

    created_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    file: Mapped[File] = relationship("File", back_populates="markers")

    __table_args__ = (Index("ix_markers_file_date", "file_id", "analysis_date"),)


class UserAnnotation(Base):
    """User annotation for consensus system."""

    __tablename__ = "user_annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    analysis_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Marker data stored as JSON for flexibility
    sleep_markers_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    nonwear_markers_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)

    algorithm_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_spent_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft")  # draft, submitted

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    file: Mapped[File] = relationship("File", back_populates="annotations")
    user: Mapped[User] = relationship("User", back_populates="annotations")

    __table_args__ = (Index("ix_user_annotations_file_date_user", "file_id", "analysis_date", "user_id", unique=True),)


class SleepMetric(Base):
    """
    Calculated Tudor-Locke sleep metrics per period.

    Reference:
        Tudor-Locke C, et al. (2014). Fully automated waist-worn accelerometer algorithm
        for detecting children's sleep-period time. Applied Physiology, Nutrition, and
        Metabolism, 39(1):53-57.
    """

    __tablename__ = "sleep_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    analysis_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    period_index: Mapped[int] = mapped_column(Integer, default=0)

    # Period boundaries (timestamps in seconds, datetimes for display)
    onset_timestamp: Mapped[float | None] = mapped_column(Float, nullable=True)
    offset_timestamp: Mapped[float | None] = mapped_column(Float, nullable=True)
    in_bed_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    out_bed_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sleep_onset: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sleep_offset: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Duration metrics (minutes)
    time_in_bed_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_sleep_time_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_onset_latency_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    waso_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Awakening metrics
    number_of_awakenings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    average_awakening_length_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Quality indices (percentages 0-100)
    sleep_efficiency: Mapped[float | None] = mapped_column(Float, nullable=True)
    movement_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    fragmentation_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_fragmentation_index: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Activity metrics
    total_activity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nonzero_epochs: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Algorithm info
    algorithm_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    scored_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(50), default="draft")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    file: Mapped[File] = relationship("File", back_populates="sleep_metrics")

    __table_args__ = (Index("ix_sleep_metrics_file_date_period", "file_id", "analysis_date", "period_index", unique=True),)


class ConsensusResult(Base):
    """Calculated consensus when 2+ annotations exist."""

    __tablename__ = "consensus_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    analysis_date: Mapped[datetime] = mapped_column(Date, nullable=False)

    has_consensus: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consensus_sleep_markers_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    consensus_nonwear_markers_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    disagreement_details_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    calculated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (Index("ix_consensus_results_file_date", "file_id", "analysis_date", unique=True),)


class ResolvedAnnotation(Base):
    """Admin-resolved final values for disputed annotations."""

    __tablename__ = "resolved_annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    analysis_date: Mapped[datetime] = mapped_column(Date, nullable=False)

    final_sleep_markers_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    final_nonwear_markers_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)

    resolved_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_resolved_annotations_file_date", "file_id", "analysis_date", unique=True),)
