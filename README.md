# Steam ARK Join Control

```
This project is NOT actively maintained and there are currently no plans to make
it so!
```


## Overview
This project provides an HTTP service compatible with the
[ARK Join Control](https://steamcommunity.com/sharedfiles/filedetails/?id=949422684)
mod for the "ARK: Survival Evolved" game, allowing all members of a provided Steam
group to enter the ARK server while disallowing everyone else. 


## Features
 * Local caching of Steam Profile URL to Steam ID mappings
 * Static "always allow" configuration for admins
     * Currently requires service restart (via CTRL+C)
 * Static "always deny" configuration for suspended members
     * Currently requires service restart (via CTRL+C)


## Installing
 * `python3.7 -m pip install -r requirements.txt`
 * edit `config.json` to fit your configuration


## Running
 * `python3.7 -m service` 


## Testing
 * `curl "http://localhost?steam_id=<steam_id_here>"`


## Tech Stack
 * [requests](https://pypi.org/project/requests/)
 * [lxml](https://lxml.de/)
 * SQLite3
 * Python3.7
