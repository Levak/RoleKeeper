# RoleKeeper
Discord bot for Warface Tournaments


## About

RoleKeeper is a bot specificly designed to handle Warface Discord tournament
servers. Its main features are:
 - Auto-assignment of team captain and group roles based on an CSV file
   (exported from esports site);
 - Creation of chat channels used for guided pick & ban sequence (bo1, bo2, bo3);
 - Broadcast of events from and to match chat channels (match room
   created, streamed match, pick&ban results).

It was successfuly used in the
[June Fast Cup](https://esports.my.com/tournament/5/bracket/) (JFC 2017) with over
100 teams, first Warface Tournament ever ran on Discord. It has been used and
polished ever since.

## Demo

Here is a quick demonstration (from 2017) of what Rolekeeper does:

[![](https://img.youtube.com/vi/VnQ-jv2clgI/0.jpg)](https://www.youtube.com/watch?v=VnQ-jv2clgI
"Click to play on YouTube.com")

## Discord usage

The bot has a chat-command interface. A command starts with a `!` (bang sign)
followed by the command name, a space and then the command arguments.

### Team captains commands

A Team captain is a member imported using the `!add_captain` or `!start_cup` commands.

 - `!ban map`, bans map `map` from the map list available in the pick & ban
   sequence. `map` is case-insensitively matched at 80% with available maps;
 - `!pick map`, same as `!ban` excepts it is used to pick a map (best-of-3
   only);
 - `!side side`, chooses the side, either attack or defense.

**Note**: The above commands are only available in a match chat channel
  created by the bot itself.

### Referees commands

A judge referee is a member with the role [`roles/referee`](#rolesreferee)

 - `!say #channel message...`, makes the bot say `message...` in `channel`. Note
   that `channel` has to be a valid chat-channel mention;
 - `!bo1 @teamA @teamB [>cat] [cup] [new/reuse]` (Both first arguments have to
   be **existing** Discord role mentions);
   1. Creates a chat room named `match_teamA_vs_teamB` (with transliteration);
   2. If `>cat` is given, creates the channel in the `cat` channel category
      where `cat` has to be given in [`servers/.../categories/`](#serverscategories);
   3. Broadcast the fact the channel was created in rooms
      [`servers/.../rooms/match_created`](#serversroomsmatch_created);
   4. Gives permissions to `teamA` and `teamB` roles to write in the
      chat room;
   5. Starts a best-of-1 map pick & ban sequence (6xban, 7th is a pick, side);
   6. Team captains are invited to type `!ban map`, `!pick map` or `!side
      side` one after the other;
   7. Prints the summary of elected maps and sides;
   8. Broadcast the results in rooms
   [`servers/.../rooms/match_starting`](#serversroomsmatch_starting).
   Note: When a match already exists for the 2 teams, the bot will ask to
   either add `reuse` or `new` in the command. Otherwise, these arguments
   should never be given to avoid mistakes.
 - `!bo2 @teamA @teamB ...`, same as `!bo1` excepts it creates a best-of-2 chat
   channel (ban, ban, pick, pick, side);
 - `!bo3 @teamA @teamB ...`, same as `!bo1` excepts it creates a best-of-3 chat
   channel (ban, ban, pick, pick, ban, ban, 7th is a pick, side);
 - `!add_captain @captain teamA nickname group|- [cup]`, add captain to the
   captain database (for cup `cup`), assign the captain, team and group roles
   and rename the captain to the one defined in the CSV file. Argument `group`
   is mandatory, but if no group is required, use `-` (dash);
 - `!remove_captain @captain [cup]`, remove a captain from the captain
   database (for cup `cup`), reset its nickname, remove the assigned roles.
 - `!add_group group [cup]`, add group to the group database. Here `group`
   should correspond to `{}` in [`roles/group`](#rolesgroup) (e.g. `Group
   {}`). The Discord role for that group has to exist;
 - `!remove_group group [cup]`, remove a group from the group database.
 - `!ban`, `!pick` and `!side` commands (see [Team captains](#team-captains-commands))
   are available to referees so that they can test or bridge team captains
   choice if they are not in Discord server;
 - `!undo`, to go back 1 step in the pick & ban sequence.

**Note**: The `cup` argument is optional if there is only 1 cup running. Else it
is mandatory.

### Streamers commands

A streamer is a member with the role [`roles/streamer`](#rolesstreamer)

 - `!stream match_id [@streamer]`, will broadcast the information that
   `match_id` will be streamed by the one executing the command. Rolekeeper
   provides `match_id` to channels
   [`servers/.../rooms/match_created`](#serversroomsmatch_created) which
   streamers should have access to. The bot will also give visibility (read
   only) to the streamer on the match room if
   [`servers/.../streamer_can_see_match`](#serversstreamer_can_see_match) is
   `true`. If the optional `@streamer` argument is given (_valid Discord
   mention_) then it will be used in place of the command author.

### Admins commands

An admin is a member with Discord permission `manage roles`, someone that has
access to the `config.json` file and bot launch.

 - `!check_cup cup [// CSV]`, takes the attached CSV and builds a report of
   missing members or invalid Discord IDs. If the command was already used and
   we just want to run the check with the same database, the attached file is
   optional;
 - `!start_cup cup [maps_key] [// CSV]`, same as `!check_cup` but actually imports
   the captains and teams, and start assigning the roles. Same as
   `!check_cup`, if there was already a CSV given to check, the attached CSV
   file is optional. Once `!start_cup` is used, the scratchpad is emptied. If
   `maps_key` is given, use this one as the map pool key instead of the
   default one for the server;
 - `!stop_cup cup`, wipes out teams, captains and matches, then unregisters
   the cup from the database;
 - `!members`, will generate a CSV of all members in the Discord server;
 - `!stats [cup]`, will generate a CSV of pick&bans statistics;
 - `!wipe_matches [cup]`, will remove all match chat channels created;
 - `!wipe_messages #channel`, will remove all non-pinned messages in
   `channel`. Note that `channel` has to be a valid chat-channel mention.

## Usage

Rolekeeper requires Python >=3.5. Entrypoint is `main.py`, which takes an
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

This project requires **Python >=3.5** as it uses extensively the Python
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
            "db": "myserver",
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
 - [`Referees`](#rolesreferee);
 - [`Streamers`](#rolesstreamer).

**Note**: Make sure these roles are below `RoleKeeper` role in Discord role
  list so that it can manage them.

7. Run RoleKeeper

```
(venv) $ python ./main.py
```

8. Create a `members.csv` file (see [Member list](#member-list) section)

9. Check the members for a cup (in Discord):

```
Levak: !check_cup mycup
       <members.csv>
```

10. Start the cup (in Discord):

```
Levak: !start_cup mycup
```

11. Create pick&ban rooms (in Discord):

```
Levak: !bo1  @noob team  @pro team
Levak: !bo2  @op team    @ez team
Levak: !bo3  @wp team    @gg team
```

12. Fetch the pick&ban statistics and stop the cup (in Discord):

```
Levak: !stats mycup
Levak: !stop_cup mycup
```

Once everything is setup, the only things to repeat are steps 8 to 12.

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
        "referee": { "name": "Referees" },
        "streamer": { "name": "Streamers" },
        "captain": { "name": "{} Captains", "color": "0xf1c40f" },
        "group": { "name": "Group {}" },
        "team": { "name": "{} team", "color": "orange" }
    },

    "maps": {
        "ptb": [ "Yard", "D-17", "Factory", "District", "Destination", "Palace", "Pyramid" ],
        "test": [ "Lorem", "Ipsum", "Dolor", "Sit", "Amet", "Consectetur", "Adipiscing" ]
    },

    "servers": {
        "June Fast Cup": {
            "db": "jfc",
            "default_maps": "ptb",
            "rooms": {
                "match_created": [ "jfc_streamers" ],
                "match_starting": [ "bot_referees", "jfc_streamers" ]
            },
            "streamer_can_see_match": true,
            "categories": {
                "A": "Referee A",
                "B": "Referee B"
            }
        },

        "JFCtest": {
            "db": "jfctest",
            "default_maps": "test",
            "rooms": {
                "match_created": [ "streamers" ],
                "match_starting": [ "referees", "streamers" ]
            }
        }
    }
}
```

### Role type

#### `role/name`

**String**. Name of the role. The role may support formating string, in such
  cases, use `{}` to indicate the location where the formatting will happen
  (e.g. `{} team` will become `Foobar team` for team `Foobar`).

#### `role/color`

**String**. Color of the role in Discord. The format may be hexadecimal
  (e.g. `0xFFFFFF`) or the name of the color (e.g. `orange`).

### `app_bot_token`

**String**. Token for the bot. Go to
[Discord application page](https://discordapp.com/developers/applications/me#top),
click on your application, then create a bot for the application and expand
the _APP BOT TOKEN_.

### `emotes/loading`

**String**. ID of the emote to use for loading operations. Can be ommited and
  no loading emoji will be used. In order to add a custom loading emoji, add
  an animated emoji to a server the bot has access to
  (e.g. [this one](https://cdn.discordapp.com/emojis/425366701794656276.gif) ),
  right click on it, "Open image in a new tab" and copy the digit part of the
  URL.

### `roles/referee`

**Role**. Role used for Judge referees.

### `roles/streamer`

**Role**. Role used for Streamers/Casters.

### `roles/captain`

**Role**. Role used for Team captains. Formatted with the cup name.

### `roles/group`

**Role**. Role used for the Team Groups. Formatted with the group ID.

### `roles/team`

**Role**. Role used for the Team names. Formatted with the team name.

### `maps/...`

**Dict of List of String**. All the available maps for the pick & ban
  sequences indexed by "key". May contain any number of maps per key. "key" is
  used to reference a map pool in `!start_cup` and in
  [`servers/.../default_maps`](#serversdefault_maps).

### `servers/.../db`

**String**. Name of the persistent storage DB on the disk (unique per server).

### `servers/.../default_maps`

**String**. Key referencing the map pool defined in [`maps/...`](#maps).

### `servers/.../rooms/match_created`

**List of String**. Channels that will receive match creation notifications,
  when either `!bo1` or `!bo3` is used.

### `servers/.../rooms/match_starting`

**List of String**. Channels that will receive match start notifications, when
  ever the pick & ban sequence has ended.

### `servers/.../streamer_can_see_match`

**Boolean**. If `true`, then when creating a match, a streamer that uses the
  `!stream` command will be able to see (read-only) the said rooms. Useful
  when the streamer needs to see the pick&ban sequence, or know when/if the
  match is about to start.

### `servers/.../categories/...`

**Dict of String**. Discord channel category shortcuts. e.g.

```
"categories": {
    "A": "Referee A",
    "B": "Referee B"
}
```

And then use it like this:

```
!bo1 @xxx @yyy >A
!bo1 @zzz @www >B
```


## Member list

RoleKeeper heavily relies on `members.csv` files that contain all team
captains Discord ID, team name, group and IGN. Based on such file, the bot is
able to rename, create the team role, and assign it to the team captain
whenever he joins the Discord server.

A `member.csv` file can be remotely uploaded via Discord to the bot using the
`!check_cup` or `!start_cup` command (attach the file to the Discord message).

A `members.csv` file has to be in the following format (comma separated
values, `#` for comments):

**members.csv**
```
#discord,team_name,nickname,group
ezpz#4242,Noobs,AllProsAboveMe,A
gg#2424,Pros,xX-AtTheTop-Xx,B
noob42#777,PGM,SixSweat,C
```

**Note**: The first line of the members.csv file has to contain column names
  that match the ones in the above example. That is, `discord`, `team_name`,
  `nickname` and `group`. There can be other columns with other names, these
  will be ignored.

The above member list makes RoleKeeper wait for any server join from
`ezpz#4242`, `gg#2424` and `noob42#777` on the Discord server the command was
ran on.

For instance, once `ezpz#4242` joins the server, he will be:
 - Renamed to `AllProsAboveMe`;
 - Assigned roles `TestCup Captains`, `Group A` and `Noobs team`.

**CAUTION**: **NEVER MANUALLY ASSIGN TEAM ROLES TO CAPTAINS**. The bot uses
its own database to know who is and who isn't allowed to use captain
commands. A team captain can only be added using the `!add_captain` and
`!start_cup` (bulk) commands. Do not try to give the Discord roles manually to
them. You may think the captain is now allowed to see the room, but he will be
unable to pick or ban maps.

## Recommandations

- It is recommanded to create a chat channel `#bot_commands` that both bot and
  referees can see and talk in order to enter all bot commands.  It will ease
  command tracking and prevent spam in lobby channels.

- Groups are useful to separate teams among referees. A referee handles one
  and only one group, until the brackets merge. At this point, some referees
  lose the responsability of their group. It is recommanded to create chat
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
- [x] Add progress for long operations, e.g. `!refresh`, `!wipe_teams`,
  `!wipe_matches`
- [x] Add CSV upload instead of static memberlist.
- [x] Support multiple cups at the same time, e.g. `!start_cup x` and
  `!stop_cup x`
- [x] Regroup match chat rooms by categories (new Discord feature, requires
  new discord.py)
- [x] Export pick/ban stats command, or on `!stop_cup`
- [x] `!export_members` to export server member list
- [ ] `!unstream x` to cancel `!stream x`.
- [x] `!undo` to undo a `!ban` or `!pick`
- [x] unlimited and dynamid map pools instead of just 7 maps
