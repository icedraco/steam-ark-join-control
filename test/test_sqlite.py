import os
import tempfile
from datetime import datetime, timedelta
from unittest import TestCase

from service.acl.sqlite import SqliteAccessControlList


class TestSqliteAccessStore(TestCase):
    def setUp(self) -> None:
        self.dbfile = tempfile.mktemp(prefix='unittest-', suffix='.sqlite')
        self.assertFalse(os.path.exists(self.dbfile))

    def tearDown(self) -> None:
        if os.path.exists(self.dbfile):
            os.unlink(self.dbfile)

        self.assertFalse(os.path.exists(self.dbfile))

    def test_create_raises_if_file_exists(self):
        db = self.dbfile

        with open(db, 'w') as f:
            f.write('stuff')

        self.assertTrue(os.path.isfile(db))
        with self.assertRaises(FileExistsError):
            SqliteAccessControlList.create(db)

    def test_create_creates_and_populates_dbfile(self):
        db = self.dbfile
        SqliteAccessControlList.create(db).close()
        self.assertTrue(os.path.isfile(db))
        self.assertGreater(os.path.getsize(db), 0)

    def test_open_raises_is_file_is_missing_and_create_flag_is_false(self):
        db = self.dbfile
        self.assertFalse(os.path.exists(db))
        with self.assertRaises(FileNotFoundError):
            SqliteAccessControlList.open(db, create=False)

    def test_open_creates_file_if_missing(self):
        db = self.dbfile
        self.assertFalse(os.path.exists(db))
        SqliteAccessControlList.open(db).close()
        self.assertTrue(os.path.exists(db))

    def test_open_succeeds_after_create(self):
        db = self.dbfile
        SqliteAccessControlList.create(db).close()
        SqliteAccessControlList.open(db).close()

    def test_find_returns_none_if_steam_id_missing(self):
        db = self.dbfile
        store = SqliteAccessControlList.create(db)
        self.assertIsNone(store.find('bogus_steam_id_here'))

    def test_find_returns_correct_object(self):
        now = datetime.now()
        steam_id = '31337'
        steam_user = 'Test User'

        db = SqliteAccessControlList.create(self.dbfile)
        self.assertTrue(db.add(steam_id, steam_user, now))

        entry = db.find(steam_id)
        self.assertEqual(steam_id, entry.steam_id, msg=repr(entry))
        self.assertEqual(steam_user, entry.name, msg=repr(entry))
        self.assertEqual(now, entry.added_on, msg=repr(entry))

    def test_add_new_user_returns_true(self):
        db = SqliteAccessControlList.create(self.dbfile)
        self.assertTrue(db.add('12345', 'Test User'))

    def test_add_existing_user_returns_false(self):
        db = SqliteAccessControlList.create(self.dbfile)
        self.assertTrue(db.add('12345', 'Test User'))
        self.assertFalse(db.add('12345', 'Test User'))

    def test_add_existing_steam_id_with_different_username_returns_false(self):
        db = SqliteAccessControlList.create(self.dbfile)
        self.assertTrue(db.add('12345', 'Test User'))
        self.assertFalse(db.add('12345', 'Different'))

    def test_add_new_steam_id_with_existing_username_adds_as_new_user(self):
        db = SqliteAccessControlList.create(self.dbfile)
        self.assertTrue(db.add('12345', 'Test User'))
        self.assertTrue(db.add('12346', 'Test User'))

        user1 = db.find('12345')
        self.assertEqual('12345', user1.steam_id)
        self.assertEqual('Test User', user1.name)

        user2 = db.find('12346')
        self.assertEqual('12346', user2.steam_id)
        self.assertEqual('Test User', user2.name)

    def test_remove_missing_steam_id_returns_false(self):
        db = SqliteAccessControlList.create(self.dbfile)
        self.assertFalse(db.remove('12345'))
        self.assertFalse(db.remove('missing'))

    def test_remove_existing_steam_id_returns_true_only_once(self):
        db = SqliteAccessControlList.create(self.dbfile)
        self.assertTrue(db.add('12345', 'Test User'))
        self.assertTrue(db.remove('12345'))
        self.assertFalse(db.remove('12345'))

    def test_len(self):
        db = SqliteAccessControlList.create(self.dbfile)
        self.assertEqual(0, len(db))

        self.assertTrue(db.add('12345', 'User 1'))
        self.assertEqual(1, len(db))

        self.assertFalse(db.add('12345', 'User 1'))
        self.assertEqual(1, len(db))

        self.assertTrue(db.add('12346', 'User 2'))
        self.assertEqual(2, len(db))

        self.assertTrue(db.add('12347', 'User 3'))
        self.assertEqual(3, len(db))

        self.assertTrue(db.remove('12346'))
        self.assertEqual(2, len(db))

    def test_default_add_timestamp_is_correct(self):
        db = SqliteAccessControlList.create(self.dbfile)

        lim_min = datetime.now()
        db.add('12345', 'Test User')
        lim_max = datetime.now() + timedelta(milliseconds=5)

        entry = db.find('12345')
        self.assertIsInstance(entry.added_on, datetime, msg=repr(entry))
        self.assertTrue(lim_min <= entry.added_on < lim_max, msg=repr(entry))

    def test_add_remove_operations_are_flushed_asap(self):
        db1 = SqliteAccessControlList.create(self.dbfile)
        db2 = SqliteAccessControlList.open(self.dbfile)

        self.assertEqual(0, len(db2))
        self.assertTrue(db1.add('12345', 'Test User'))
        self.assertEqual(1, len(db2))
        self.assertFalse(db2.add('12345', 'Test User 2'))
        self.assertTrue(db2.add('12346', 'Test User 2'))
        self.assertEqual(2, len(db1))

    def test_persistence_with_iter(self):
        users = [
            ('1000', 'First User'),
            ('1001', 'Second User'),
            ('1002', 'Third User'),
            ('1003', 'Fourth User'),
        ]

        with SqliteAccessControlList.create(self.dbfile) as db1:
            for user in users:
                self.assertTrue(db1.add(*user), msg=repr(user))

        with SqliteAccessControlList.open(self.dbfile) as db2:
            steam_ids = {u[0] for u in users}
            steam_names = {u[1] for u in users}
            for entry in db2:
                self.assertIn(entry.steam_id, steam_ids, msg=repr(entry))
                self.assertIn(entry.name, steam_names, msg=repr(entry))
