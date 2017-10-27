# RoleKeeper
Discord bot for Warface Tournaments


## About

RoleKeeper is a bot specificly designed to handle Warface Discord tournament
servers. Its main features are:
 - Auto-assignment of team captain roles based on an CSV file
   (exported from esports site);
 - Creation of chat channels used for guided pick & ban sequence;
 - Broadcast of events from and to match chat channels (match room
   created, streamed match, pick&ban results).

It was successfuly used in the
[June Fast Cup](https://esports.my.com/tournament/5/bracket/) (JFC) with over
100 teams, first Warface Tournament ever ran on Discord.

## Demo

[![](https://img.youtube.com/vi/VnQ-jv2clgI/0.jpg)](https://www.youtube.com/watch?v=VnQ-jv2clgI
"Click to play on YouTube.com")

## Discord usage

The bot has a chat-command interface. A command starts with a `!` (bang sign)
followed by the command name, a space and then the command arguments.

### Team captains commands

A Team captain is a member with the role `roles/captain` defined in `config.json`

 - `!ban map`, bans map `map` from the map list available in the pick & ban
   sequence. `map` is case-insensitively matched at 80% with available maps;
 - `!pick map`, same as `!ban` excepts it is used to pick a map (best-of-3
   only);
 - `!side side`, chooses the side, either attack or defense.

**Note**: The above commands are only available in a match chat channel
  created by the bot itself.

### Referees commands

A judge referee is a member with the role `roles/referee` defined in `config.json`

 - `!say #channel message...`, makes bot say `message...` in `channel`. Note
   that `channel` has to be a valid chat-channel mention;
 - `!bo1 @teamA @teamB` (Both arguments have to be **existing** Discord role
   mentions);
   1. Creates a chat room named `match_teamA_vs_teamB`;
   2. Broadcast the fact the channel was created in rooms
      `servers/.../rooms/match_created` defined in `config.json`;
   3. Gives permissions to `teamA` and `teamB` roles to see the chat room;
   4. Starts a best-of-1 map pick & ban sequence (6xban, pick, side);
   5. Team captains are invited to type `!ban map`, `!pick map` or `!side
      side` one after the other;
   6. Prints the summary of elected maps and sides;
   7. Broadcast the results in rooms `servers/.../rooms/match_starting`
      defined in `config.json`.
 - `!bo2 @teamA @teamB`, same as `!bo1` excepts it creates a best-of-2 chat
   channel (ban, ban, pick, pick, side);
 - `!bo3 @teamA @teamB`, same as `!bo1` excepts it creates a best-of-3 chat
   channel (ban, ban, pick, pick, ban, ban, pick, side);
 - `!add_captain @captain teamA nickname group`, add captain to the captain
   database, assign the captain, team and group roles and rename the captain;
 - `!remove_captain @captain`, remove a captain from the captain database,
   reset its nickname, remove the assigned roles.
 - `!ban`, `!pick` and `!side` commands (see [Team captains](#team-captains))
   are available to referees so that they can test or bridge team captains
   choice if they are not in Discord server.

### Streamers commands

A streamer is a member with the role `roles/streamer` defined in `config.json`

 - `!stream match_id`, will broadcast the information that `match_id` will be
   streamed by the one executing the command. Rolekeeper provides `match_id`
   to channels `servers/[server]/rooms/match_created` which streamers should
   have access to.

### Admins commands

An admin is a member with Discord permission `manage roles`, someone that has
access to the `config.json` file and bot launch.

 - `!refresh`, will crawl the server member list again to find members without
   any role and assign one if a team captain is found. **CAUTION**: Do not use
   this command if someone already used `!add_captain` or `!remove_captain` as
   it will reset captain database and forget about the new ones;
 - `!create_teams`, [DEPRECATED] based on `members.csv`, creates all the team
   roles in advance (optional). This can be helpful when `members.csv` is
   incomplete and contains invalid Discord ID while teams are correct,
   allowing manual role-assigning by a referee;
 - `!members`, will generate a CSV of all members in the Discord server;
 - `!stats`, will generate a CSV of pick&bans statistics;
 - `!wipe_teams`, will delete all team-captain roles known from captain
   database, remove their captain and group roles, reset their nickname;
 - `!wipe_matches`, will remove all match chat channels created;
 - `!wipe_messages #channel`, will remove all non-pinned messages in
   `channel`. Note that `channel` has to be a valid chat-channel mention.

## Usage

Rolekeeper requires Python >=3.6. Entrypoint is `main.py`, which takes an
optional 1st argument, the configuration file. By default, no argument given
means Rolekeeper will look for the file `config.json`.

Example:
```
~/rolekeeper/$ ./main.py config_mr.py
```

or:
```
~/rolekeeper/$ ./main.py
Using default configuration file path: `config.json`
...
```

## How to install

This project requires **Python >=3.6** as it uses extensively the Python
[Discord API](https://github.com/Rapptz/discord.py). It is recommended to run
it in a Python `virtualenv` and install dependencies with `pip`.

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

3. Go to
   [Discord application registration page](https://discordapp.com/developers/applications/me#top)
   and create an app with a bot.

4. Edit `config.json` and:
   1. Fill `app_bot_token` with the _APP BOT USER_ token;
   2. Change or add a discord server with its member list;

**config.json**
```
...
    "app_bot_token" = "--redacted--",
...
    "servers" : {
        "My Discord server": {
            "captains": "members.csv",
            ...
        }
    },
...
```

5. Invite the bot to the Discord server (replace `BOT_CLIENT_ID` with the one
   from the bot app page)

```
https://discordapp.com/oauth2/authorize?client_id=BOT_CLIENT_ID&scope=bot&permissions=402705488 
```

This link should give the following permissions:
 - Manage roles;
 - Manage nicknames;
 - Manage channels;
 - Read/Send messages.

**Note**: Make sure the bot role is just below the admin role (above the roles
  it manages)

6. Create the mandatory roles in the Discord server (names can be changed
   in `config.json`):
 - `Group xxxx` _where xxxx are the group IDs present in `members.csv`
   (e.g. `A` through `F`)_;
 - `Team Captains`;
 - `Referees`;
 - `Streamers`.

**Note**: Make sure these roles are below `RoleKeeper` role in Discord role
  list so that it can manage them.

7. Create the `members.csv` file (see [Member list](#member-list) section)

8. Run RoleKeeper
```
(venv) $ python ./main.py
```

Once everything is setup, the only things to repeat are steps 7 and 8.

## Configuration

The bot is configurable at startup with the file `config.json`. This file
defines all the variable parameters supported by RoleKeeper, such as role
names, member list path per servers, broadcast lists, etc.

Here is an example of configuration file:

**config.json**
```
{
    "app_bot_token": "--redacted--",

    "roles": {
        "referee": "Referees",
        "captain": "Team Captains",
        "streamer": "Streamers",
        "group": "Group {}",
        "team": "{} team"
    },

    "servers": {
        "June Fast Cup": {
            "db": "jfc",
            "captains": "members.csv",
            "maps": [ "Yard", "D-17", "Factory", "District", "Destination", "Palace", "Pyramid" ],
            "rooms": {
                "match_created": [ "jfc_streamers" ],
                "match_starting": [ "bot_referees", "jfc_streamers" ]
            }
        },

        "JFCtest": {
            "captains": "members_test.csv",
            "maps": [ "Lorem", "Ipsum", "Dolor", "Sit", "Amet", "Consectetur", "Adipiscing" ],
            "rooms": {
                "match_created": [ "streamers" ],
                "match_starting": [ "referees", "streamers" ]
            }
        }
    }
}
```

### `app_bot_token`

**String**. Token for the bot. Go to
[Discord application page](https://discordapp.com/developers/applications/me#top),
click on your application, then create a bot for the application and expand
the _APP BOT TOKEN_.

### `roles/referee`

**String**. Name of the role used for Judge referees.

### `roles/captain`

**String**. Name of the role used for Team captains.

### `roles/streamer`

**String**. Name of the role used for Streamers.

### `roles/group`

**String**. Template name used for the Team Groups. Use `{}` to indicate the
  location where the actual group ID will be in the role name.

### `roles/team`

**String**. Template name used for the Team names. Use `{}` to indicate the
  location where the actual team name will be in the role name.

### `servers/.../db`

**String**. Name of the persistent storage DB on the disk (unique per server).

### `servers/.../captains`

**String**. Path to the member list file for that server.

### `servers/.../maps`

**List of String**. All the available maps for the pick & ban sequences for
  that server. Must contain exactly 7 elements.

### `servers/.../rooms/match_created`

**List of String**. Channels that will receive match creation notifications,
  when either `!bo1` or `!bo3` is used.

### `servers/.../rooms/match_starting`

**List of String**. Channels that will receive match start notifications, when
  ever the pick & ban sequence has ended.

## Member list

RoleKeeper heavily relies on the `members.csv` file that contains all team
captains Discord ID, team name, group and IGN. Based on this file, the bot is
able to rename, create the team role, and assign it to the team captain
whenever he joins the Discord server.

The filename and location for `member.csv` are not enforced and can be changed
in the `config.json` file. It is a per-server configuration:

**config.json**
```
...
    "servers" : {
        "June Fast Cup": {
            "captains": "members.csv",
            ...
        },
        "JFCtest": {
            "captains": "members_test.csv",
            ...
        }
    },
...
```

The `members.csv` file has to be in the following format (comma separated
values, `#` for comments):

**members.csv**
```
#discord,team,nickname,group
ezpz#4242,Noobs,AllProsAboveMe,A
gg#2424,Pros,xX-AtTheTop-Xx,B
noob42#777,PGM,SixSweat,C
```

The above member list makes RoleKeeper wait for any server join from
`ezpz#4242`, `gg#2424` and `noob42#777` on the Discord server he is invited
in.

For instance, once `ezpz#4242` joins the server, he will be:
 - Renamed to `AllProsAboveMe`;
 - Assigned roles `Team Captains`, `Group A` and `Noobs team`.

**Note**: Automatic role assignement is made only on members that do not have
_any_ role.  If for some reason a member has extra roles, he will not be
processed and will have to be handled manually by a referee.

## Recommandations

- It is recommanded to create a chat channel `#bot_commands` that both bot and
  referees can see and talk in order to enter all bot commands.  It will ease
  command tracking and prevent spam in lobby channels.

- Groups are useful to separate teams among referees. A referee handles one
  and only one group, until the brackets merge. At this point, some referees
  lose the responsability of their group.  It is recommanded to create chat
  channels like `#group_a` where members with role `Group A` are able to
  read/send messages. When the groups merge, referees can manually assign
  the new group role to the affected team captains.

## TODO

- [x] Reparse `members.csv` or provide a more dynamic way of adding team
  captains at the _last-minute_
- [x] Cross-server non-interference (When the bot is invited in several
  Discord servers, it will run on the same member list)
- [x] Take `config.json` as parameter
- [x] Configurable role names and list
- [x] Configurable map list
- [x] Forward pick & ban results in a room for a new `Streamer` role
- [x] Add `!stream` command for a new `Streamer` role to notify matches are streamed
- [x] Handle unicode team names in order to create valid Discord chat channel names.
- [ ] Add `!setup` for admin to create all channels and required roles (first time install).
- [x] Add `!wipe_match_rooms` for admin to remove all match chat rooms.
- [x] Add `!wipe_team_roles` for admin to remove all team captain roles.
- [ ] (idea) Import `members.csv` directly from esports website
- [ ] (idea) Automatically launch `!bo1`/`!bo3` based on info from esports
  website
- [ ] (idea) Handle match result gathering (with vote from both teams)
- [ ] Add progress for long operations, e.g. `!refresh`, `!wipe_teams`,
  `!wipe_matches`
- [ ] Add CSV upload instead of static memberlist.
- [ ] Support multiple cups at the same time, e.g. `!start_cup x` and
  `!stop_cup x`
- [ ] Regroup match chat rooms by categories (new Discord feature, requires
  new discord.py)
- [x] Export pick/ban stats command, or on `!stop_cup`
- [x] `!export_members` to export server member list
