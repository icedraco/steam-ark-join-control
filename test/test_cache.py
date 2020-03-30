import os
from datetime import timedelta
from tempfile import mktemp
from time import sleep
from unittest import TestCase

from service.steam.cache import SqliteSteamProfileCache
from service.steam.model import SteamUserProfile, SteamID


class TestSteamProfileCache(TestCase):
    def setUp(self) -> None:
        self.cache_file = mktemp(suffix='.shelf', prefix='unittest-')
        self.cache = SqliteSteamProfileCache.open(self.cache_file)

        # add default profiles
        self.profiles = [
            SteamUserProfile('https://example.com/1', 'User1', SteamID('0001')),
            SteamUserProfile('https://example.com/2', 'User2', SteamID('0002')),
            SteamUserProfile('https://example.com/3', 'User3', SteamID('0003')),
        ]

        for profile in self.profiles:
            self.cache.put(profile.url, profile, ttl=timedelta(milliseconds=100))

        self.assertEqual(len(self.profiles), len(self.cache))

    def tearDown(self) -> None:
        self.cache.close()
        if os.path.exists(self.cache_file):
            os.unlink(self.cache_file)

    def test_get_missing_profile_returns_none(self):
        self.assertIsNone(self.cache.get('http://whatever.com'))

    def test_caching(self):
        profile_url = 'https://example.com/9999'

        current_count = len(self.cache)
        self.assertIsNone(self.cache.get(profile_url))

        self.cache.put(
            profile_url,
            SteamUserProfile(profile_url, 'Test User', SteamID('0999')),
            ttl=timedelta(days=7),
        )

        self.assertEqual(current_count + 1, len(self.cache))
        profile = self.cache.get(profile_url)
        self.assertIsInstance(profile, SteamUserProfile)
        self.assertEqual(profile_url, profile.url)
        self.assertEqual('Test User', profile.name)
        self.assertEqual(SteamID('0999'), profile.steam_id)

    def test_len(self):
        self.cache.clear()
        for i, profile in enumerate(self.profiles):
            self.assertEqual(i, len(self.cache), msg=repr(profile))
            self.cache.put(profile.url, profile, ttl=timedelta(milliseconds=100))
            self.assertEqual(i + 1, len(self.cache), msg=repr(profile))

        sleep(0.100)
        self.assertEqual(len(self.profiles), self.cache.expire())
        self.assertEqual(0, len(self.cache))

    def test_expiry(self):
        self.cache.clear()
        self.cache.put(self.profiles[0].url, self.profiles[0], ttl=timedelta(milliseconds=50))
        self.cache.put(self.profiles[1].url, self.profiles[1], ttl=timedelta(seconds=1))
        sleep(0.055)

        self.assertEqual(2, len(self.cache))
        self.assertEqual(1, self.cache.expire())
        self.assertEqual(1, len(self.cache))

    def test_persistence_reload(self):
        cache_file = self.cache_file
        cache1 = self.cache

        self.assertEqual(len(self.profiles), len(cache1))
        cache1.close()
        self.assertFalse(cache1.is_open())

        cache2 = SqliteSteamProfileCache.open(cache_file)
        self.assertEqual(len(self.profiles), len(cache2))

        for profile in self.profiles:
            self.assertEqual(profile, cache2.get(profile.url), msg=repr(profile))

        cache2.close()
        self.assertFalse(cache2.is_open())

    def test_put_on_closed_cache_returns_assertion_error(self):
        self.cache.close()
        self.assertFalse(self.cache.is_open())
        with self.assertRaises(AssertionError):
            self.cache.put(self.profiles[0].url, self.profiles[0], ttl=timedelta(days=7))

    def test_get_on_closed_cache_returns_assertion_error(self):
        self.cache.close()
        self.assertFalse(self.cache.is_open())
        with self.assertRaises(AssertionError):
            self.cache.get(self.profiles[0].url)

    def test_clear_on_closed_cache_returns_assertion_error(self):
        self.cache.close()
        self.assertFalse(self.cache.is_open())
        with self.assertRaises(AssertionError):
            self.cache.clear()

    def test_expire_on_closed_cache_returns_assertion_error(self):
        self.cache.close()
        self.assertFalse(self.cache.is_open())
        with self.assertRaises(AssertionError):
            self.cache.expire()

    def test_len_on_closed_cache_returns_assertion_error(self):
        self.cache.close()
        self.assertFalse(self.cache.is_open())
        with self.assertRaises(AssertionError):
            len(self.cache)
