from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.enums import BackgroundTaskStatus, BackgroundTaskType
from app.db.metadata import database_enum, mutable_json_dict


class BackgroundTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "background_tasks"
    __table_args__ = (
        Index("ix_background_tasks_created_at", "created_at"),
        CheckConstraint("completed_items >= 0", name="completed_items_nonnegative"),
        CheckConstraint("total_items IS NULL OR total_items >= 0", name="total_items_nonnegative"),
        CheckConstraint("percentage >= 0 AND percentage <= 100", name="percentage_range"),
        CheckConstraint(
            "total_items IS NULL OR completed_items <= total_items",
            name="completed_within_total",
        ),
    )

    type: Mapped[BackgroundTaskType] = mapped_column(
        database_enum(BackgroundTaskType, "background_task_type"), index=True
    )
    status: Mapped[BackgroundTaskStatus] = mapped_column(
        database_enum(BackgroundTaskStatus, "background_task_status"),
        default=BackgroundTaskStatus.PENDING,
        index=True,
    )
    job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("job_postings.id", ondelete="SET NULL"), index=True
    )
    candidate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("candidates.id", ondelete="SET NULL"), index=True
    )
    current_step: Mapped[str | None] = mapped_column(String(255))
    completed_items: Mapped[int] = mapped_column(Integer, default=0)
    total_items: Mapped[int | None] = mapped_column(Integer)
    percentage: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, object]] = mapped_column(mutable_json_dict(), default=dict)
    result: Mapped[dict[str, object]] = mapped_column(mutable_json_dict(), default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            BackgroundTaskStatus.COMPLETED,
            BackgroundTaskStatus.FAILED,
            BackgroundTaskStatus.CANCELLED,
        }
