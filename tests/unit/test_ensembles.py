def test_add_ensemble_returns_id_and_name(client, mock_db):
    gc, conn, cur = mock_db
    cur.fetchone.return_value = (1,)

    response = client.post("/ensembles", json={"name": "Beatles"})

    assert response.status_code == 200
    assert response.json() == {"id": 1, "name": "Beatles"}
    conn.commit.assert_called_once()


def test_count_compositions(client, mock_db):
    gc, conn, cur = mock_db
    cur.fetchone.return_value = (3,)

    response = client.get("/ensembles/1/compositions/count")

    assert response.status_code == 200
    assert response.json() == {"ensemble_id": 1, "compositions_count": 3}
    assert cur.execute.call_args[0][1] == (1,)


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}