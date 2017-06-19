# RoleKeeper
Discord bot for Warface Tournaments


## About

RoleKeeper is a bot specificly designed to handle Warface Discord tournament servers.
It auto-assigns roles of team captains based on an CSV file (exported from esports site).
From there, it also features the creation of chat channels used for guided pick & ban sequence.

It was successfuly used in the [June Fast Cup](https://esports.my.com/tournament/5/bracket/) (JFC) with over 100 teams,
first Warface Tournament ever ran on Discord.

## Demo

[![](https://img.youtube.com/vi/VnQ-jv2clgI/0.jpg)](https://www.youtube.com/watch?v=VnQ-jv2clgI "Click to play on YouTube.com")

## Discord usage

The bot has a chat-command interface.
A command starts with a `!` (bang sign) followed by the command name, a space and then the command arguments.

### Team captains commands

A team captain is a member with the role `Team Captains`.

 - `!ban map`, bans map `map` from the map list available in the pick & ban sequence. `map` is case-insensitively matched at 80% with available maps;
 - `!pick map`, same as `!ban` excepts it is used to pick a map (best-of-3 only);
 - `!side side`, chooses the side, either attack or defense.

**Note**: The above commands are only available in a match chat channel created by the bot itself.

### Referees commands

A judge referee is a member with Discord permission `manage roles`.

 - `!say #channel message...`, makes bot say `message...` in `channel`. Note that `channel` has to be a valid chat-channel mention;
 - `!bo1 @teamA @teamB` (Both arguments have to be **existing** Discord role mentions);
   1. Creates a chat room named `match_teamA_vs_teamB`;
   2. Gives permissions to `teamA` and `teamB` roles to see the chat room;
   3. Starts a best-of-1 map pick & ban sequence;
   4. Team captains are invited to type `!ban map`, `!pick map` or `!side side` one after the other;
   5. Prints the summary of elected maps and sides;
 - `!bo3 @teamA @teamB`, same as `!bo1` excepts it creates a best-of-3 chat channel;
 - `!ban`, `!pick` and `!side` commands (see [Team captains](#team-captains)) are available to
   referees so that they can test or bridge team captains choice if they are not in Discord server.

### Admins commands

An admin is someone that has access to the file `members.csv` and bot launch.

 - `!refresh`, will crawl the server member list again to find members without any role and assign one if a team captain is found;
 - `!create_teams`, based on `members.csv`, create all the team roles in advance (optional).
   This can be helpful when `members.csv` is incomplete and contains invalid Discord ID, but the teams are, allowing manual role-assigning by a referee.

## How to install

This project requires **Python >=3.4** as it uses extensively the Python [Discord API](https://github.com/Rapptz/discord.py).
It is recommended to run it in a Python `virtualenv` and install dependencies with `pip`.

1. Clone the project
```
$ git clone https://github.com/Levak/RoleKeeper.git
$ cd RoleKeeper
```

2. Create a virtual env
```
$ python -m venv env
$ source ./env/bin/activate
(venv) $ pip install -r requirements.txt
```

3. Go to [Discord application registration page](https://discordapp.com/developers/applications/me#top) and create an app with a bot.

4. Edit `config.py` and fill `token` variable with the _APP BOT USER_ token:
```
token = "--redacted--"
```

5. Invite the bot to the Discord server (replace `BOT_CLIENT_ID` with the one from the bot app page)
```
https://discordapp.com/oauth2/authorize?client_id=BOT_CLIENT_ID&scope=bot&permissions=402656272
```

This link should give the following permissions:
 - Manage roles;
 - Manage nicknames;
 - Manage channels;
 - Read/Send messages.

**Note**: Make sure the bot role is just below the admin role (above the roles it manages)

6. Create the mandatory roles in Discord server:
 - `Group A` to `Group F` (if more groups are needed, edit `rolekeeper.py` line 76);
 - `Team Captains`;
 - `WF_mods referees`;
 - `Referees`;

**Note**: Make sure these roles are below `RoleKeeper` role in Discord role list so that it can manage them.

7. Create the `members.csv` file (see [Member list](#member-list) section)

8. Run RoleKeeper
```
(venv) $ python ./main.py
```

Once everything is setup, the only things to repeat are steps 7 and 8.

## Member list

RoleKeeper heavily relies on the `members.csv` file that contains all team captains Discord ID, team name, group and IGN.
Based on this file, the bot is able to rename, create the team role, and assign it to the team captain whenever he joins the Discord server.

The `members.csv` file has to be in the following format (comma separated values, # for comments):
```
#discord,team,nickname,group
ezpz#4242,Noobs,AllProsAboveMe,A
gg#2424,Pros,xX-AtTheTop-Xx,B
noob42#777,PGM,SixSweat,C
```

The above member list makes RoleKeeper wait for any server join from `ezpz#4242`, `gg#2424` and `noob42#777` on the Discord server he is invited in.

For instance, once `ezpz#4242` joins the server, he will be:
 - Renamed to `AllProsAboveMe`;
 - Assigned roles `Team Captains`, `Group A` and `Noobs team`.

**Note**: Automatic role assignement is made only on members that do not have _any_ role.
If for some reason a member has extra roles, he will not be processed and will have to be handled manually by a referee.

## Recommandations

- It is recommanded to create a chat channel `#bot_commands` that both bot and referees can see and talk in order to enter all bot commands.
  It will ease command tracking and prevent spam in lobby channels.

- Groups are useful to separate teams among referees. A referee handles one and only one group,
  until the brackets merge. At this point, some referees lose the responsability of their group.
  It is recommanded to create chat channels like `#group_a` where members with role `Group A` are able to read/send messages.
  When the groups merge, the team captains have to be manually assigned their new group role (by referee).

## TODO

- [ ] Reparse `members.csv` or provide a more dynamic way of adding team captains at the _last-minute_
- [ ] Cross-server non-interference (When the bot is invited in several Discord servers, it will run on the same member list)
- [ ] Take `members.csv` as parameter
- [ ] Configurable role names and list
- [ ] Configurable map list
- [ ] Handle unicode team names in order to create valid Discord chat channel names.
- [ ] (idea) Import `members.csv` directly from esports website
- [ ] (idea) Automatically launch `!bo1`/`!bo3` based on info from esports website
- [ ] (idea) Handle match result gathering (with vote from both teams)
