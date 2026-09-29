import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def dump(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)


class Store:
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connection() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS catalogs(id TEXT PRIMARY KEY,title TEXT NOT NULL,version INTEGER NOT NULL,state TEXT NOT NULL,original TEXT NOT NULL,published TEXT,published_version INTEGER,created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,catalog_id TEXT NOT NULL,version INTEGER NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,before_state TEXT NOT NULL,created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,name TEXT NOT NULL,role TEXT NOT NULL,salt TEXT NOT NULL,password_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires REAL NOT NULL,csrf TEXT NOT NULL);
            ''')

    @contextmanager
    def connection(self,write=False):
        db=sqlite3.connect(self.path,timeout=20)
        db.row_factory=sqlite3.Row
        try:
            if write: db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
