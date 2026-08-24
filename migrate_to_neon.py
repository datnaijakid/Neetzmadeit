"""
Migration Script: Transfer local SQLite data (neetzmadeit.db) to Neon PostgreSQL.
Usage:
  1. Ensure DATABASE_URL is set in your .env file or environment:
     DATABASE_URL=postgresql://user:pass@ep-xyz.aws.neon.tech/neetzmadeit?sslmode=require
  2. Run:
     python migrate_to_neon.py
"""

import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def migrate():
    database_url = os.environ.get('DATABASE_URL', '').strip()
    if not database_url:
        print("ERROR: DATABASE_URL is not set. Please set it in your .env file.")
        return

    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    print("Connecting to local SQLite database (neetzmadeit.db)...")
    sqlite_conn = sqlite3.connect('neetzmadeit.db')
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    print("Connecting to Neon PostgreSQL database...")
    pg_conn = psycopg2.connect(database_url)
    pg_cur = pg_conn.cursor()

    print("Creating tables in Neon PostgreSQL if not exists...")
    pg_cur.execute('''
        CREATE TABLE IF NOT EXISTS "user" (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS product (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            price DOUBLE PRECISION NOT NULL,
            images TEXT NOT NULL,
            is_featured BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS site_settings (
            id SERIAL PRIMARY KEY,
            key TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL
        );
    ''')
    pg_conn.commit()

    # 1. Migrate Users
    users = sqlite_cur.execute('SELECT username, password_hash FROM user').fetchall()
    for u in users:
        pg_cur.execute('''
            INSERT INTO "user" (username, password_hash)
            VALUES (%s, %s)
            ON CONFLICT (username) DO NOTHING
        ''', (u['username'], u['password_hash']))
    pg_conn.commit()
    print(f"Migrated {len(users)} user(s).")

    # 2. Migrate Products
    products = sqlite_cur.execute('SELECT name, description, price, images, is_featured, created_at FROM product').fetchall()
    migrated_products = 0
    for p in products:
        # Check if product already exists by name
        pg_cur.execute('SELECT id FROM product WHERE name = %s', (p['name'],))
        if not pg_cur.fetchone():
            pg_cur.execute('''
                INSERT INTO product (name, description, price, images, is_featured, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (p['name'], p['description'], float(p['price']), p['images'], bool(p['is_featured']), p['created_at']))
            migrated_products += 1
    pg_conn.commit()
    print(f"Migrated {migrated_products} new product(s) (out of {len(products)} found in SQLite).")

    # 3. Migrate Site Settings
    settings = sqlite_cur.execute('SELECT key, value FROM site_settings').fetchall()
    for s in settings:
        pg_cur.execute('''
            INSERT INTO site_settings (key, value)
            VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        ''', (s['key'], s['value']))
    pg_conn.commit()
    print(f"Migrated {len(settings)} setting(s).")

    sqlite_conn.close()
    pg_conn.close()
    print("\nMigration to Neon PostgreSQL completed successfully!")

if __name__ == '__main__':
    migrate()
