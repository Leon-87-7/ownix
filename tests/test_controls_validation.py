from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.api.controls import TagIn, _normalize_domain, controls_router
from src.utils.validators import is_valid_domain_name


@pytest.fixture
def controls_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_file = tmp_path / "controls.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))

    from src import database

    asyncio.run(database.init_db())
    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        request.state.user = {"id": 42}
        return await call_next(request)

    app.include_router(controls_router)
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


def test_tag_rejects_blank_name_and_unknown_icon() -> None:
    with pytest.raises(ValidationError):
        TagIn(name="   ")
    with pytest.raises(ValidationError):
        TagIn(name="AI", icon="NotAnIcon")
    assert TagIn(name=" AI ", icon="Brain").icon == "Brain"


def test_domain_validation_rejects_bare_tld_and_bad_labels() -> None:
    assert _normalize_domain("https://www.Example.com/path") == "example.com"
    assert is_valid_domain_name("example.com") is True
    assert is_valid_domain_name("com") is False
    assert is_valid_domain_name("bad_host.example") is False
    assert is_valid_domain_name("example..com") is False


def test_accessibility_settings_endpoints_roundtrip(controls_client: TestClient) -> None:
    endpoint = "/api/controls/accessibility-settings"
    assert controls_client.get(endpoint).json() == {
        "visual_motion": True,
        "haptic_motion": True,
        "voice_uri": None,
    }
    saved = controls_client.put(
        endpoint,
        json={"visual_motion": False, "haptic_motion": True, "voice_uri": "Daniel"},
    )
    assert saved.json() == {
        "visual_motion": False,
        "haptic_motion": True,
        "voice_uri": "Daniel",
    }


def test_tag_endpoints_return_409_for_canonical_collisions(
    controls_client: TestClient,
) -> None:
    payload = {"meaning": "", "color": "#8b5cf6"}
    created = controls_client.post(
        "/api/controls/tags",
        json={**payload, "name": "Read Later"},
    )
    assert created.status_code == 201

    duplicate = controls_client.post(
        "/api/controls/tags",
        json={**payload, "name": "read_later"},
    )
    assert duplicate.status_code == 409

    other = controls_client.post(
        "/api/controls/tags",
        json={**payload, "name": "Archive"},
    )
    assert other.status_code == 201
    renamed = controls_client.put(
        f"/api/controls/tags/{other.json()['id']}",
        json={**payload, "name": "read_later"},
    )
    assert renamed.status_code == 409

    tags = controls_client.get("/api/controls/tags")
    assert tags.status_code == 200
    assert sorted(tag["name"] for tag in tags.json()) == ["Archive", "Read Later"]

def test_accessibility_settings_get_put_and_validate(controls_client: TestClient) -> None:
    response = controls_client.get("/api/controls/accessibility-settings")
    assert response.status_code == 200
    assert response.json() == {
        "visual_motion": True,
        "haptic_motion": True,
        "voice_uri": None,
    }
    response = controls_client.put(
        "/api/controls/accessibility-settings",
        json={"visual_motion": False, "haptic_motion": True, "voice_uri": None},
    )
    assert response.status_code == 200
    assert controls_client.get("/api/controls/accessibility-settings").json() == response.json()
    assert controls_client.put(
        "/api/controls/accessibility-settings", json={"visual_motion": False}
    ).status_code == 422
    assert controls_client.put(
        "/api/controls/accessibility-settings",
        json={"visual_motion": False, "haptic_motion": True},
    ).status_code == 422
    assert controls_client.put(
        "/api/controls/accessibility-settings",
        json={"visual_motion": False, "haptic_motion": True, "voice_uri": "x" * 513},
    ).status_code == 422
