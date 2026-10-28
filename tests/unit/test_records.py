def test_top_sales_returns_sorted_list_and_limit(client, mock_db):
    gc, conn, cur = mock_db
    cur.fetchall.return_value = [("Abbey Road", 500), ("Help!", 300)]

    response = client.get("/records/top-sales?limit=2")

    assert response.status_code == 200
    assert response.json() == [
        {"title": "Abbey Road", "sold_this_year": 500},
        {"title": "Help!", "sold_this_year": 300},
    ]
    assert cur.execute.call_args[0][1] == (2,)


def test_add_record_without_title_returns_422(client, mock_db):
    gc, conn, cur = mock_db

    response = client.post("/records", json={"catalog_number": "EMI-001"})

    assert response.status_code == 422
    gc.assert_not_called()
