from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.audit_log import AuditLog
from app.models.enums import MaintenanceStatus, UserRole
from app.models.user import User
from app.schemas.asset import AssetCreate
from app.services.assets import create_asset
from tests.types import TokenResponseData


def test_engineer_cannot_view_unrelated_request(
    client: TestClient,
    db_session: Session,
    make_user: Callable[[str, UserRole, str], User],
    login_as: Callable[[str, str], TokenResponseData],
) -> None:
    supervisor = make_user(
        "supervisor1@example.com", UserRole.SUPERVISOR, "ChangeMe123!"
    )
    requester = make_user(
        "engineer-owner@example.com", UserRole.ENGINEER, "ChangeMe123!"
    )
    outsider = make_user(
        "engineer-outsider@example.com", UserRole.ENGINEER, "ChangeMe123!"
    )
    asset = create_asset(
        db_session,
        supervisor,
        AssetCreate(
            asset_tag="VALVE-2001",
            name="Gas inlet valve",
            facility="West Pad",
            equipment_type="Valve",
            location_detail="Cluster 5",
        ),
    )
    db_session.commit()

    owner_tokens = login_as(requester.email, "ChangeMe123!")
    create_response = client.post(
        "/api/v1/maintenance-requests",
        headers={"Authorization": f"Bearer {owner_tokens['access_token']}"},
        json={
            "asset_id": asset.id,
            "title": "Valve pressure fluctuation",
            "description": "Pressure readings became unstable during morning shift.",
            "issue_code": "PRS-03",
        },
    )
    assert create_response.status_code == 201, create_response.text
    request_id = create_response.json()["id"]

    outsider_tokens = login_as(outsider.email, "ChangeMe123!")
    read_response = client.get(
        f"/api/v1/maintenance-requests/{request_id}",
        headers={"Authorization": f"Bearer {outsider_tokens['access_token']}"},
    )

    assert read_response.status_code == 403


def test_assets_require_authentication(
    client: TestClient,
    db_session: Session,
    make_user: Callable[[str, UserRole, str], User],
) -> None:
    supervisor = make_user(
        "supervisor-assets@example.com", UserRole.SUPERVISOR, "ChangeMe123!"
    )
    asset = create_asset(
        db_session,
        supervisor,
        AssetCreate(
            asset_tag="PIPE-1001",
            name="Pipeline segment",
            facility="North Yard",
            equipment_type="Pipe",
            location_detail="Section 7",
        ),
    )
    db_session.commit()

    list_response = client.get("/api/v1/assets")
    detail_response = client.get(f"/api/v1/assets/{asset.id}")

    assert list_response.status_code == 401
    assert detail_response.status_code == 401


