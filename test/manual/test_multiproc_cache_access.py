from random import randint
from time import sleep
from multiprocessing import Process, current_process
from typing import Callable
from datetime import datetime, timedelta

from service.steam.cache import SqliteSteamProfileCache
from service.steam.model import SteamUserProfile, SteamID

G_TEST_DB = '/tmp/delete-me.db'
G_NUM_WORKERS = 5


def mklog(name: str = '') -> Callable:
    name = name or current_process().name

    def log(msg: str = ''):
        print(f'[{datetime.now()}] {name}: {msg}')

    return log


def main() -> int:
    log = mklog('main')

    log('creating workers...')
    proc_workers = [
        Process(target=p_worker, name=f'WORKER-{i + 1}', args=(G_TEST_DB,), daemon=True)
        for i
        in range(G_NUM_WORKERS)
    ]

    log('starting workers...')
    [p.start() for p in proc_workers]

    log('system running!')
    try:
        while True:
            sleep(5.0)
    except KeyboardInterrupt:
        log('CTRL+C -> shutting down')

    log('awaiting workers....')
    [p.join() for p in proc_workers]

    log('all done')
    return 0


def p_worker(cache_file: str):
    log = mklog()
    log('starting...')

    cache = SqliteSteamProfileCache.open(cache_file)
    log(f'cache opened at {cache_file}')

    try:
        while True:
            rnd_id = randint(10, 99)
            profile = SteamUserProfile(f'https://example.com/profile/{rnd_id}', f'User {rnd_id}', SteamID(str(rnd_id)))

            if cache.get(profile.url) == profile:
                status = f'[H!] {repr(profile)}'
            else:
                cache.put(profile.url, profile, ttl=timedelta(seconds=30))
                status = '[H<]'

            log(f'{status} {profile}')
            sleep(0.1)
    except KeyboardInterrupt:
        log('CTRL+C -> shutting down')
    finally:
        cache.close()

    log('shutdown complete')


if __name__ == '__main__':
    raise SystemExit(main())
