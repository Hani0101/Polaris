import pytest

from polaris import app


@pytest.fixture(autouse=True)
def test_client_is_this_machine(monkeypatch):
    """TestClient sends Host: testserver from the client named testclient (AU-14)."""

    monkeypatch.setattr(app, "LOCAL_NAMES", app.LOCAL_NAMES | {"testserver", "testclient"})
