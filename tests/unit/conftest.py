import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_db():
    with patch("main.get_connection") as gc:
        conn = MagicMock()
        cur = conn.cursor.return_value
        gc.return_value = conn
        yield gc, conn, cur