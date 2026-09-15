import json
import pathlib

import pytest

SAMPLE = pathlib.Path(__file__).resolve().parents[3] / "sample" / "sample_mask.json"


@pytest.fixture(autouse=True)
def isolated_geometry_cache():
    from app.analyzer import clear_geometry_cache
    clear_geometry_cache()
    yield
    clear_geometry_cache()


@pytest.fixture(scope="session")
def sample_bytes() -> bytes:
    return SAMPLE.read_bytes()


@pytest.fixture(scope="session")
def sample_json(sample_bytes: bytes) -> dict:
    return json.loads(sample_bytes)
