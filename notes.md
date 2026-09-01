# How Alembic and SQL Alchemy Work together on a postgres database 

Alembic creates the structure, not the entries. 

1. It builds the tables and columns (empty shelves) — never actual rows of data (an actual product, an actual order). Alembic doesn't insert numbers or data.
2. The database itself already exists — Postgres created the empty referenceapp database when docker-compose.yml started it. Alembic's job is narrower: build the tables inside that already-existing, empty database.
3. Corrected version: Alembic reads models.py (written using SQLAlchemy) to know what tables should exist, then creates them — empty, no data — inside Postgres. After that, SQLAlchemy is what the app itself uses, later, to actually put real rows in (a real order) or read them back out.

4. One-line summary: Alembic builds the shelves. SQLAlchemy is what stocks and reads them — both when Alembic is building the shelves, and afterward when the app is running.

