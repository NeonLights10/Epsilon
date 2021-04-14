# Epsilon
![latest release](https://img.shields.io/badge/latest%20release-0.4.0-brightgreen.svg)

Epsilon is a multipurpose discord bot written in Python using the discord.py library.
Supports Python 3.5+

## Installation
* Ensure you have all requirements by running `pip install -r requirements.txt`. See notice for extra steps.
* Rename the file `sample.config.json` to `config.json` in the root directory and modify it as needed.
* Ensure that you have set up a mongodb atlas cluster and have the login info. This will go in `config.json`.

## Support
Neon#5555 on discord

## Features
* Server specific modmail
* Reaction based self role assignment
* Strike/ban system with record lookup
* Logging capabilities
* Timezone conversion
* Fun commands
* And more coming soon...

### Notice
This bot makes use of the experimental [discord-ext-menus](https://github.com/Rapptz/discord-ext-menus) project.
To install this, you must run this command: `python -m pip install -U git+https://github.com/Rapptz/discord-ext-menus` as it is not on PyPI yet.
