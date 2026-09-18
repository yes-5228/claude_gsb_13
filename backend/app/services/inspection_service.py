"""保洁巡查记录业务逻辑。"""

from datetime import date, datetime, time

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import DomainError, NotFoundError
from app.models import Inspection, InspectorCorrection, Restroom
from app.schemas.inspection import (
    InspectionCreate,
    InspectionOut,
    InspectionUpdate,
    InspectorCorrectionCreate,
)
from app.services import restroom_service, scoring

SORTABLE_FIELDS = {
    "inspect_time": Inspection.inspect_time,
    "score": Inspection.score,
    "inspector": Inspection.inspector,
    "created_at": Inspection.created_at,
}


def _correction_inspector_match(like_value: str):
    """存在性条件：更正流水中的原巡查人或更正后巡查人命中关键字。"""
    return exists().where(
        InspectorCorrection.inspection_id == Inspection.id,
        or_(
            InspectorCorrection.original_inspector.like(like_value),
            InspectorCorrection.corrected_inspector.like(like_value),
        ),
    )


def _normalize_items(items: list) -> list[dict]:
    if not items:
        raise DomainError("巡查检查项不能为空")
    normalized: list[dict] = []
    seen: set[str] = set()
    for item in items:
        data = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        name = str(data.get("name", "")).strip()
        if not name:
            raise DomainError("检查项名称不能为空")
        if name in seen:
            raise DomainError(f"检查项 {name} 重复提交")
        seen.add(name)
        normalized.append(
            {"name": name, "score": float(data.get("score", 0)), "remark": data.get("remark")}
        )
    return normalized


def get_inspection(db: Session, inspection_id: int) -> Inspection:
    inspection = db.get(Inspection, inspection_id)
    if inspection is None:
        raise NotFoundError(f"巡查记录 {inspection_id} 不存在")
    return inspection


def to_out(inspection: Inspection) -> InspectionOut:
    data = InspectionOut.model_validate(inspection)
    data.issue_count = len(inspection.issues)
    return data


def list_inspections(
    db: Session,
    *,
    restroom_id: int | None = None,
    district: str | None = None,
    inspector: str | None = None,
    shift: str | None = None,
    result: str | None = None,
    keyword: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 10,
    sort_by: str = "inspect_time",
    order: str = "desc",
) -> tuple[list[Inspection], int]:
    stmt = select(Inspection).options(selectinload(Inspection.corrections))
    if district:
        stmt = stmt.join(Restroom, Restroom.id == Inspection.restroom_id).where(
            Restroom.district == district
        )
    if restroom_id:
        stmt = stmt.where(Inspection.restroom_id == restroom_id)
    if inspector:
        kw = f"%{inspector.strip()}%"
        stmt = stmt.where(
            or_(Inspection.inspector.like(kw), _correction_inspector_match(kw))
        )
    if shift:
        stmt = stmt.where(Inspection.shift == shift)
    if result:
        stmt = stmt.where(Inspection.result == result)
    if date_from:
        stmt = stmt.where(Inspection.inspect_time >= datetime.combine(date_from, time.min))
    if date_to:
        stmt = stmt.where(Inspection.inspect_time <= datetime.combine(date_to, time.max))
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                Inspection.inspector.like(like),
                Inspection.remark.like(like),
                _correction_inspector_match(like),
                Inspection.restroom_id.in_(select(Restroom.id).where(Restroom.name.like(like))),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    column = SORTABLE_FIELDS.get(sort_by, Inspection.inspect_time)
    stmt = stmt.order_by(column.desc() if order == "desc" else column.asc(), Inspection.id.desc())
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return rows, total


def create_inspection(db: Session, payload: InspectionCreate) -> Inspection:
    restroom_service.get_restroom(db, payload.restroom_id)
    items = _normalize_items(payload.items)
    score, grade, result = scoring.evaluate(items)
    inspection = Inspection(
        restroom_id=payload.restroom_id,
        inspector=payload.inspector,
        shift=payload.shift.value if hasattr(payload.shift, "value") else payload.shift,
        inspect_time=payload.inspect_time or datetime.now(),
        items=items,
        score=score,
        grade=grade,
        result=result,
        remark=payload.remark,
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    restroom_service.touch(db, payload.restroom_id)
    return inspection


def update_inspection(db: Session, inspection_id: int, payload: InspectionUpdate) -> Inspection:
    inspection = get_inspection(db, inspection_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("items") is not None:
        items = _normalize_items(payload.items or [])
        score, grade, result = scoring.evaluate(items)
        inspection.items = items
        inspection.score = score
        inspection.grade = grade
        inspection.result = result
    if data.get("shift") is not None and payload.shift is not None:
        inspection.shift = payload.shift.value if hasattr(payload.shift, "value") else payload.shift
    if data.get("inspect_time") is not None and payload.inspect_time is not None:
        inspection.inspect_time = payload.inspect_time
    if "remark" in data:
        inspection.remark = payload.remark
    db.commit()
    db.refresh(inspection)
    return inspection


def correct_inspector(
    db: Session, inspection_id: int, payload: InspectorCorrectionCreate
) -> Inspection:
    """更正巡查人：记录原巡查人与更正原因，但不改变得分、等级与结论。"""
    inspection = get_inspection(db, inspection_id)
    new_inspector = payload.corrected_inspector.strip()
    reason = payload.reason.strip()
    if new_inspector == inspection.inspector:
        raise DomainError("更正后的巡查人与当前巡查人相同，无需更正")

    inspection.corrections.append(
        InspectorCorrection(
            original_inspector=inspection.inspector,
            corrected_inspector=new_inspector,
            reason=reason,
            operator=payload.operator.strip(),
        )
    )
    # 仅更新巡查人；items/score/grade/result 一律保持原值，确保得分与结论不受更正影响。
    inspection.inspector = new_inspector
    db.commit()
    db.refresh(inspection)
    return inspection


def delete_inspection(db: Session, inspection_id: int) -> None:
    inspection = get_inspection(db, inspection_id)
    db.delete(inspection)
    db.commit()


def restroom_options(db: Session, keyword: str | None = None, limit: int = 50) -> list[Restroom]:
    stmt = select(Restroom).order_by(Restroom.code)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(Restroom.name.like(like), Restroom.code.like(like)))
    return list(db.scalars(stmt.limit(limit)))
