import os
from typing import Any
from unittest import TestCase

from service.steam.model import SteamUserProfile, SteamMembersPage, SteamGroupMember, SteamErrorPage
from service.steam.parsers import SteamUserProfilePageParser, SteamParserError, SteamMembersPageParser, SteamErrorPageParser, \
    NoPageParser


class MyTestCase(TestCase):
    """
    Note:
        This class uses MRO dependency injection
    """

    def parse(self, filename: str) -> Any:
        # noinspection PyUnresolvedReferences
        return super().parse(self.load_asset(filename))

    @staticmethod
    def get_asset_path(*path_elements: str) -> str:
        return os.path.join(os.getcwd(), 'assets', *path_elements)

    def load_asset(self, filename: str) -> bytes:
        with open(self.get_asset_path(filename), 'rb') as f:
            return f.read()

    def test_get_asset_path_is_correct(self):
        self.assertTrue(os.path.exists(self.get_asset_path('steam-members-drake-ark-server.html')), msg=os.getcwd())


class TestSteamMembersPageParser(MyTestCase, SteamMembersPageParser):
    def test_parse(self):
        expected_members = [
            SteamGroupMember('Vas', 'Group Owner', 'https://steamcommunity.com/id/VasVadum'),
            SteamGroupMember('Raziel2212', 'Group Moderator', 'https://steamcommunity.com/id/Raziel2212'),
            SteamGroupMember('Poketkobold', 'Member', 'https://steamcommunity.com/profiles/76561198112492431'),
        ]

        page = self.parse('steam-members-drake-ark-server.html')
        self.assertIsInstance(page, SteamMembersPage)
        self.assertEqual(page.group_name, 'Land of Dragons Ark Server')
        self.assertEqual(page.num_members, 10)
        self.assertEqual(len(page.members), page.num_members)
        for member in expected_members:
            self.assertIn(member, page.members, msg=member)

    def test_parse_non_group(self):
        bad_files = [
            'steam-members-error.html',
            'steam-group-error.html',
        ]

        for filename in bad_files:
            with self.assertRaises(SteamParserError, msg=filename):
                self.parse(filename)


class TestSteamUserProfilePageParser(MyTestCase, SteamUserProfilePageParser):
    def test_parse(self):
        profile = self.parse('steam-profile-vas.html')
        self.assertIsInstance(profile, SteamUserProfile)
        self.assertEqual(profile.url, 'https://steamcommunity.com/id/VasVadum')
        self.assertEqual(profile.steam_id, '76561198023716890')
        self.assertEqual(profile.name, 'Vas')

    def test_parse_non_profile(self):
        bad_files = [
            'steam-members-drake-ark-server.html',
            'steam-members-error.html',
        ]

        for filename in bad_files:
            with self.assertRaises(SteamParserError, msg=filename):
                self.parse(filename)


class TestSteamErrorPageParser(MyTestCase, SteamErrorPageParser):
    def test_parse(self):
        error = self.parse('steam-members-error.html')
        self.assertIsInstance(error, SteamErrorPage)
        self.assertEqual(error.message, 'No group could be retrieved for the given URL.')

    def test_parse_non_error(self):
        bad_files = [
            'steam-members-drake-ark-server.html',
            'steam-profile-vas.html',
        ]

        for filename in bad_files:
            with self.assertRaises(SteamParserError):
                self.parse(filename)


class TestParserBooleanness(MyTestCase):
    def test_regular_parsers_are_true(self):
        true_parsers = [
            SteamUserProfilePageParser,
            SteamMembersPageParser,
            SteamErrorPageParser,
        ]

        for clazz in true_parsers:
            self.assertTrue(clazz, msg=clazz)
            self.assertTrue(clazz(), msg=clazz)

    def test_noparser_evaluates_to_false(self):
        self.assertFalse(NoPageParser())
