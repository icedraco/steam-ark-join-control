"""
Steam Page Parsers - Steam API

This module facilitates information extraction from raw HTML within relevant
Steam pages.

Author:
    IceDragon <icedragon@quickfox.org>
"""

from abc import ABC, abstractmethod
from typing import Any, List

import json
import lxml.html

from service.steam.model import SteamGroupMember, SteamUserProfile, SteamMembersPage, SteamErrorPage

__all__ = [
    'SteamParserError',
    'AbstractParser',
    'SteamMembersPageParser',
    'SteamUserProfilePageParser',
    'SteamErrorPageParser',
    'NoPageParser',
]


class SteamParserError(Exception):
    pass


class AbstractParser(ABC):
    def parse(self, html: bytes) -> Any:
        """
        :param html: raw HTML content
        :return: parsed model object containing all extracted information
        """
        if not self._is_valid_html(html):
            raise SteamParserError('unsupported page format')

        doc = lxml.html.fromstring(html)

        if not self._is_valid_doc(doc):
            raise SteamParserError('unsupported page format')

        return self._parse(doc)

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def _is_valid_html(self, html: bytes) -> bool:
        """
        Note:
            Override this method in order to validate parsed HTML

        :param html: raw html to check
        :return: True if document is supported by parser; False otherwise
        """
        return True

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def _is_valid_doc(self, doc: lxml.html.HtmlElement) -> bool:
        """
        Note:
            Override this method  in order to validate parsed LXML document

        :param doc: lxml document to check
        :return: True if document is supported by parser; False otherwise
        """
        return True

    @abstractmethod
    def _parse(self, doc: lxml.html.HtmlElement) -> Any:
        pass


class SteamMembersPageParser(AbstractParser):
    """
    Responsible for parsing Steam group page pages.

    Example URL:
        https://steamcommunity.com/groups/DrakeArkServer/members
    """

    DEFAULT_RANK = 'Member'

    def _parse(self, doc: lxml.html.HtmlElement) -> SteamMembersPage:
        """
        :param doc: lxml document to parse
        :return: steam group information extracted from `html`
        :raises SteamParserException: unsupported format or not a Steam group page
        """
        return SteamMembersPage(
            self._parse_group_name(doc),
            self._parse_num_members(doc),
            self._parse_members(doc),
        )

    @staticmethod
    def _parse_group_name(doc: lxml.html.HtmlElement) -> str:
        name_xpath = doc.xpath('//div[contains(@class,"grouppage_header_name")]/text()')
        if not name_xpath:
            raise SteamParserError('cannot find group_header_name')

        return name_xpath[0].strip()

    @staticmethod
    def _parse_num_members(doc: lxml.html.HtmlElement) -> int:
        membercount_xpath = doc.xpath(
            '//div[contains(@class,"membercount")]'
            '/*/span[contains(@class,"count")]'
            '/text()')

        if not membercount_xpath:
            raise SteamParserError('cannot find membercount')

        try:
            return int(membercount_xpath[0].strip())
        except ValueError:
            raise SteamParserError(f'membercount is not numeric: {repr(membercount_xpath)}')

    @classmethod
    def _parse_members(cls, doc: lxml.html.HtmlElement) -> List[SteamGroupMember]:
        ranks = [
            it.attrib.get('title', 'UNKNOWN')
            for it
            in doc.xpath('//div[contains(@class,"rank_icon")]')
        ]

        if not ranks:
            raise SteamParserError('cannot find rank icons')

        members_xpath = doc.xpath('//a[contains(@class,"linkFriend")]')
        if not members_xpath:
            raise SteamParserError('cannot find linkFriend items')

        if len(ranks) > len(members_xpath):
            raise SteamParserError(
                f'there are more ranks [{len(ranks)}] '
                f'than page [{len(members_xpath)}]')
        else:
            # fill with empty ranks so that the two lists match
            ranks.extend([''] * (len(members_xpath) - len(ranks)))

        return [
            SteamGroupMember(
                name=x.text.strip(),
                rank=rank or cls.DEFAULT_RANK,
                profile_url=x.attrib.get('href', ''),
            )
            for x, rank
            in zip(members_xpath, ranks)
        ]

    def _is_valid_html(self, html: bytes) -> bool:
        return b'<!-- member list -->' in html \
               and b'STEAM GROUP' in html


class SteamUserProfilePageParser(AbstractParser):
    """
    Responsible for parsing Steam user profile pages.

    Example URL:
        https://steamcommunity.com/id/VasVadum
        https://steamcommunity.com/profiles/76561198112492431
    """

    def _parse(self, doc: lxml.html.HtmlElement) -> SteamUserProfile:
        """
        :param doc: lxml document to parse
        :return: steam user profile information extracted from `html`
        :raises SteamParserException: unsupported format or not a Steam user profile page
        """
        profile_script = [
            script_text
            for script_text
            in doc.xpath('//script/text()')
            if 'g_rgProfileData = ' in script_text
        ]

        if not profile_script:
            raise SteamParserError('cannot find g_rgProfileData segment')

        script_text = profile_script[0].strip()

        # extract profile_data from within javascript
        clean_script = script_text[script_text.find('{'):script_text.find('};') + 1]
        profile_data = json.loads(clean_script)

        # ensure profile_data has all required keys
        missing_keys = {'url', 'personaname', 'steamid'} - profile_data.keys()
        if missing_keys:
            raise SteamParserError(f'missing keys in profile_data: {repr(missing_keys)}')

        return SteamUserProfile(
            url=profile_data['url'].rstrip('/'),
            name=profile_data['personaname'],
            steam_id=profile_data['steamid'],
        )

    def _is_valid_html(self, html: bytes) -> bool:
        return b'g_rgProfileData = {' in html


class SteamErrorPageParser(AbstractParser):
    def _parse(self, doc: lxml.html.HtmlElement) -> SteamErrorPage:
        h3 = doc.xpath('//h3/text()')
        if not h3:
            raise SteamParserError('cannot find h3 tags for error message')

        return SteamErrorPage(str(h3[0].strip()))

    def _is_valid_html(self, html: bytes) -> bool:
        return b'<h2>Error</h2>' in html


class NoPageParser(AbstractParser):
    """
    Default parser that always returns None.

    Used in case none of the parsers are compatible with the given format
    """

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def _parse(self, doc: lxml.html.HtmlElement) -> None:
        return None

    def __bool__(self) -> bool:
        return False
