import pytest
from fastapi.testclient import TestClient

from main import app, get_connection


@pytest.fixture(scope="session")
def client():
    # С `with` выполняется lifespan, то есть создаются таблицы.
    # raise_server_exceptions=False: ошибки БД приходят как ответ 500, а не исключение.
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_db(client):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("TRUNCATE compositions, records, ensembles RESTART IDENTITY CASCADE;")
    conn.commit()
    cur.close()
    conn.close()