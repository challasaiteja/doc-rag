from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def fake_png_file() -> tuple[str, io.BytesIO, str]:
    return ("sample.png", io.BytesIO(b"not-a-real-png"), "image/png")
