import json
import os
import signal
from queue import Full
from time import sleep
from datetime import datetime, timedelta
from typing import Callable, Tuple, Optional, Dict, Set
from multiprocessing import current_process, Queue, Process, Pool

from .acl import SqliteAccessControlList
from .httpservice import start_http_service
from .steam.api import SteamApi, SteamApiError
from .steam.cache import SqliteSteamProfileCache
from .steam.model import SteamMembersPage, SteamID, SteamUserProfile

CONFIG_FILE = 'config.json'

# amount of seconds to wait after unsuccessful Steam member request
G_RETRY_SECS = 10.0

# how many seconds to wait before dropping pending group data?
# (this time should never trip unless there is a serious bug!)
G_UPDATE_QUEUE_TIMEOUT = 5.0

# how many times should we attempt to resolve a single profile into a Steam ID
# before declaring fatal failure? (used to retry failed HTTP requests)
G_MAX_RESOLVE_ATTEMPTS = 3

# how many processes (profile HTTP requests) should we maintain at the same
# time?
G_NUM_RESOLVER_PROCESSES = 4

# how long should a cache entry stay on disk without being accessed before
# expiring?
G_CACHE_TTL = timedelta(days=7)

# address for the HTTP service to listen on
#
# IMPORTANT:
# IF YOU CHANGE THIS FROM 'localhost', TAKE CARE TO PROVIDE SUFFICIENT SECURITY
# FOR THE SERVICE!
#
# G_LISTEN_HOSTNAME = ''  # listen on all addresses
G_LISTEN_HOSTNAME = 'localhost'


def main() -> int:
    log = mklog('main')

    log('reading configuration...')
    config = get_config()
    group_url: str = config['group_url']
    group_id: str = group_url.split('/')[-1]  # group_url suffix
    interval: int = config['group_poll_interval_secs']
    cache_file: str = config['cache_file']
    acl_file: str = config['acl_file']
    service_port: int = config['service_port']

    auto_allow: Dict[str, str] = config['allowed']
    auto_deny: Dict[str, str] = config['denied']

    log('preparing queues...')
    q_group_updates = Queue(1)
    q_resolved_profiles = Queue(1)

    log('preparing processes...')
    proc_poller = Process(
        target=p_group_poller,
        name='POLLER',
        args=(q_group_updates, group_id, interval),
        daemon=True)

    proc_resolver = Process(
        target=p_resolver,
        name='RESOLVER',
        args=(q_group_updates, q_resolved_profiles, cache_file),
        daemon=False)

    proc_acl_updater = Process(
        target=p_acl_updater,
        name='ACL-UPDATER',
        args=(q_resolved_profiles, acl_file, auto_allow, auto_deny),
        daemon=True)

    log('spawning processes...')
    proc_poller.start()
    proc_resolver.start()
    proc_acl_updater.start()

    log('waiting for ACL database file creation...')
    while not os.path.isfile(acl_file):
        sleep(1.0)

    log(f'starting HTTP service on port {service_port}')
    acl = SqliteAccessControlList.open(acl_file)
    start_http_service(
        addr=(G_LISTEN_HOSTNAME, service_port),
        is_allowed=lambda steam_id: acl.find(steam_id) is not None,
    )

    log('shutdown process...')

    log('awaiting sub-process shutdown...')
    for subproc in [proc_poller, proc_resolver, proc_acl_updater]:
        log(f' > {subproc.name}')
        subproc.join()

    log('SHUTDOWN COMPLETE')
    return 0


# region Sub-Processes

