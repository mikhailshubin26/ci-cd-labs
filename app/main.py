from fastapi import FastAPI
from pydantic import BaseModel
import psycopg2
import os
import time
from contextlib import asynccontextmanager

DB_CONFIG = {
    "host": "db",
    "dbname": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
}

def get_connection():
    # Пробуем подключиться к БД в течение нескольких секунд, пока она инициализируется
    for i in range(10):
        try:
            return psycopg2.connect(**DB_CONFIG)
        except psycopg2.OperationalError:
            print(f"База данных еще не готова. Ожидание... (Попытка {i+1}/10)")
            time.sleep(2)
    # Если за 20 секунд не подключились — тогда уже падаем официально
    return psycopg2.connect(**DB_CONFIG)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- То, что выполняется при СТАРТЕ приложения ---
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ensembles (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );
    """)
    # ... (остальные ваши cur.execute для таблиц records и compositions) ...
    conn.commit()
    cur.close()
    conn.close()
    
    yield  # В этой точке приложение работает и принимает запросы
    
    # --- То, что выполняется при ОСТАНОВКЕ приложения (если нужно) ---
    pass

# Передаем lifespan в конструктор приложения
app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Hello World"}

# ---------- Pydantic-модели ----------

class EnsembleIn(BaseModel):
    name: str

class RecordIn(BaseModel):
    catalog_number: str
    title: str
    company: str | None = None
    wholesale_price: float | None = None
    retail_price: float | None = None
    release_date: str | None = None  # формат YYYY-MM-DD
    sold_last_year: int = 0
    sold_this_year: int = 0
    unsold: int = 0

class CompositionIn(BaseModel):
    title: str
    ensemble_id: int
    record_id: int

# ---------- п.5: ввод новых данных об ансамблях ----------

@app.post("/ensembles")
async def add_ensemble(ensemble: EnsembleIn):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ensembles (name) VALUES (%s) RETURNING id;",
        (ensemble.name,)
    )
    ensemble_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return {"id": ensemble_id, "name": ensemble.name}

@app.get("/ensembles")
async def list_ensembles():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM ensembles;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r[0], "name": r[1]} for r in rows]

# ---------- п.4: ввод/изменение данных о пластинках ----------

@app.post("/records")
async def add_record(record: RecordIn):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO records (catalog_number, title, company, wholesale_price,
                              retail_price, release_date, sold_last_year,
                              sold_this_year, unsold)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
    """, (record.catalog_number, record.title, record.company,
          record.wholesale_price, record.retail_price, record.release_date,
          record.sold_last_year, record.sold_this_year, record.unsold))
    record_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return {"id": record_id, **record.dict()}

@app.put("/records/{record_id}")
async def update_record(record_id: int, record: RecordIn):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE records SET catalog_number=%s, title=%s, company=%s,
            wholesale_price=%s, retail_price=%s, release_date=%s,
            sold_last_year=%s, sold_this_year=%s, unsold=%s
        WHERE id=%s;
    """, (record.catalog_number, record.title, record.company,
          record.wholesale_price, record.retail_price, record.release_date,
          record.sold_last_year, record.sold_this_year, record.unsold,
          record_id))
    conn.commit()
    cur.close()
    conn.close()
    return {"id": record_id, **record.dict()}

@app.get("/records")
async def list_records():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, catalog_number, title, sold_this_year FROM records;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r[0], "catalog_number": r[1], "title": r[2], "sold_this_year": r[3]} for r in rows]

# ---------- связь: добавить произведение (ансамбль исполняет на пластинке) ----------

@app.post("/compositions")
async def add_composition(comp: CompositionIn):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO compositions (title, ensemble_id, record_id) VALUES (%s, %s, %s) RETURNING id;",
        (comp.title, comp.ensemble_id, comp.record_id)
    )
    comp_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return {"id": comp_id, **comp.dict()}

# ---------- п.1: количество произведений заданного ансамбля ----------

@app.get("/ensembles/{ensemble_id}/compositions/count")
async def count_compositions(ensemble_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM compositions WHERE ensemble_id = %s;", (ensemble_id,))
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return {"ensemble_id": ensemble_id, "compositions_count": count}

# ---------- п.2: названия всех CD заданного ансамбля ----------

@app.get("/ensembles/{ensemble_id}/records")
async def ensemble_records(ensemble_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT r.id, r.title
        FROM records r
        JOIN compositions c ON c.record_id = r.id
        WHERE c.ensemble_id = %s;
    """, (ensemble_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r[0], "title": r[1]} for r in rows]

# ---------- п.3: лидеры продаж текущего года ----------

@app.get("/records/top-sales")
async def top_sales(limit: int = 5):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT title, sold_this_year
        FROM records
        ORDER BY sold_this_year DESC
        LIMIT %s;
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"title": r[0], "sold_this_year": r[1]} for r in rows]