def _record(catalog_number, title, sold_this_year=0):
    return {
        "catalog_number": catalog_number,
        "title": title,
        "sold_this_year": sold_this_year,
    }
 
def test_created_ensemble_appears_in_list(client):
    created = client.post("/ensembles", json={"name": "Beatles"}).json()
 
    listed = client.get("/ensembles").json()
 
    assert {"id": created["id"], "name": "Beatles"} in listed
 
 
def test_duplicate_ensemble_name_fails(client):
    first = client.post("/ensembles", json={"name": "Beatles"})
    second = client.post("/ensembles", json={"name": "Beatles"})
 
    assert first.status_code == 200
    # Фиксируем текущее поведение: нарушение UNIQUE даёт 500 (по-хорошему должно быть 409)
    assert second.status_code == 500

def test_ensemble_records_and_count_after_compositions(client):
    ens_id = client.post("/ensembles", json={"name": "Beatles"}).json()["id"]
    rec1 = client.post("/records", json=_record("EMI-001", "Abbey Road")).json()["id"]
    rec2 = client.post("/records", json=_record("EMI-002", "Help!")).json()["id"]
 
    for title, rec in [("Come Together", rec1), ("Something", rec1), ("Help!", rec2)]:
        r = client.post(
            "/compositions",
            json={"title": title, "ensemble_id": ens_id, "record_id": rec},
        )
        assert r.status_code == 200
 
    count = client.get(f"/ensembles/{ens_id}/compositions/count").json()
    records = client.get(f"/ensembles/{ens_id}/records").json()
 
    assert count["compositions_count"] == 3
    assert len(records) == 2  # DISTINCT: пластинка с двумя произведениями не дублируется
    assert {r["title"] for r in records} == {"Abbey Road", "Help!"}
 
 
def test_update_record_changes_top_sales_order(client):
    id1 = client.post("/records", json=_record("EMI-001", "Abbey Road", 100)).json()["id"]
    id2 = client.post("/records", json=_record("EMI-002", "Help!", 50)).json()["id"]
 
    before = client.get("/records/top-sales").json()
    assert before[0]["title"] == "Abbey Road"
 
    updated = _record("EMI-002", "Help!", 200)
    assert client.put(f"/records/{id2}", json=updated).status_code == 200
 
    after = client.get("/records/top-sales").json()
    assert after[0]["title"] == "Help!"
    assert after[0]["sold_this_year"] == 200
 