def p_group_poller(q_group_updates: Queue, group_id: str, interval: int):
    """
    Group Poller Process

    Responsible for periodically polling a Steam group and sending all its
    member info through `q_group_updates` queue to the next process...

    Note:
        q_group_updates will receive a List[SteamGroupMember] object where ALL
        the current group members are listed! This is a complete list and
        anyone not found on it can be assumed to NOT be inside the group!

    :param q_group_updates: queue to put group updates into
    :param group_id: ID of the Steam group we are polling (found at the end of group URL)
    :param interval: interval (in seconds) between group checks
    """
    assert interval >= 30, f'interval is too short ({interval} secs)'

    log = mklog()
    log('starting...')
    num_requests = 0

    api = SteamApi(on_error=log_error)

    try:
        while True:
            num_requests += 1

            try:
                members_page = api.members(group_id)
                profile_urls = [member.profile_url for member in members_page.members]
                q_group_updates.put(profile_urls, timeout=G_UPDATE_QUEUE_TIMEOUT)
                log(f'{len(members_page)} members found and sent for update')
            except SteamApiError as ex:
                log(f'API ERROR: {ex}')
                log(f'retrying in {G_RETRY_SECS} seconds...')
                sleep(G_RETRY_SECS)
                continue
            except Full:
                log(f'WARNING: q_group_updates queue is NOT READY! STATUS DATA WAS LOST!')
                # even if the queue will be released at some point, this data
                # may quickly become stale and outdated - it's best to re-fetch

            log(f'sleeping {interval} secs...')
            sleep(interval)
    except KeyboardInterrupt:
        log('CTRL+C PRESSED -> SHUTTING DOWN...')

    log(f'shutdown complete: {num_requests} requests made...')


def init_resolve_one_worker():
    # block SIGINT to avoid KeyboardInterrupt exceptions
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def resolve_one(profile_url: str) -> Tuple[str, Optional[SteamUserProfile], int]:
    """
    Resolve a single Steam user profile

    Note:
        None is returned instead of a Steam ID if the lookup consistently
        failed to obtain a proper profile page for this Steam member.

    :param profile_url: member's Steam profile URL
    :return: (profile_url, steam_profile|None, num_requests_made)
    """
    log = mklog()
    api = SteamApi(on_error=log_error)
    for attempt in range(G_MAX_RESOLVE_ATTEMPTS):
        def log_ex(msg: str = ''):
            log(f'[{attempt + 1}/{G_MAX_RESOLVE_ATTEMPTS}] {msg}')

        try:
            log_ex(f'resolving profile {profile_url}')
            profile = api.profile(profile_url)
            log_ex(f'resolved: {profile_url} -> {repr(profile)}')
            return profile_url, profile, attempt + 1
        except SteamApiError as ex:
            log_ex(f'ERROR: {ex} (profile: {profile_url})')

    log(f'WARNING: MAX RESOLVE ATTEMPTS REACHED; PROFILE: {profile_url}')
    return profile_url, None, G_MAX_RESOLVE_ATTEMPTS


def p_resolver(q_group_updates: Queue, q_resolved_profiles: Queue, profile_cache_file: str):
    """
    Steam Profile Resolver Process

    Responsible for resolving lists of profile URLs into
    {profile_url: SteamUserProfile} dictionaries using Steam API and local disk
    cache.

    :param q_group_updates: [IN] List[str] - list of profile URLs from a Steam group member list
    :param q_resolved_profiles: [OUT] Dict[str, SteamUserProfile] - {profile_url: steam_user_profile} units
    :param profile_cache_file: file path to the local profile cache
    """
    log = mklog()
    log('starting...')
    num_outbound_requests = 0
    num_cache_hits = 0

    cache = SqliteSteamProfileCache.open(profile_cache_file)
    cache_ttl = G_CACHE_TTL

    resolver_pool = Pool(G_NUM_RESOLVER_PROCESSES, init_resolve_one_worker)
    try:
        while True:
            # get initial profiles from cache
            profiles: Dict[str, Optional[SteamUserProfile]] = \
                {
                    profile_url: cache.get(profile_url)
                    for profile_url
                    in q_group_updates.get()
                }

            # profiles not cached yet are "missing"
            missing_profiles = [profile_url for profile_url, profile in profiles.items() if not profile]

            num_cache_hits += len(profiles) - len(missing_profiles)

            # resolve remaining profiles via Steam API in parallel
            missed_profile_urls = set()
            for profile_url, profile, num_attempts in resolver_pool.map(resolve_one, missing_profiles):
                if profile:
                    profiles[profile_url] = profile
                    cache.put(profile_url, profile, cache_ttl)
                else:
                    missed_profile_urls.add(profile_url)

                num_outbound_requests += num_attempts

            # disqualify this work unit if there are still profiles missing
            if missed_profile_urls:
                log(f'WARNING: RESOLVE FAILED ({len(missed_profile_urls)} PROFILES MISSING)')
                for profile_url in missed_profile_urls:
                    log(f'MISSING PROFILE: {profile_url}')
            else:
                q_resolved_profiles.put(profiles)

            # work unit complete -> expire entries
            num_expired = cache.expire()
            if num_expired > 0:
                log(f'expired {num_expired} cache entries')

    except KeyboardInterrupt:
        log('CTRL+C -> SHUTTING DOWN')
    finally:
        resolver_pool.close()
        resolver_pool.join()
        cache.close()

    log(f'shutdown complete: {num_outbound_requests} API requests ({num_cache_hits} cache hits)')


