import os

from sqlalchemy import create_engine, make_url, text

# Tests truncate tables, so they run against their own database.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5433/payloads_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

url = make_url(TEST_DATABASE_URL)
# CREATE DATABASE cannot run inside a transaction
admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
with admin.connect() as conn:
    exists = conn.execute(
        text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
    ).first()
    if not exists:
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
admin.dispose()
