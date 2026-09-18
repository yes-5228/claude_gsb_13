"""保洁巡查记录业务逻辑。"""

from datetime import date, datetime, time

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

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
    stmt = select(Inspection)
    if district:
        stmt = stmt.join(Restroom, Restroom.id == Inspection.restroom_id).where(
            Restroom.district == district
        )
    if restroom_id:
        stmt = stmt.where(Inspection.restroom_id == restroom_id)
    if inspector:
        like = f"%{inspector.strip()}%"
        stmt = stmt.where(
            or_(
                Inspection.inspector.like(like),
                # 更正前后的巡查人都可以检索到该记录
                Inspection.id.in_(
                    select(InspectorCorrection.inspection_id).where(
                        or_(
                            InspectorCorrection.from_inspector.like(like),
                            InspectorCorrection.to_inspector.like(like),
                        )
                    )
                ),
            )
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
    """更正填错的巡查人：留存更正前后内容与原因，得分与结论保持不变。"""
    inspection = get_inspection(db, inspection_id)
    new_inspector = payload.inspector.strip()
    if not new_inspector:
        raise DomainError("更正后的巡查人不能为空")
    reason = payload.reason.strip()
    if not reason:
        raise DomainError("更正巡查人必须说明原因")
    if new_inspector == inspection.inspector:
        raise DomainError("更正后的巡查人与当前巡查人一致，无需更正")
    correction = InspectorCorrection(
        inspection_id=inspection.id,
        from_inspector=inspection.inspector,
        to_inspector=new_inspector,
        reason=reason,
    )
    inspection.inspector = new_inspector
    db.add(correction)
    db.commit()
    db.refresh(inspection)
    return inspection


def list_inspector_corrections(db: Session, inspection_id: int) -> list[InspectorCorrection]:
    inspection = get_inspection(db, inspection_id)
    return list(inspection.corrections)


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
