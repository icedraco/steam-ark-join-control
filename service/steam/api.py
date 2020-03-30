"""
Steam API

Limited API implementation for extracting data from Steam web pages

Author:
    IceDragon <icedragon@quickfox.org>
"""

from typing import Callable

import requests

from .model import SteamUserProfile, SteamErrorPage, SteamMembersPage
from .parsers import SteamUserProfilePageParser, SteamMembersPageParser, SteamErrorPageParser, SteamParserError

__all__ = [
    'SteamApi',
    'SteamApiError',
]

DO_NOTHING: Callable[[str, bytes, str], None] = lambda url, content, error_msg: None


class SteamApiError(Exception):
    """
    Represents an error obtained through calls to SteamApi
    """


class SteamApi:
    """
    A limited user-facing API to the Steam website
    """

    PROFILE_PAGE_PARSER = SteamUserProfilePageParser()
    MEMBERS_PAGE_PARSER = SteamMembersPageParser()
    ERROR_PAGE_PARSER = SteamErrorPageParser()

    def __init__(self, on_error: Callable[[str, bytes, str], None] = DO_NOTHING):
        session = requests.session()
        session.headers['User-Agent'] = 'SteamApiX/1.0'
        self.session = session
        self.on_error = on_error

    def profile(self, profile_url: str) -> SteamUserProfile:
        """
        :param profile_url: Steam profile URL
        :return: Steam user profile info
        :raises SteamApiError: could not obtain/parse profile page at given URL
        """
        try:
            return self.PROFILE_PAGE_PARSER.parse(self._get(profile_url))
        except SteamParserError as ex:
            raise SteamApiError(f'({profile_url}) {str(ex)}')

    def members(self, group_id: str) -> SteamMembersPage:
        """
        :param group_id: Steam group ID (used in the URL)
        :return: member page
        :raises SteamApiError: could not obtain member page
        """
        return self._members_url(f'https://steamcommunity.com/groups/{group_id}/members')

    def _members_url(self, members_url: str) -> SteamMembersPage:
        """
        :param members_url: Steam members page URL
        :return: member page
        :raises SteamApiError: could not obtain member page
        """
        try:
            return self.MEMBERS_PAGE_PARSER.parse(self._get(members_url))
        except SteamParserError as ex:
            raise SteamApiError(f'({members_url}) {str(ex)}')

    def _get(self, url: str) -> bytes:
        result = self.session.get(url)
        content = result.content

        def error(msg: str):
            self.on_error(url, content, msg)
            raise SteamApiError(f'({url}) {msg}')

        if not result.ok:
            error(f'Bad HTTP result ({result.status_code} {result.reason})')

        content_type = result.headers.get('Content-Type', '')
        if not content_type.startswith('text/html'):
            error(f'Unsupported content type: {content_type}')

        try:
            page = self.ERROR_PAGE_PARSER.parse(result.content)
            assert isinstance(page, SteamErrorPage), repr(page)
            error(page.message)
        except SteamParserError as ex:
            # this is not an error message -> return the data
            return result.content
