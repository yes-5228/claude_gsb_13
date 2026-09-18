"""巡查人更正：原因必填、原值留存、得分结论不变、前后人员均可查询。"""

from tests.conftest import full_items


def _create_inspection(client, restroom, inspector="李巡查"):
    resp = client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": inspector,
            "shift": "中班",
            "items": full_items(9),
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_correct_inspector_keeps_score_and_result(client, restroom):
    inspection = _create_inspection(client, restroom, inspector="李巡查")
    before = {key: inspection[key] for key in ("score", "grade", "result", "items", "shift")}

    resp = client.post(
        f"/api/v1/inspections/{inspection['id']}/inspector-correction",
        json={
            "corrected_inspector": "王巡查",
            "reason": "原记录为替班代签，实际巡查人为王巡查",
            "operator": "值班长",
        },
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()

    # 当前巡查人已变更
    assert updated["inspector"] == "王巡查"
    # 得分、等级、结论、打分明细、班次均不因更正而变化
    for key, value in before.items():
        assert updated[key] == value

    # 更正流水完整保留原值、新值、原因、操作人
    assert len(updated["corrections"]) == 1
    record = updated["corrections"][0]
    assert record["original_inspector"] == "李巡查"
    assert record["corrected_inspector"] == "王巡查"
    assert "替班代签" in record["reason"]
    assert record["operator"] == "值班长"
    assert record["created_at"]


def test_correction_requires_reason(client, restroom):
    inspection = _create_inspection(client, restroom)

    missing_reason = client.post(
        f"/api/v1/inspections/{inspection['id']}/inspector-correction",
        json={"corrected_inspector": "王巡查"},
    )
    assert missing_reason.status_code == 422

    blank_reason = client.post(
        f"/api/v1/inspections/{inspection['id']}/inspector-correction",
        json={"corrected_inspector": "王巡查", "reason": "   "},
    )
    assert blank_reason.status_code == 422

    blank_inspector = client.post(
        f"/api/v1/inspections/{inspection['id']}/inspector-correction",
        json={"corrected_inspector": "   ", "reason": "笔误"},
    )
    assert blank_inspector.status_code == 422


def test_correction_rejects_same_inspector(client, restroom):
    inspection = _create_inspection(client, restroom)
    resp = client.post(
        f"/api/v1/inspections/{inspection['id']}/inspector-correction",
        json={"corrected_inspector": "李巡查", "reason": "重复提交"},
    )
    assert resp.status_code == 400
    assert "相同" in resp.json()["detail"]


def test_repeated_corrections_keep_full_chain(client, restroom):
    inspection = _create_inspection(client, restroom, inspector="李巡查")

    for corrected in ("王巡查", "赵巡查"):
        resp = client.post(
            f"/api/v1/inspections/{inspection['id']}/inspector-correction",
            json={"corrected_inspector": corrected, "reason": f"更正为{corrected}"},
        )
        assert resp.status_code == 200, resp.text

    detail = client.get(f"/api/v1/inspections/{inspection['id']}").json()
    assert detail["inspector"] == "赵巡查"
    assert [c["original_inspector"] for c in detail["corrections"]] == ["李巡查", "王巡查"]
    assert [c["corrected_inspector"] for c in detail["corrections"]] == ["王巡查", "赵巡查"]
    # 首次更正的原值始终是最初录入的巡查人
    assert detail["corrections"][0]["original_inspector"] == "李巡查"


def test_inspectors_before_and_after_are_searchable(client, restroom):
    inspection = _create_inspection(client, restroom, inspector="李巡查")
    client.post(
        f"/api/v1/inspections/{inspection['id']}/inspector-correction",
        json={"corrected_inspector": "王巡查", "reason": "录入笔误"},
    )

    def search(extra):
        return client.get(
            "/api/v1/inspections", params={"restroom_id": restroom["id"], **extra}
        ).json()

    # 按当前（更正后）巡查人可检索到
    by_new = search({"inspector": "王巡查"})
    assert by_new["meta"]["total"] == 1
    assert by_new["items"][0]["id"] == inspection["id"]

    # 按原巡查人仍可检索到（更正前后的人员信息都可查询）
    by_old = search({"inspector": "李巡查"})
    assert by_old["meta"]["total"] == 1
    assert by_old["items"][0]["id"] == inspection["id"]

    # 列表项也带更正标记
    row = by_old["items"][0]
    assert row["inspector"] == "王巡查"
    assert row["corrections"][0]["original_inspector"] == "李巡查"

    # 关键字搜索原巡查人同样可命中
    by_keyword = search({"keyword": "李巡查"})
    assert by_keyword["meta"]["total"] == 1


def test_patch_cannot_silently_change_inspector(client, restroom):
    inspection = _create_inspection(client, restroom, inspector="李巡查")
    # 通用更新接口不再受理巡查人字段，巡查人保持原值，且不产生更正流水
    resp = client.patch(
        f"/api/v1/inspections/{inspection['id']}",
        json={"inspector": "王巡查", "shift": "晚班"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["inspector"] == "李巡查"
    assert resp.json()["shift"] == "晚班"
    assert resp.json()["corrections"] == []
