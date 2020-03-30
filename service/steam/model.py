"""
Steam API Model

Contains domain definitions of the Steam API.

Author:
    IceDragon <icedragon@quickfox.org>
"""

from typing import NamedTuple, List, NewType

__all__ = [
    'SteamID',
    'SteamErrorPage',
    'SteamUserProfile',
    'SteamGroupMember',
    'SteamMembersPage',
]

SteamID = NewType('SteamID', str)


class SteamErrorPage(NamedTuple):
    """
    Represents an error page from Steam

    Example URL:
        https://steamcommunity.com/id/VasVadumNoWorkie
    """

    message: str

    def __str__(self) -> str:
        return self.message


class SteamUserProfile(NamedTuple):
    """
    Example URL:
        https://steamcommunity.com/id/VasVadum
    """

    url: str
    name: str
    steam_id: SteamID

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other) -> bool:
        return isinstance(other, self.__class__) and other.steam_id == self.steam_id

    def __int__(self) -> int:
        return int(self.steam_id)


class SteamGroupMember(NamedTuple):
    """
    Represents a Steam group member inside a Steam Members Page
    """

    name: str
    rank: str
    profile_url: str

    def __str__(self) -> str:
        return self.name


class SteamMembersPage(NamedTuple):
    """
    Example URL:
        https://steamcommunity.com/groups/DrakeArkServer/members
    """
    group_name: str
    num_members: int
    members: List[SteamGroupMember]

    def __len__(self) -> int:
        return self.num_members
