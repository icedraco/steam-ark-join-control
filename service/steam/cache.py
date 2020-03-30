"""
SQLite3 Driven Steam Profile Cache - Steam API

A component that allows local mapping from Steam profile URLs to the Steam ID
of the user who owns that profile.

Author:
    IceDragon <icedragon@quickfox.org>
"""


from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

import sqlite3

from .model import SteamUserProfile, SteamID

__all__ = ['SqliteSteamProfileCache']

SQLITE_TIMEOUT = 5.0  # secs


class SqliteSteamProfileCache:
    """
    Responsible for caching SteamUserProfile objects and indexing them by their
    profile URLs.
    """

    @classmethod
    def open(cls, cache_file: str) -> SqliteSteamProfileCache:
        """
        Open or create a cache file

        :param cache_file: cache file to open/create
        :return: SteamProfileCache object for the given cache file
        """
        create = not os.path.isfile(cache_file)
        conn = cls.__connect(cache_file)
        conn.row_factory = sqlite3.Row

        if create:
            conn.execute(
                '''
                    CREATE TABLE profile_cache (
                        profile_url TEXT UNIQUE NOT NULL PRIMARY KEY,
                        steam_id    TEXT        NOT NULL DEFAULT '',
                        name        TEXT        NOT NULL DEFAULT '',
                        created_on  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        last_seen   TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        ttl_secs    NUMERIC     NOT NULL DEFAULT 2678400  -- 31 days
                    )
                ''')

        return cls(conn)

    def __init__(self, conn: sqlite3.Connection):
        self.__conn = conn

    def __enter__(self) -> SqliteSteamProfileCache:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __len__(self) -> int:
        """
        :return: amount of entries currently cached
        """
        cur = self._conn.cursor()
        cur.execute('''SELECT COUNT(*) FROM profile_cache''')
        result = cur.fetchone()[0]
        cur.close()
        return result

    @property
    def _conn(self) -> sqlite3.Connection:
        assert self.is_open(), 'this cache is closed'
        return self.__conn

    def is_open(self) -> bool:
        """
        :return: True if this cache is currently open
        """
        return self.__conn is not None

    def get(self, profile_url: str) -> Optional[SteamUserProfile]:
        """
        Get a profile from cache by given profile URL

        :param profile_url: Steam profile URL
        :return: SteamUserProfile associated with the profile URL, or None if not found in cache
        """
        cur = self._conn.cursor()
        cur.execute(
            '''
                SELECT steam_id, name
                FROM profile_cache
                WHERE profile_url=?
                LIMIT 1
            ''',
            (profile_url,))

        row = cur.fetchone()
        cur.close()
        if not row:
            return None

        profile = SteamUserProfile(profile_url, row['name'], SteamID(row['steam_id']))
        self.__update_seen(profile_url)
        return profile

    def put(self, profile_url: str, profile: SteamUserProfile, ttl: timedelta):
        """
        Put a profile in cache, or update its expiry time

        :param profile_url: user profile URL (used to obtain the profile)
        :param profile: user profile to store/update
        :param ttl: how long will this entry live without access?
        """
        cur = self._conn.cursor()
        cur.execute(
            '''
                REPLACE INTO
                profile_cache(profile_url, steam_id, name, ttl_secs)
                VALUES(?, ?, ?, ?)
            ''',
            (profile_url, profile.steam_id, profile.name, ttl.total_seconds())
        )

    def remove(self, profile_url: str) -> bool:
        """
        Remove a Steam user profile from cache by given profile URL

        :param profile_url: profile URL to remove
        :return: True if cache entry found and removed; False if not found
        """
        cur = self._conn.cursor()
        cur.execute(
            '''
                DELETE FROM profile_cache
                WHERE profile_url=?
            ''',
            (profile_url,))

        found = cur.rowcount > 0
        cur.close()
        return found

    def expire(self) -> int:
        """
        Expire all relevant cache entries

        :return: amount of entries expired
        """
        cur = self._conn.cursor()
        cur.execute(
            '''
                DELETE FROM profile_cache
                WHERE DATETIME(last_seen, '+'||ttl_secs||' seconds') <= CURRENT_TIMESTAMP
            ''')

        num_expired = cur.rowcount
        cur.close()
        return num_expired

    def clear(self):
        """
        Clear cache to have nothing in it
        """
        # noinspection SqlWithoutWhere
        self._conn.execute('''DELETE FROM profile_cache''')

    def close(self):
        """
        Close cache file

        Note:
            Further operations on this cache after closure will result in
            AssertionError
        """
        if self.__conn is not None:
            self.__conn.close()
            self.__conn = None

        assert not self.is_open()

    def __update_seen(self, profile_url) -> bool:
        cur = self._conn.cursor()
        cur.execute(
            '''
                UPDATE profile_cache
                SET last_seen=?
                WHERE profile_url=?
            ''',
            (datetime.now(), profile_url))

        updated = cur.rowcount > 0
        cur.close()
        return updated

    @classmethod
    def __connect(cls, dbfile: str) -> sqlite3.Connection:
        return sqlite3.connect(
            dbfile,
            timeout=SQLITE_TIMEOUT,
            detect_types=sqlite3.PARSE_DECLTYPES,
            isolation_level=None)
