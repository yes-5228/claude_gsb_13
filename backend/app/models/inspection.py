"""保洁巡查记录模型。"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import InspectionResult, Shift
from app.core.database import Base


class Inspection(Base):
    """一次保洁巡查的结果，包含各检查项打分。"""

    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restroom_id: Mapped[int] = mapped_column(
        ForeignKey("restrooms.id", ondelete="CASCADE"), index=True, comment="所属公厕"
    )
    inspector: Mapped[str] = mapped_column(String(60), index=True, comment="巡查人")
    inspect_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, index=True, comment="巡查时间"
    )
    shift: Mapped[str] = mapped_column(String(20), default=Shift.MORNING.value, comment="班次")
    items: Mapped[list[dict]] = mapped_column(JSON, default=list, comment="检查项打分明细")
    score: Mapped[float] = mapped_column(Float, default=0.0, comment="巡查得分")
    grade: Mapped[str] = mapped_column(String(20), default="", comment="评分等级")
    result: Mapped[str] = mapped_column(
        String(20), default=InspectionResult.NORMAL.value, index=True, comment="巡查结论"
    )
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="巡查备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    restroom: Mapped["Restroom"] = relationship(back_populates="inspections")  # noqa: F821
    issues: Mapped[list["Issue"]] = relationship(back_populates="inspection")  # noqa: F821
    corrections: Mapped[list["InspectorCorrection"]] = relationship(
        back_populates="inspection",
        cascade="all, delete-orphan",
        order_by="InspectorCorrection.created_at",
    )


class InspectorCorrection(Base):
    """巡查人更正记录：保留更正前后的巡查人与更正原因，便于追溯。"""

    __tablename__ = "inspector_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inspection_id: Mapped[int] = mapped_column(
        ForeignKey("inspections.id", ondelete="CASCADE"), index=True, comment="所属巡查记录"
    )
    from_inspector: Mapped[str] = mapped_column(String(60), comment="更正前巡查人")
    to_inspector: Mapped[str] = mapped_column(String(60), index=True, comment="更正后巡查人")
    reason: Mapped[str] = mapped_column(Text, comment="更正原因")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, index=True, comment="更正时间"
    )

    inspection: Mapped["Inspection"] = relationship(back_populates="corrections")