def test_supervisor_assigns_and_engineer_completes_request(
    client: TestClient,
    db_session: Session,
    make_user: Callable[[str, UserRole, str], User],
    login_as: Callable[[str, str], TokenResponseData],
) -> None:
    supervisor = make_user(
        "supervisor2@example.com", UserRole.SUPERVISOR, "ChangeMe123!"
    )
    engineer = make_user("engineer-main@example.com", UserRole.ENGINEER, "ChangeMe123!")
    asset = create_asset(
        db_session,
        supervisor,
        AssetCreate(
            asset_tag="PUMP-3001",
            name="Injection pump",
            facility="North Station",
            equipment_type="Pump",
            location_detail="Line 2",
        ),
    )
    db_session.commit()

    engineer_tokens = login_as(engineer.email, "ChangeMe123!")
    create_response = client.post(
        "/api/v1/maintenance-requests",
        headers={"Authorization": f"Bearer {engineer_tokens['access_token']}"},
        json={
            "asset_id": asset.id,
            "title": "Pump vibration check",
            "description": "Abnormal vibration observed after restart.",
            "issue_code": "VIB-02",
        },
    )
    assert create_response.status_code == 201, create_response.text
    request_id = create_response.json()["id"]
    assert create_response.json()["status"] == MaintenanceStatus.OPEN.value
    assert "requested_by_id" not in create_response.json()
    assert "created_at" not in create_response.json()
    assert "updated_at" not in create_response.json()

    supervisor_tokens = login_as(supervisor.email, "ChangeMe123!")
    assign_response = client.patch(
        f"/api/v1/maintenance-requests/{request_id}/status",
        headers={"Authorization": f"Bearer {supervisor_tokens['access_token']}"},
        json={
            "status": MaintenanceStatus.ASSIGNED.value,
            "assigned_engineer_id": engineer.id,
            "internal_notes": "Dispatch during low-load window only.",
        },
    )
    assert assign_response.status_code == 200, assign_response.text
    assert assign_response.json()["status"] == MaintenanceStatus.ASSIGNED.value
    assert (
        assign_response.json()["internal_notes"]
        == "Dispatch during low-load window only."
    )

    outsider = make_user(
        "engineer-status-outsider@example.com", UserRole.ENGINEER, "ChangeMe123!"
    )
    outsider_tokens = login_as(outsider.email, "ChangeMe123!")
    forbidden_status_response = client.patch(
        f"/api/v1/maintenance-requests/{request_id}/status",
        headers={"Authorization": f"Bearer {outsider_tokens['access_token']}"},
        json={"status": MaintenanceStatus.IN_PROGRESS.value},
    )
    assert forbidden_status_response.status_code == 403

    engineer_view = client.get(
        f"/api/v1/maintenance-requests/{request_id}",
        headers={"Authorization": f"Bearer {engineer_tokens['access_token']}"},
    )
    assert engineer_view.status_code == 200
    assert engineer_view.json()["internal_notes"] is None

    in_progress_response = client.patch(
        f"/api/v1/maintenance-requests/{request_id}/status",
        headers={"Authorization": f"Bearer {engineer_tokens['access_token']}"},
        json={"status": MaintenanceStatus.IN_PROGRESS.value},
    )
    assert in_progress_response.status_code == 200, in_progress_response.text
    assert in_progress_response.json()["status"] == MaintenanceStatus.IN_PROGRESS.value

    completed_response = client.patch(
        f"/api/v1/maintenance-requests/{request_id}/status",
        headers={"Authorization": f"Bearer {engineer_tokens['access_token']}"},
        json={"status": MaintenanceStatus.COMPLETED.value},
    )
    assert completed_response.status_code == 200, completed_response.text
    assert completed_response.json()["status"] == MaintenanceStatus.COMPLETED.value
    assert completed_response.json()["completed_at"] is not None

    actions = db_session.query(AuditLog.action).all()
    assert ("maintenance_request.create",) in actions
    assert ("maintenance_request.status_change",) in actions


def test_supervisor_cannot_start_or_complete_assigned_engineer_work(
    client: TestClient,
    db_session: Session,
    make_user: Callable[[str, UserRole, str], User],
    login_as: Callable[[str, str], TokenResponseData],
) -> None:
    supervisor = make_user(
        "supervisor-p5-status@example.com", UserRole.SUPERVISOR, "ChangeMe123!"
    )
    engineer = make_user(
        "engineer-p5-status@example.com", UserRole.ENGINEER, "ChangeMe123!"
    )
    asset = create_asset(
        db_session,
        supervisor,
        AssetCreate(
            asset_tag="PUMP-P5-STATUS",
            name="Process pump",
            facility="Central Station",
            equipment_type="Pump",
            location_detail="Skid 9",
        ),
    )
    db_session.commit()

    engineer_tokens = login_as(engineer.email, "ChangeMe123!")
    create_response = client.post(
        "/api/v1/maintenance-requests",
        headers={"Authorization": f"Bearer {engineer_tokens['access_token']}"},
        json={
            "asset_id": asset.id,
            "title": "Seal replacement",
            "description": "Seal wear observed during inspection.",
            "issue_code": "SEAL-01",
        },
    )
    assert create_response.status_code == 201, create_response.text
    request_id = create_response.json()["id"]

    supervisor_tokens = login_as(supervisor.email, "ChangeMe123!")
    assign_response = client.patch(
        f"/api/v1/maintenance-requests/{request_id}/status",
        headers={"Authorization": f"Bearer {supervisor_tokens['access_token']}"},
        json={
            "status": MaintenanceStatus.ASSIGNED.value,
            "assigned_engineer_id": engineer.id,
            "internal_notes": "Work must be performed by the assigned engineer.",
        },
    )
    assert assign_response.status_code == 200, assign_response.text

    forbidden_start = client.patch(
        f"/api/v1/maintenance-requests/{request_id}/status",
        headers={"Authorization": f"Bearer {supervisor_tokens['access_token']}"},
        json={"status": MaintenanceStatus.IN_PROGRESS.value},
    )
    forbidden_complete = client.patch(
        f"/api/v1/maintenance-requests/{request_id}/status",
        headers={"Authorization": f"Bearer {supervisor_tokens['access_token']}"},
        json={"status": MaintenanceStatus.COMPLETED.value},
    )

    assert forbidden_start.status_code == 403
    assert forbidden_complete.status_code == 403


