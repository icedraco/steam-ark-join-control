"""
SQLite3 Access Control List Implementation

Author:
    IceDragon <icedragon@quickfox.org>
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, Iterator

import sqlite3

from .base import AclEntry, AbstractAccessControlList

__all__ = ['SqliteAccessControlList']

SQLITE_TIMEOUT = 5.0  # secs


class SqliteAccessControlList(AbstractAccessControlList):
    """
    SQLite3-based AbstractAccessControlList implementation
    """

    @classmethod
    def create(cls, dbfile: str) -> SqliteAccessControlList:
        if os.path.isfile(dbfile):
            raise FileExistsError(dbfile)

        conn = cls.__connect(dbfile)
        conn.execute(
            '''
                CREATE TABLE allowed_users (
                    steam_id   TEXT UNIQUE NOT NULL PRIMARY KEY,
                    name       TEXT        NOT NULL DEFAULT '',
                    added_on   TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_seen  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')

        return cls(conn)

    @classmethod
    def open(cls, dbfile: str, create=True) -> SqliteAccessControlList:
        if os.path.isfile(dbfile):
            return cls(cls.__connect(dbfile))
        elif create:
            return cls.create(dbfile)
        else:
            raise FileNotFoundError(dbfile)

    def __init__(self, sqlite_conn: sqlite3.Connection):
        """
        :param sqlite_conn: open SQLite3 connection to the database
        """
        self.conn = sqlite_conn

    def __enter__(self) -> SqliteAccessControlList:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __len__(self) -> int:
        cur = self.conn.cursor()
        cur.execute('''SELECT COUNT(*) FROM allowed_users''')
        result = cur.fetchone()[0]
        cur.close()
        return result

    def entries(self) -> Iterator[AclEntry]:
        cur = self.conn.cursor()
        cur.execute(
            '''
                SELECT steam_id, name, added_on, last_seen
                FROM allowed_users
            ''')

        for row in cur:
            yield AclEntry(*row)

        cur.close()

    def find(self, steam_id: str) -> Optional[AclEntry]:
        cur = self.conn.cursor()
        cur.execute(
            '''
                SELECT name, added_on, last_seen
                FROM allowed_users
                WHERE steam_id=?
                LIMIT 1
            ''',
            (steam_id,))

        result = cur.fetchone()
        cur.close()
        if not result:
            return None

        name, added_on, last_seen = result
        return AclEntry(steam_id, name, added_on, last_seen)

    def add(
            self,
            steam_id: str,
            name: str,
            added_on: Optional[datetime] = None,
            *,
            last_seen: Optional[datetime] = None,
    ) -> bool:
        if not added_on:
            added_on = datetime.now()

        if not last_seen or last_seen < added_on:
            last_seen = added_on

        cur = self.conn.execute(
            '''
                INSERT OR IGNORE 
                INTO allowed_users 
                (steam_id, name, added_on, last_seen) 
                VALUES 
                (?, ?, ?, ?)
            ''',
            (steam_id, name, added_on, last_seen))

        return cur.rowcount > 0

    def remove(self, steam_id: str) -> bool:
        cur = self.conn.execute(
            '''
                DELETE FROM allowed_users 
                WHERE steam_id=?
            ''',
            (steam_id,))

        success = cur.rowcount > 0
        cur.close()
        return success

    def update_last_seen(self, steam_id: str, ts: Optional[datetime] = None) -> bool:
        cur = self.conn.execute(
            '''
                UPDATE allowed_users
                SET last_seen=?
                WHERE steam_id=?
            ''',
            (ts or datetime.now(), steam_id))

        success = cur.rowcount > 0
        cur.close()
        return success

    def expire(self, min_last_seen: datetime) -> int:
        cur = self.conn.execute(
            '''
                DELETE FROM allowed_users
                WHERE last_seen < ?
            ''',
            (min_last_seen,))

        num_removed = cur.rowcount
        cur.close()
        return num_removed

    def close(self):
        """
        Close this database
        """
        self.conn.close()

    @classmethod
    def __connect(cls, dbfile: str) -> sqlite3.Connection:
        return sqlite3.connect(
            dbfile,
            timeout=SQLITE_TIMEOUT,
            detect_types=sqlite3.PARSE_DECLTYPES,
            isolation_level=None)
