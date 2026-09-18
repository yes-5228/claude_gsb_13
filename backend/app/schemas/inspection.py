"""保洁巡查记录相关数据结构。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import Shift
from app.schemas.restroom import RestroomBrief


class InspectionItem(BaseModel):
    """单个检查项的打分。"""

    name: str = Field(description="检查项名称")
    score: float = Field(ge=0, le=10, description="得分，0-10")
    remark: str | None = Field(default=None, max_length=200, description="单项备注")


class InspectionCreate(BaseModel):
    restroom_id: int
    inspector: str = Field(min_length=1, max_length=60, description="巡查人")
    shift: Shift = Field(default=Shift.MORNING, description="班次")
    inspect_time: datetime | None = Field(default=None, description="巡查时间，留空取当前时间")
    items: list[InspectionItem] = Field(min_length=1, description="检查项打分明细")
    remark: str | None = Field(default=None, max_length=500)


class InspectionUpdate(BaseModel):
    shift: Shift | None = None
    inspect_time: datetime | None = None
    items: list[InspectionItem] | None = Field(default=None, min_length=1)
    remark: str | None = Field(default=None, max_length=500)


class InspectorCorrectionCreate(BaseModel):
    """巡查人更正申请：新巡查人与更正原因必填。"""

    corrected_inspector: str = Field(min_length=1, max_length=60, description="更正后的巡查人")
    reason: str = Field(min_length=1, max_length=500, description="更正原因")
    operator: str = Field(default="", max_length=60, description="执行更正的操作人")

    @field_validator("corrected_inspector", "reason", mode="before")
    @classmethod
    def _strip_required(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("operator", mode="before")
    @classmethod
    def _strip_optional(cls, value):
        return value.strip() if isinstance(value, str) else value


class InspectorCorrectionOut(BaseModel):
    """一条巡查人更正记录。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    original_inspector: str
    corrected_inspector: str
    reason: str
    operator: str
    created_at: datetime


class InspectionBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    inspector: str
    inspect_time: datetime
    score: float
    grade: str
    result: str
    shift: str


class InspectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    restroom_id: int
    restroom: RestroomBrief | None = None
    inspector: str
    shift: str
    inspect_time: datetime
    items: list[InspectionItem] = Field(default_factory=list)
    score: float
    grade: str
    result: str
    remark: str | None = None
    created_at: datetime
    issue_count: int = 0
    corrections: list[InspectorCorrectionOut] = Field(default_factory=list)