def test_invalid_uuid_inputs_are_rejected(
    client: TestClient,
    db_session: Session,
    make_user: Callable[[str, UserRole, str], User],
    login_as: Callable[[str, str], TokenResponseData],
) -> None:
    supervisor = make_user(
        "supervisor-uuid@example.com", UserRole.SUPERVISOR, "ChangeMe123!"
    )
    engineer = make_user("engineer-uuid@example.com", UserRole.ENGINEER, "ChangeMe123!")
    supervisor_tokens = login_as(supervisor.email, "ChangeMe123!")
    engineer_tokens = login_as(engineer.email, "ChangeMe123!")

    invalid_asset_detail = client.get(
        "/api/v1/assets/not-a-uuid",
        headers={"Authorization": f"Bearer {supervisor_tokens['access_token']}"},
    )
    invalid_request_create = client.post(
        "/api/v1/maintenance-requests",
        headers={"Authorization": f"Bearer {engineer_tokens['access_token']}"},
        json={
            "asset_id": "not-a-uuid",
            "title": "Pump vibration check",
            "description": "Abnormal vibration observed after restart.",
            "issue_code": "VIB-02",
        },
    )

    assert invalid_asset_detail.status_code == 422
    assert invalid_request_create.status_code == 422


def test_asset_creation_and_report_export_are_role_restricted(
    client: TestClient,
    db_session: Session,
    make_user: Callable[[str, UserRole, str], User],
    login_as: Callable[[str, str], TokenResponseData],
) -> None:
    supervisor = make_user(
        "supervisor3@example.com", UserRole.SUPERVISOR, "ChangeMe123!"
    )
    engineer = make_user(
        "engineer-report@example.com", UserRole.ENGINEER, "ChangeMe123!"
    )
    supervisor_tokens = login_as(supervisor.email, "ChangeMe123!")
    engineer_tokens = login_as(engineer.email, "ChangeMe123!")

    forbidden_asset_response = client.post(
        "/api/v1/assets",
        headers={"Authorization": f"Bearer {engineer_tokens['access_token']}"},
        json={
            "asset_tag": "COMP-4001",
            "name": "Compressor",
            "facility": "Central Yard",
            "equipment_type": "Compressor",
            "location_detail": "Bay 4",
        },
    )
    assert forbidden_asset_response.status_code == 403

    create_asset_response = client.post(
        "/api/v1/assets",
        headers={"Authorization": f"Bearer {supervisor_tokens['access_token']}"},
        json={
            "asset_tag": "COMP-4001",
            "name": "Compressor",
            "facility": "Central Yard",
            "equipment_type": "Compressor",
            "location_detail": "Bay 4",
        },
    )
    assert create_asset_response.status_code == 201, create_asset_response.text
    assert "registered_by_id" not in create_asset_response.json()
    assert "created_at" not in create_asset_response.json()
    assert "updated_at" not in create_asset_response.json()

    engineer_report_response = client.get(
        "/api/v1/reports/maintenance-summary",
        headers={"Authorization": f"Bearer {engineer_tokens['access_token']}"},
    )
    assert engineer_report_response.status_code == 403

    supervisor_report_response = client.get(
        "/api/v1/reports/maintenance-summary",
        headers={"Authorization": f"Bearer {supervisor_tokens['access_token']}"},
    )
    assert supervisor_report_response.status_code == 200, (
        supervisor_report_response.text
    )
    payload = supervisor_report_response.json()
    assert payload["total_requests"] >= 0

    stored_asset = (
        db_session.query(Asset).filter(Asset.asset_tag == "COMP-4001").one_or_none()
    )
    assert stored_asset is not None