def p_acl_updater(
        q_resolved_profiles: Queue,
        acl_file: str,
        auto_allow: Optional[Dict[str, str]] = None,
        auto_deny: Optional[Dict[str, str]] = None,
):
    log = mklog()
    log(f'starting ({len(auto_allow)} auto-allow and {len(auto_deny)} auto-deny entries)...')
    num_updates = 0

    # stabilize auto-allow and auto-deny sets
    auto_allow_ids: Set[SteamID] = {SteamID(steam_id) for steam_id in (auto_allow or {}).values()}
    auto_deny_ids: Set[SteamID] = {SteamID(steam_id) for steam_id in (auto_deny or {}).values()}
    auto_deny_ids.difference_update(auto_allow_ids)  # auto-allow prevails
    auto_ids: Set[SteamID] = auto_allow_ids.union(auto_deny_ids)

    # ACL initialization
    acl = SqliteAccessControlList.open(acl_file, create=True)
    for name, steam_id_str in (auto_allow or {}).items():
        acl.add(steam_id_str, name, added_on=datetime.now(), last_seen=datetime.now())

    for steam_id in auto_deny_ids:
        acl.remove(steam_id)

    try:
        while True:
            profiles: Dict[str, SteamUserProfile] = q_resolved_profiles.get()
            now = datetime.now()

            # prevent auto-allow members from expiring
            [acl.update_last_seen(steam_id, now) for steam_id in auto_allow_ids]

            # remove auto-allow and auto-deny profiles:
            #  auto-allow profiles were added at INIT and updated just now
            #  auto-deny  profiles were removed at INIT
            auto_urls = {
                profile_url
                for profile_url, profile
                in profiles.items()
                if profile.steam_id in auto_ids
            }

            for profile_url in auto_urls:
                del profiles[profile_url]

            # add/update what's left
            log(f'{len(profiles)} dynamic profiles updated')
            for profile_url, profile in profiles.items():
                updated = acl.update_last_seen(profile.steam_id, ts=now)
                if not updated:
                    acl.add(profile.steam_id, profile.name, added_on=now, last_seen=now)

            # expire what wasn't added/updated by previous steps
            num_expired = acl.expire(min_last_seen=now)
            if num_expired > 0:
                log(f'expired {num_expired} from access control list')
    except KeyboardInterrupt:
        log('CTRL+C PRESSED -> SHUTTING DOWN')
    finally:
        acl.close()

    log(f'shutdown complete: {num_updates} ACL updates performed')


# endregion


# region Helper Functions

def mklog(name: str = '') -> Callable:
    name = name or current_process().name

    def log(msg: str = ''):
        print(f'[{datetime.now()}] {name}: {msg}')

    return log


def print_members(page: SteamMembersPage):
    log = mklog('main')
    log('--- Members -----------------------------')
    log(f' * Group: {page.group_name}')
    log(f'          {page.num_members} page')
    log()

    max_name_len = max(len(member.name) for member in page.members)

    fmt = '[%%16s] %%-%ds - %%s' % max_name_len
    for member in page.members:
        log(fmt % (member.rank, member.name, member.profile_url))

    log()


def get_config(filename: str = CONFIG_FILE) -> dict:
    with open(filename, 'r') as f:
        return json.load(f)


def log_error(url: str, content: bytes, msg: str):
    with open('error.html', 'wb') as f:
        f.write(bytes(f'URL: {url}\n', 'utf-8'))
        f.write(bytes(f'MSG: {msg}\n\n', 'utf-8'))
        f.write(content)


# endregion


if __name__ == '__main__':
    raise SystemExit(main())
