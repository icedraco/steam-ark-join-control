"""
Base Definitions - Access Control List (ACL) Module

Author:
    IceDragon <icedragon@quickfox.org>
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import NamedTuple, Optional, Iterator

__all__ = [
    'AclEntry',
    'AbstractAccessControlList',
]


class AclEntry(NamedTuple):
    """
    Represents a single entry within an AbstractAccessControlList
    """

    steam_id: str
    name: str
    added_on: datetime
    last_seen: datetime

    def __str__(self) -> str:
        return self.name


class AbstractAccessControlList(ABC):
    """
    Responsible for maintaining a list user Steam users that are allowed access
    into a system.
    """

    @abstractmethod
    def __len__(self) -> int:
        """
        :return: amount of entries (users) in this access store
        """

    def __iter__(self) -> Iterator[AclEntry]:
        """
        :return: iterator for all entries in this access store
        """
        yield from self.entries()

    @abstractmethod
    def entries(self) -> Iterator[AclEntry]:
        """
        :return: iterator for all entries in this access store
        """

    @abstractmethod
    def find(self, steam_id: str) -> Optional[AclEntry]:
        """
        Find an access store entry (user) based on their Steam ID

        :param steam_id: steam ID to look for
        :return: user entry, or None if no entry for given Steam ID
        """

    @abstractmethod
    def add(self, steam_id: str, name: str, now: Optional[datetime] = None) -> bool:
        """
        Add a new user to the access list

        Note:
            Name duplication is allowed, but not Steam ID duplication! Adding
            an existing Steam ID will not change anything in the data store!

        :param steam_id: user Steam ID
        :param name: user name
        :param now: timestamp for when this user was added
        :return: True if new entry was added; False if Steam ID already exists
        """

    @abstractmethod
    def remove(self, steam_id: str) -> bool:
        """
        Remove an existing user from the access list

        :param steam_id: user Steam ID
        :return: True if record was found and removed; False if no records for this Steam ID
        """

    @abstractmethod
    def update_last_seen(self, steam_id: str, ts: Optional[datetime] = None) -> bool:
        """
        Update the last_seen timestamp for the given user

        :param steam_id: Steam ID of the user
        :param ts: timestamp to update the last seen time to
        :return: True if entry was found and updated; False if entry not found
        """

    @abstractmethod
    def expire(self, min_last_seen: datetime) -> int:
        """
        Remove all users from the access list who were last seen earlier than
        min_last_seen time.

        :param min_last_seen: lower limit below which to expire entries
        :return: amount of entries expired
        """
