# The MIT License (MIT)
# Copyright (c) 2017 Levak Borok <levak92@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

import requests
import uuid
import discord
import asyncio
import csv
import random
import re
import io
import datetime

from team import Team, TeamCaptain, Cup, Group
from match import Match, MatchBo2, MatchBo3
from inputs import sanitize_input, translit_input
from db import open_db
from handle import Handle

welcome_message_bo1 =\
"""
Welcome {m_teamA} and {m_teamB}!
-- Match **BEST OF 1** --
This text channel will be used by the judge and team captains to exchange anything about the match between teams {teamA} and {teamB}.
This sequence is made using the `!ban` command team by team until one remains.
Last team to ban also needs to chose the side they will play on using `!side xxxx` (attack or defend).

 - {teamA} bans, {teamB} bans,
 - {teamA} bans, {teamB} bans,
 - {teamA} bans, {teamB} bans,
 - Last map remaining is the map to play,
 - {teamA} picks the side (attack or defense).

For instance, team A types `!ban Pyramid` which will then ban the map _Pyramid_ from the match, team B types `!ban d17` which will ban the map D-17, and so on, until only one map remains. team A then picks the side using `!side attack`.
"""

welcome_message_bo2 =\
"""
Welcome {m_teamA} and {m_teamB}!
-- Match **BEST OF 2** --
This text channel will be used by the judge and team captains to exchange anything about the match between teams {teamA} and {teamB}.
This sequence is made using the `!pick`, `!ban` and `!side` commands one by one using the following order:

 - {teamA} bans, {teamB} bans,
 - {teamA} picks, {teamB} picks,
 - {teamB} picks the side for first map (attack or defense).
 - {teamA} picks the side for second.

For instance, team A types `!ban Yard` which will then ban the map _Yard_ from the match, team B types `!ban d17` which will ban the map D-17. team A would then type `!pick Destination`, picking the first map and so on, until only one map remains, which will be the tie-breaker map. team B then picks the side using `!side attack`.
"""

welcome_message_bo3 =\
"""
Welcome {m_teamA} and {m_teamB}!
-- Match **BEST OF 3** --
This text channel will be used by the judge and team captains to exchange anything about the match between teams {teamA} and {teamB}.
This sequence is made using the `!pick`, `!ban` and `!side` commands one by one using the following order:

 - {teamA} bans, {teamB} bans,
 - {teamA} picks, {teamB} picks,
 - {teamA} bans, {teamB} bans,
 - Last map remaining is the draw map,
 - {teamB} picks the side for first map (attack or defense).
 - {teamA} picks the side for second and tie breaker map.

For instance, team A types `!ban Yard` which will then ban the map _Yard_ from the match, team B types `!ban d17` which will ban the map D-17. team A would then type `!pick Destination`, picking the first map and so on, until only one map remains, which will be the tie-breaker map. team B then picks the side using `!side attack`.
"""

import atexit

class RoleKeeper:
    def __init__(self, client, config):
        self.client = client
        self.config = config
        self.db = {}
        self.emotes = {}

        self.checked_cups = {}

        for name in [ 'loading' ]:
            if 'emotes' in config and name in config['emotes']:
                self.emotes[name] = '<a:{name}:{id}>'\
                    .format(name=name,
                            id=config['emotes'][name])
            else:
                self.emotes[name] = ''

        atexit.register(self.atexit)

    def atexit(self):
        if self.db:
            for server, db in self.db.items():
                print ('Closing DB "{}"'.format(server.name))
                db.close()
            self.db = None

    def check_server(self, server):
        if server.name not in self.config['servers']:
            print ('WARNING: Server "{}" not configured!'.format(server.name))
            return False
        return True

    # Parse header from CSV file
    def parse_header(self, header):
        return { e: header.index(e) for e in header }

    # Parse members from CSV file
    def parse_teams(self, server, csvfile, cup):
        captains = {}
        groups = {}

        if csvfile:
            dialect = csv.Sniffer().sniff(csvfile.read(1024), delimiters=',;')
            csvfile.seek(0)
            reader = csv.reader(csvfile, dialect)

            header = None

            for row in reader:
                # Skip empty lines and lines starting with #
                if len(row) <= 0 or row[0].startswith('#'):
                    # If we didn't parse header yet, first comment is usually it
                    if not header:
                        row[0] = row[0][1:] # Delete the '#'
                        header = self.parse_header(row)
                    continue

                # If we didn't parse header yet, it's the first line
                if not header:
                    header = self.parse_header(row)
                    continue

                discord_id = row[header['discord']].strip()
                team_name = row[header['team_name']].strip()
                nickname = row[header['nickname']].strip()

                # If the file doesn't contain groups, not a problem, just ignore it
                if 'group' not in header:
                    group_id = None
                else:
                    group_id = row[header['group']].strip()

                # If the member hasn't given any Discord ID, make one up
                if len(discord_id) == 0:
                    key = uuid.uuid4()
                else:
                    key = discord_id

                group = None
                # If group is new to us, cache it
                if group_id:
                    if group_id not in groups:
                        group_name = self.get_role_name('group', arg=group_id)
                        group = Group(group_name, None)
                        groups[group_id] = group
                    else:
                        group = groups[group_id]

                captains[key] = \
                    TeamCaptain(discord_id, team_name, nickname, group, cup)

        print('Parsed teams:')
        # Print parsed members
        for m in captains:
            print('-> {}'.format(captains[m]))

        return captains, groups

    async def get_or_create_role(self, server, role_name, color=None):
        role = discord.utils.get(server.roles, name=role_name)

        if not role:
            role = await self.client.create_role(
                server,
                name=role_name,
                permissions=discord.Permissions.none(),
                mentionable=True,
                color=discord.Colour(color))

            print('Create new role <{role}>'\
                  .format(role=role_name))

        role.name = role_name # This is a hotfix

        return role

    def open_db(self, server):
        if server in self.db and self.db[server]:
            self.db[server].close()

        self.db[server] = open_db(self.config['servers'][server.name]['db'])

        if 'cups' not in self.db[server]:
            self.db[server]['cups'] = {}

        # Refill group cache
        self.db[server]['sroles'] = {}
        self.cache_special_role(server, 'referee')
        self.cache_special_role(server, 'streamer')

    def open_cup_db(self, server, cup):
        if cup.name not in self.db[server]['cups']:
            self.db[server]['cups'][cup.name] = { 'cup': cup }

        db = self.db[server]['cups'][cup.name]

        if 'matches' not in db:
            db['matches'] = {}

        if 'teams' not in db:
            db['teams'] = {}

        if 'captains' not in db:
            db['captains'] = {}

        if 'groups' not in db:
            db['groups'] = {}

        return db

    def close_cup_db(self, server, cup_name):
        if cup_name not in self.db[server]['cups']:
            return False

        del self.db[server]['cups'][cup_name]
        return True

    def get_cup_db(self, server, cup_name):
        # If we didn't say which cup we wanted
        if len(cup_name) == 0:
            num_cups = len(self.db[server]['cups'])
            # If there is only 1 cup running, return it
            if num_cups == 1:
                return next(iter(self.db[server]['cups'].values())), None
            elif num_cups == 0:
                return None, 'No cup is running!'
            # Else, this is ambiguous
            else:
                return None, 'There is more than one cup running!'

        # Else if the cup exists, return it
        elif cup_name in self.db[server]['cups']:
            return self.db[server]['cups'][cup_name], None

        # Else, fail
        else:
            return None, 'No such cup is running'

    def find_cup_db(self, server, captain=None, match=None):
        if captain:
            for cup_name, db in self.db[server]['cups'].items():
                if captain in db['captains']:
                    return db, None
        elif match:
            for cup_name, db in self.db[server]['cups'].items():
                if match in db['matches']:
                    return db, None

        return None, 'No cup was found that contains this user or match'

    # Acknowledgement that we are succesfully connected to Discord
    async def on_ready(self):

        for server in self.client.servers:
            print('Server: {}'.format(server))

            if self.check_server(server):
                self.open_db(server)

    async def on_dm(self, message):
        # If it is us sending the DM, exit
        if message.author == self.client.user:
            return

        print('PM from {}: {}'.format(message.author, message.content))

        # Apologize
        await self.reply(message,
                       ''':wave: Hello there!
                       I am sorry, I cannot answer your question, I am just a bot!
                       Feel free to ask a referee or admin instead :robot:''')

    async def on_member_join(self, member):
        if member.server.name not in self.config['servers']:
            return

        await self.handle_member_join(member)

    def get_role_name(self, role_id, arg=None):
        if role_id not in self.config['roles']:
            print ('WARNING: Missing configuration for role "{}"'.format(role_id))
            return None

        role_cfg = self.config['roles'][role_id]

        if type(role_cfg) == type({}):
            if 'name' in role_cfg:
                role_name = role_cfg['name']
            else:
                print ('WARNING: Missing "name" attribute in config for role "{}"'.format(role_id))
                return None
        else:
            # retro-compatibility
            role_name = role_cfg

        if arg:
            role_name = role_name.format(arg)

        return role_name

    def get_role_color(self, role_id):
        if role_id not in self.config['roles']:
            print ('WARNING: Missing configuration for role "{}"'.format(role_id))
            return None

        role_cfg = self.config['roles'][role_id]

        # retro-compatibility
        if type(role_cfg) != type({}):
            return None

        if 'color' in role_cfg:
            color = role_cfg['color']
            if type(color) == type(''):
                if color in discord.Colour.__dict__:
                    return discord.Colour.__dict__[color].__func__(discord.Colour).value
                else:
                    try:
                        return int(color, 0)
                    except:
                        print ('WARNING: Not supported color "{}" for role "{}"'.format(color, role_id))
                        return None
            elif type(color) == type(0):
                return color
            else:
                return None
        else:
            return None

    def cache_special_role(self, server, role_id):
        role_name = self.get_role_name(role_id)
        if not role_name:
            return None

        role = discord.utils.get(server.roles, name=role_name)

        self.db[server]['sroles'][role_id] = role
        if not self.db[server]['sroles'][role_id]:
            print ('WARNING: Missing role "{}" in {}'.format(role_name, server.name))

    def get_special_role(self, server, role_id):
        if role_id in self.db[server]['sroles']:
            return self.db[server]['sroles'][role_id]
        return None

    async def add_group(self, message, server, group_id, cup_name):
        if not self.check_server(server):
            return False

        db, error = self.get_cup_db(server, cup_name)
        if error:
            await self.reply(message, error)
            return False

        # Check if group exists
        if group_id in db['groups']:
            await self.reply(message, 'Group "{}" already exists'.format(group_id))
            return False

        # If group is new to us, cache it
        group_name = self.get_role_name('group', arg=group_id)
        role_color = self.get_role_color('group')
        group_role = await self.get_or_create_role(server, group_name, color=role_color)
        group = Group(group_role, group_name)

        db['groups'][group_id] = group

        return True

    async def remove_group(self, message, server, group_id, cup_name):
        if not self.check_server(server):
            return False

        db, error = self.get_cup_db(server, cup_name)
        if error:
            await self.reply(message, error)
            return False

        # Check if group exists
        if group_id not in db['groups']:
            await self.reply(message, 'Group "{}" does not exist'.format(group_id))
            return False

        group = db['groups'][group_id]

        members = list(server.members)
        # Remove the group from each captain using it
        for _, captain in db['captains'].items():
            if captain.group and captain.group.name == group.name:
                captain.group = None

                cpt = None
                for member in members:
                    if str(member) == captain.discord:
                        cpt = member
                        break

                if not cpt:
                    continue

                try:
                    await self.client.remove_roles(cpt, group.role)
                    print ('Removed role "{grole}" from "{member}"'\
                           .format(member=captain.discord,
                                   grole=group.name))
                except:
                    print ('WARNING: Failed to remove role "{grole}" from "{member}"'\
                           .format(member=captain.discord,
                                   grole=group.name))
                    pass


        del db['groups'][group_id]

        return True

    async def add_captain(self, message, server, member, team, nick, group_id, cup_name):
        if not self.check_server(server):
            return False

        db, error = self.get_cup_db(server, cup_name)
        if error:
            await self.reply(message, error)
            return False

        discord_id = str(member)

        # If captain already exists, remove him
        if discord_id in db['captains']:
            await self.remove_captain(message, server, member, cup_name)

        # Check if destination group exists
        if group_id and group_id not in db['groups']:
            await self.reply(message, 'Group "{}" does not exist'.format(group_id))
            return False

        # Add new captain to the list
        db['captains'][discord_id] = \
            TeamCaptain(discord_id,
                        team,
                        nick,
                        db['groups'][group_id] if group_id else None,
                        db['cup'])

        # Trigger update on member
        await self.handle_member_join(member, db)

        return True

    async def remove_captain(self, message, server, member, cup_name):
        if not self.check_server(server):
            return False

        db, error = self.get_cup_db(server, cup_name)
        if error:
            await self.reply(message, error)
            return False

        discord_id = str(member)

        if discord_id not in db['captains']:
            await self.reply(message, '{} is not a known captain in cup {}'\
                             .format(member.mention,
                                     db['cup'].name))
            return False

        captain = db['captains'][discord_id]

        captain_role = captain.cup.role if captain.cup else None
        group_role = captain.group.role if captain.group else None
        team = captain.team
        team_role = team.role if team else None

        crole_name = captain_role.name if captain_role else ''
        grole_name = group_role.name if group_role else '<no group>'
        trole_name = team_role.name if team_role else ''

        # Remove team, team captain and group roles from member
        try:
            if group_role:
                await self.client.remove_roles(member, captain_role, team_role, group_role)
            else:
                await self.client.remove_roles(member, captain_role, team_role)

            print ('Removed roles "{crole}", "{grole}" and "{trole}" from "{member}"'\
                   .format(member=discord_id,
                           crole=crole_name,
                           grole=grole_name,
                           trole=trole_name))
        except:
            print ('WARNING: Failed to remove roles "{crole}", "{grole}" and "{trole}" from "{member}"'\
                   .format(member=discord_id,
                           crole=crole_name,
                           grole=grole_name,
                           trole=trole_name))
            pass

        # Check if the role is now orphan, and delete it
        members = list(server.members)
        if not any(r == team_role for m in members for r in m.roles):
            try:
                await self.client.delete_role(server, team_role)
                print ('Deleted role "{role}"'\
                       .format(role=trole_name))
            except:
                print ('WARNING: Failed to delete role "{role}"'\
                       .format(role=trole_name))
                pass
            del db['teams'][trole_name]

        # Reset member nickname
        try:
            await self.client.change_nickname(member, None)
            print ('Reset nickname for "{member}"'\
                   .format(member=discord_id))
        except:
            print ('WARNING: Failed to reset nickname for "{member}"'\
                   .format(member=discord_id))
            pass

        # Remove captain from DB
        del db['captains'][discord_id]

        return True

    # Go through the parsed captain list and create all team roles
    async def create_all_teams(self, server, cup_name):
        if not self.check_server(server):
            return False

        db, error = self.get_cup_db(server, cup_name)
        if error:
            print('ERROR create_all_teams: {}'.format(error))
            return False

        db['teams'] = {}
        for _, captain in db['captains'].items():
            team = await self.create_team(server, db, captain.team_name)
            captain.team = team

        return True

    # Create team captain role
    async def create_team(self, server, db, team_name):
        role_name = self.get_role_name('team', arg=team_name)

        if role_name in db['teams']:
            return db['teams'][role_name]

        role_color = self.get_role_color('team')
        role = await self.get_or_create_role(server, role_name, color=role_color)

        team = Team(team_name, role)
        db['teams'][role_name] = team

        return team

    # Whenever a new member joins into the Discord server
    # 1. Create a user group just for the Team captain
    # 2. Assign the special group to that Team captain
    # 3. Assign the global group to that Team captain
    # 4. Change nickname of Team captain
    async def handle_member_join(self, member, db=None):
        discord_id = str(member)
        server = member.server

        # If no db was provided
        if not db:
            # Find cup from discord_id
            db, error = self.find_cup_db(server, discord_id)

            # User was not found
            if error:
                return

        # Check that the captain is indeed in our list
        if discord_id not in db['captains']:
            #print('WARNING: New user "{}" not in captain list'\
            #      .format(discord_id))
            return

        print('Team captain "{}" joined server'\
              .format(discord_id))

        captain = db['captains'][discord_id]

        # Create role
        team = await self.create_team(server, db, captain.team_name)
        team_role = team.role if team else None
        captain.team = team

        # Assign user roles
        group_role = captain.group.role if captain.group else None
        captain_role = captain.cup.role if captain.cup else None

        try:
            if group_role:
                await self.client.add_roles(member, team_role, captain_role, group_role)
            else:
                await self.client.add_roles(member, team_role, captain_role)
            print('Assigned role <{role}> to "{id}"'\
                  .format(role=team_role.name, id=discord_id))
        except:
            print('ERROR: Missing one role out of R:{} C:{} G:{}'\
                  .format(team_role, captain_role, group_role))

        # Change nickname of team captain
        nickname = '{}'.format(captain.nickname)

        try:
            await self.client.change_nickname(member, nickname)
            print ('Renamed "{id}" to "{nick}"'\
                   .format(id=discord_id, nick=nickname))
        except:
            print ('WARNING: Failed to rename "{id}" to "{nick}"'\
                   .format(id=discord_id, nick=nickname))
            pass

    # Reply to a message in a channel
    async def reply(self, message, reply):
        msg = '{} {}'.format(message.author.mention, reply)

        acc = ''
        for l in msg.splitlines():
            if len(acc) + len(l) >= 2000:
                await self.client.send_message(message.channel, acc)
                acc = l
            else:
                acc = '{}\n{}'.format(acc, l)

        return await self.client.send_message(message.channel, acc)

    async def embed(self, message, title, body, error=False):
        color = 0x992d22 if error else 0x2ecc71
        handle = Handle(self, message=message)

        li = []
        acc = ''
        for l in body.splitlines():
            if len(acc) + len(l) >= 2000:
                li.append(acc)
                acc = l
            else:
                acc = '{}\n{}'.format(acc, l)

        count = len(li) + 1
        i = 1
        for msg in li:
            await handle.embed('{} ({}/{})'.format(title, i, count), msg, color)
            i = i + 1

        if count > 1:
            title = '{} ({}/{})'.format(title, count, count)

        return await handle.embed(title, acc, color)

    MATCH_BO1 = 1
    MATCH_BO2 = 2
    MATCH_BO3 = 3

    REUSE_UNK = 0
    REUSE_YES = 2
    REUSE_NO  = 3

    # Create a match against 2 teams
    # 1. Create the text channel
    # 2. Add permissions to read/send to both teams, and the judge
    # 3. Send welcome message
    # 4. Register the match to internal logic for commands like !ban x !pick x
    async def matchup(self, message, server, _roleteamA, _roleteamB, cat_id, cup_name, mode=MATCH_BO1, flip_coin=False, reuse=REUSE_UNK):
        if not self.check_server(server):
            return False

        db, error = self.get_cup_db(server, cup_name)
        if error:
            await self.reply(message, error)
            return False

        if flip_coin:
            randomized = [ _roleteamA, _roleteamB ]
            random.shuffle(randomized)
            roleteamA, roleteamB = randomized[0], randomized[1]
        else:
            if message.content.find(_roleteamA.mention) < message.content.find(_roleteamB.mention):
                roleteamA, roleteamB = _roleteamA, _roleteamB
            else:
                roleteamA, roleteamB = _roleteamB, _roleteamA

        notfound = None

        if roleteamA.name in db['teams']:
            teamA = db['teams'][roleteamA.name]
        else:
            notfound = roleteamA.name

        if roleteamB.name in db['teams']:
            teamB = db['teams'][roleteamB.name]
        else:
            notfound = roleteamB.name

        if notfound:
            await self.reply(message, 'Role "{}" is not a known team'.format(notfound))
            return False

        roleteamA_name_safe = sanitize_input(translit_input(teamA.name))
        roleteamB_name_safe = sanitize_input(translit_input(teamB.name))
        topic = 'Match {} vs {}'.format(teamA.name, teamB.name)

        ref_role = self.get_special_role(server, 'referee')

        read_perms = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        no_perms = discord.PermissionOverwrite(read_messages=False)

        index = 1
        index_str = ''
        while True:
            channel_name = 'match_{}_vs_{}{}'.format(roleteamA_name_safe, roleteamB_name_safe, index_str)  # TODO cup
            channel = discord.utils.get(server.channels, name=channel_name)

            # Channel already exists, but we do not know if we should reuse it
            if channel and reuse == self.REUSE_UNK:
                await self.reply(message, 'Room `{}` already exists!\nAdd `reuse` in the command to reuse the same channel or `new` to create a new one.'.format(channel_name))
                return False

            if not channel or reuse == self.REUSE_YES:
                break

            index = index + 1
            index_str = '_r{}'.format(index)

        category = None
        if 'categories' in self.config['servers'][server.name] \
           and cat_id in self.config['servers'][server.name]['categories']:
            cat_name = self.config['servers'][server.name]['categories'][cat_id]
            for ch in server.channels:
                if cat_name.lower() in ch.name.lower():
                    category = ch

        if not channel:
            try:
                channel = await self.client.create_channel(
                    server,
                    channel_name,
                    (roleteamA, read_perms),
                    (roleteamB, read_perms),
                    (server.default_role, no_perms),
                    (server.me, read_perms),
                    (ref_role, read_perms),
                    category=category)

                print('Created channel "<{channel}>"'\
                      .format(channel=channel.name))
            except:
                print('WARNING: Failed to create channel "<{channel}>"'\
                      .format(channel=channel.name))

            try:
                await self.client.edit_channel(
                    channel,
                    topic=topic)

                print('Set topic for channel "<{channel}>" to "{topic}"'\
                      .format(channel=channel.name, topic=topic))
            except:
                print('WARNING: Failed to set topic for channel "<{channel}>"'\
                      .format(channel=channel.name))
        else:
            print('Reusing existing channel "<{channel}>"'\
                  .format(channel=channel.name))

        maps = self.config['servers'][server.name]['maps']

        if mode == self.MATCH_BO3:
            match = MatchBo3(teamA, teamB, maps)
            template = welcome_message_bo3
        elif mode == self.MATCH_BO2:
            match = MatchBo2(teamA, teamB, maps)
            template = welcome_message_bo2
        else:
            match = Match(teamA, teamB, maps)
            template = welcome_message_bo1

        db['matches'][channel_name] = match
        handle = Handle(self, channel=channel)
        msg = template.format(m_teamA=roleteamA.mention,
                              m_teamB=roleteamB.mention,
                              teamA=teamA.name,
                              teamB=teamB.name,
                              maps='\n'.join([ ' - {}'.format(m) for m in maps ]))

        await self.client.send_message(channel, msg)
        await match.begin(handle)

        return True


    # Returns if a member is a team captain in the given channel
    def is_captain_in_match(self, member, channel):
        server = member.server

        if server not in self.db:
            return False

        db, error = self.find_cup_db(server, match=channel.name)
        if error:
            return False

        if channel.name not in db['matches']:
            return False

        return db['matches'][channel.name].is_in_match(member)

    # Ban a map
    async def ban_map(self, message, map_unsafe, force=False):
        server = message.author.server
        channel = message.channel
        banned_map_safe = sanitize_input(translit_input(map_unsafe))

        if not self.check_server(server):
            return False

        db, error = self.find_cup_db(server, match=channel.name)
        if error:
            return False

        if channel.name not in db['matches']:
            return False

        handle = Handle(self, message=message)
        return await db['matches'][channel.name].ban_map(handle, banned_map_safe, force)

    # Pick a map
    async def pick_map(self, message, map_unsafe, force=False):
        server = message.author.server
        channel = message.channel
        picked_map_safe = sanitize_input(translit_input(map_unsafe))

        if not self.check_server(server):
            return False

        db, error = self.find_cup_db(server, match=channel.name)
        if error:
            return False

        if channel.name not in db['matches']:
            return False

        handle = Handle(self, message=message)
        return await db['matches'][channel.name].pick_map(handle, picked_map_safe, force)

    # Choose sides
    async def choose_side(self, message, side_unsafe, force=False):
        server = message.author.server
        channel = message.channel
        side_safe = sanitize_input(translit_input(side_unsafe))

        if not self.check_server(server):
            return False

        db, error = self.find_cup_db(server, match=channel.name)
        if error:
            return False

        if channel.name not in db['matches']:
            return False

        handle = Handle(self, message=message)
        return await db['matches'][channel.name].choose_side(handle, side_safe, force)

    # Broadcast information that the match is or will be streamed
    # 1. Notify captains match will be streamed
    # 2. Give permission to streamer to see match room
    # 3. Invite streamer to join it
    async def stream_match(self, message, match_id, streamer):
        server = message.server

        if not self.check_server(server):
            return False

        member = message.author if not streamer else streamer
        channel = discord.utils.get(member.server.channels, name=match_id)

        # If we found a channel with the given name
        if not channel:
            await self.reply(message, 'This match does not exist!')
            return False

        # 1. Notify captains match will be streamed
        await self.client.send_message(
            channel, ':eye::popcorn: _**{}** will stream this match!_ :movie_camera::satellite:\n'
            ':arrow_forward: _8.9. The teams whose match will be officially streamed will have '
            '**only** 10 minutes to assemble._\n'\
            .format(member.nick if member.nick else member.name))

        print('Notified "{channel}" the match will be streamed by "{member}"'\
              .format(channel=channel.name,
                      member=str(member)))

        if 'streamer_can_see_match' in self.config['servers'][server.name] \
           and self.config['servers'][server.name]['streamer_can_see_match']:

            # 2. Give permission to streamer to see match room
            overwrite = discord.PermissionOverwrite()
            overwrite.read_messages = True
            await self.client.edit_channel_permissions(channel, member, overwrite)

            print('Gave permission to "{member}" to see channel "{channel}"'\
                  .format(channel=channel.name,
                  member=str(member)))

            # 3. Invite streamer to join it
            await self.reply(message, 'Roger! Checkout {}'.format(channel.mention))

        return True

    # Remove all teams
    # 1. Delete all existing team roles
    # 2. Find all members with role team captain
    # 3. Remove group role from member
    # 4. Remove team captain and group roles from member
    # 5. Reset member nickname
    async def wipe_teams(self, message, cup_name):
        server = message.server

        if not self.check_server(server):
            return False

        db, error = self.get_cup_db(server, cup_name)
        if error:
            await self.reply(message, error)
            return False

        count = len(db['teams'])
        reply = await self.reply(message,
                                 '{l} Deleting {count} teams... (this might take a while)'\
                                 .format(count=count,
                                         l=self.emotes['loading']))

        # 1. Delete all existing team roles
        for role_name, team in db['teams'].items():
            try:
                await self.client.delete_role(server, team.role)
                print ('Deleted role "{role}"'\
                       .format(role=role_name))
            except:
                print ('WARNING: Failed to delete role "{role}"'\
                       .format(role=role_name))
                pass

        db['teams'].clear()

        # 2. Find all members with role team captain
        members = list(server.members)
        for member in members: # TODO go through db instead
            discord_id = str(member)
            if discord_id not in db['captains']:
                continue

            captain = db['captains'][discord_id]

            print ('Found captain "{member}"'\
                   .format(member=discord_id))

            # 3. Remove group role from member
            captain_role = captain.cup.role if captain.cup else None
            group_role = captain.group.role if captain.group else None
            crole_name = captain_role.name if captain_role else ''
            grole_name = group_role.name if group_role else '<no group>'

            # 4. Remove team captain and group roles from member
            try:
                if group_role:
                    await self.client.remove_roles(member, captain_role, group_role)
                else:
                    await self.client.remove_roles(member, captain_role)

                print ('Removed roles "{crole}" and "{grole}" from "{member}"'\
                       .format(member=discord_id,
                               crole=crole_name,
                               grole=grole_name))
            except:
                print ('WARNING: Failed to remove roles "{crole}" and "{grole}" from "{member}"'\
                       .format(member=discord_id,
                               crole=crole_name,
                               grole=grole_name))
                pass

            # 5. Reset member nickname
            try:
                await self.client.change_nickname(member, None)
                print ('Reset nickname for "{member}"'\
                       .format(member=discord_id))
            except:
                print ('WARNING: Failed to reset nickname for "{member}"'\
                       .format(member=discord_id))
                pass

        db['captains'].clear()

        await self.client.edit_message(reply, '{mention} Deleted {count} teams.'\
                                       .format(mention=message.author.mention,
                                               count=count))

        return True

    # Remove all match rooms
    # 1. Find all match channels that where created by the bot for this cup
    # 2. Delete channel
    async def wipe_matches(self, message, cup_name):
        server = message.server

        if not self.check_server(server):
            return False

        db, error = self.get_cup_db(server, cup_name)
        if error:
            await self.reply(message, error)
            return False

        count = len(db['matches'])
        reply = await self.reply(message,
                                 '{l} Deleting {count} matches... (this might take a while)'\
                                 .format(count=count,
                                         l=self.emotes['loading']))

        for channel_name in db['matches'].keys():
            channel = discord.utils.get(server.channels, name=channel_name)
            if channel:
                try:
                    await self.client.delete_channel(channel)
                    print ('Deleted channel "{channel}"'\
                           .format(channel=channel_name))
                except:
                    print ('WARNING: Fail to Delete channel "{channel}"'\
                           .format(channel=channel_name))

        db['matches'].clear()

        await self.client.edit_message(reply, '{mention} Deleted {count} matches.'\
                                       .format(mention=message.author.mention,
                                               count=count))

        return True

    # Helper function to delete messages one by one
    async def delete_messages_one_by_one(self, l):
        count = len(l)
        for msg in l:
            try:
                await self.client.delete_message(msg)
            except:
                count = count - 1
                print('WARNING: No permission to delete in "{}"'.format(channel.name))
                pass

        return count


    # Remove all messages that are not pinned in a given channel
    async def wipe_messages(self, message, channel):
        server = message.server

        if not self.check_server(server):
            return False

        messages_to_delete = []
        old_messages_to_delete = []
        t_14days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=14)

        try:
            async for msg in self.client.logs_from(channel, limit=1000):
                if not msg.pinned:
                    if msg.timestamp < t_14days_ago:
                        old_messages_to_delete.append(msg)
                    else:
                        messages_to_delete.append(msg)
        except:
            print('WARNING: No permission to read logs from "{}"'.format(channel.name))
            return False

        count = 0

        reply = await self.reply(message,
                                 '{l} Clearing {count} message(s)... (this might take a while)'\
                                 .format(count=len(messages_to_delete) + len(old_messages_to_delete),
                                         l=self.emotes['loading']))

        max_api_count = 100
        for i in range(int(len(messages_to_delete) / max_api_count) + 1):
            # Try to delete messages in bulk, if not older than 14 days
            try:
                bulk_messages_to_delete = messages_to_delete[(i)*max_api_count:(i+1)*max_api_count]
                await self.client.delete_messages(bulk_messages_to_delete)
                count += len(bulk_messages_to_delete)
            except:
                # If there is any error, try to delete them 1 by 1 instead
                count += await self.delete_messages_one_by_one(bulk_messages_to_delete)

        # Finally delete old messages
        count += await self.delete_messages_one_by_one(old_messages_to_delete)

        await self.client.edit_message(reply, '{mention} Deleted {count} messages.'\
                                       .format(mention=message.author.mention,
                                               count=count))
        print ('Deleted {count} messages in "{channel}"'\
               .format(count=count, channel=channel.name))

        return True

    # Announcement message
    async def announce(self, msg, message):
        server = message.server

        if not self.check_server(server):
            return False

        handle = Handle(self, message=message)
        await handle.broadcast('announcement', msg)

        return True

    # Export full list of members as CSV
    async def export_members(self, message):
        server = message.server

        if not self.check_server(server):
            return False

        csv = io.BytesIO()
        csv.write('#discord_id\n'.encode())

        members = list(server.members)
        for member in members:
            discord_id = str(member)
            csv.write('{}\n'.format(discord_id).encode())

        csv.seek(0)

        member_count = len(members)
        filename = 'members-{}.csv'.format(self.config['servers'][server.name]['db'])
        msg = '{mention} Here is the list of all {count} members in this Discord server'\
            .format(mention=message.author.mention,
                    count=member_count)

        try:
            await self.client.send_file(message.channel,
                                        csv,
                                        filename=filename,
                                        content=msg)
            print ('Sent member list ({})'.format(member_count))
        except Exception as e:
            print ('ERROR: Failed to send member list ({})'.format(member_count))
            raise e

        csv.close()

        return True

    # Export pick&ban stats for a running cup
    async def export_stats(self, message, cup_name):
        server = message.server

        if not self.check_server(server):
            return False

        db, error = self.get_cup_db(server, cup_name)
        if error:
            await self.reply(message, error)
            return False

        csv = io.BytesIO()
        csv.write('#action,map,count\n'.encode())

        banned_maps = {}
        picked_maps = {}
        sides = { 'attacks': 0, 'defends': 0 }

        for match in db['matches'].values():
            if not match.is_done():
                continue

            for m in match.banned_maps:
                if m in banned_maps:
                    banned_maps[m] += 1
                else:
                    banned_maps[m] = 1
            for m in match.picked_maps:
                if m in picked_maps:
                    picked_maps[m] += 1
                else:
                    picked_maps[m] = 1

            for s in match.picked_sides:
                sides[s] += 1

        for bm, count in banned_maps.items():
            csv.write('ban,{map},{count}\n'\
                      .format(map=bm,
                              count=count).encode())

        for pm, count in picked_maps.items():
            csv.write('pick,{map},{count}\n'\
                      .format(map=pm,
                              count=count).encode())

        for cs, count in sides.items():
            csv.write('side,{side},{count}\n'\
                      .format(side=cs,
                              count=count).encode())

        csv.seek(0)

        filename = 'stats-{}-{}.csv'\
            .format(self.config['servers'][server.name]['db'],
                    db['cup'].name)
        msg = '{mention} Here are the pick&ban stats'\
            .format(mention=message.author.mention)

        try:
            await self.client.send_file(message.channel,
                                        csv,
                                        filename=filename,
                                        content=msg)
            print ('Sent pick&ban stats')
        except Exception as e:
            print ('ERROR: Failed to send pick&ban stats')
            raise e

        csv.close()

        return True

    def discord_validate(self, did):
        return not did.startswith('@') \
            and not did.startswith('#') \
            and re.match('^.*[^ ]#[0-9]+$', did)

    # Check a CSV file before launching a cup
    # 1. Parse the CSV file
    # 2. For all parsed captains:
    #    A. List all captains not in server
    #    B. List all captains with invalid Discord ID
    #    C. List all captains with no Discord ID.
    async def check_cup(self, message, cup_name, attachment, checkonly=True):
        server = message.server

        if not self.check_server(server):
            return False

        reply = await self.reply(message,
                                 '{l} Checking members{imported}...'\
                                 .format(l=self.emotes['loading'],
                                         imported=' before import' if not checkonly else ''))

        print('Checking members for cup {cup}'.format(cup=cup_name))

        if attachment:
            # Fetch the CSV file and parse it
            r = requests.get(attachment['url'])

            print(r.encoding) # TODO Check UTF8 / ISO problems
            r.encoding = 'utf-8'

            csv = io.StringIO(r.text)
            captains, groups = self.parse_teams(server, csv, None)
            csv.close()

            # Save it for later in a scratchpad
            self.checked_cups[cup_name] = (captains, groups)

        elif cup_name in self.checked_cups:
            captains, groups = self.checked_cups[cup_name]

        else:
            await self.reply(message, 'I do not remember checking that cup and you did not attach a CSV file to check ¯\_(ツ)_/¯')
            await self.client.delete_message(reply)
            return False

        members = list(server.members)

        # If this is not just a check, update database
        if not checkonly:
            captains, groups = self.checked_cups[cup_name]

            db, error = self.get_cup_db(server, cup_name)
            if error:
                await self.reply(message, error)
                return False

            for group_id, group in groups.items():
                role_color = self.get_role_color('group')
                group_role = await self.get_or_create_role(server, group.name, color=role_color)
                group.role = group_role

            for discord_id, captain in captains.items():
                captain.cup = db['cup']

            db['captains'] = captains
            db['groups'] = groups # TODO cup-ref?

            await self.create_all_teams(server, cup_name)

            # Visit all members of the server
            for member in members:
                await self.handle_member_join(member, db)

            # If cup was in scratchpad, remove it
            if cup_name in self.checked_cups:
                del self.checked_cups[cup_name]

        # Collect missing captain Discords
        missing_discords = []
        invalid_discords = []
        missing_members = []
        for captain in captains.values():
            group_s = ', Group {}'.format(captain.group.role.name) if captain.group and captain.group.role else ''
            if not captain.discord:
                missing_discords.append('`{n}` (Team `{t}`{g})'\
                                        .format(n=captain.nickname,
                                                t=captain.team_name,
                                                g=group_s))
            elif not self.discord_validate(captain.discord):
                invalid_discords.append('`{n}` (Team `{t}`{g}): `{d}`'\
                                        .format(n=captain.nickname,
                                                t=captain.team_name,
                                                d=captain.discord,
                                                g=group_s))
            elif not discord.utils.find(lambda m: str(m) == captain.discord, members):
                missing_members.append('`{n}` (Team `{t}`{g}): `{d}`'\
                                       .format(n=captain.nickname,
                                               t=captain.team_name,
                                               d=captain.discord,
                                               g=group_s))

        report = ''

        if len(missing_members) > 0:
            report = '{}\n\n:shrug: **Missing members**\n• {}'.format(report, '\n• '.join(missing_members))
        if len(missing_discords) > 0:
            report = '{}\n\n:mag: **Missing Discord IDs**\n• {}'.format(report, '\n• '.join(missing_discords))
        if len(invalid_discords) > 0:
            report = '{}\n\n:no_entry_sign: **Invalid Discord IDs**\n• {}'.format(report, '\n• '.join(invalid_discords))

        total = len(captains)
        if checkonly:
            title = 'Checked cup {}'.format(cup_name)
            report = '{r}\n\n**Ready to import {count}/{total} teams.**\nUse `!start_cup {cup}` to start it.'.format(
                r=report,
                cup=cup_name,
                total=total,
                count=total \
                - len(missing_members) \
                - len(missing_discords) \
                - len(invalid_discords))
        else:
            title = 'Started cup {}'.format(cup_name)
            report = '{r}\n\n**Imported {count}/{total} teams**.'.format(
                r=report,
                total=total,
                count=total \
                - len(missing_members) \
                - len(missing_discords) \
                - len(invalid_discords))

        #await self.reply(message, report)
        await self.embed(message, title, report)
        await self.client.delete_message(reply)

        return True

    # Start a cup
    async def start_cup(self, message, cup_name, attachment):
        server = message.server

        if not self.check_server(server):
            return False

        cup_role_name = self.get_role_name('captain', arg=cup_name)
        role_color = self.get_role_color('captain')
        cup_role = await self.get_or_create_role(server, cup_role_name, color=role_color)
        cup = Cup(cup_name, cup_role)

        self.open_cup_db(server, cup)

        if not await self.check_cup(message, cup_name, attachment, checkonly=False):
            return False

        # TODO do actual things for the cup
        return True

    # List active cups
    async def list_cups(self, message):
        server = message.server

        if not self.check_server(server):
            return False

        error = False
        body = ''

        if len(self.db[server]['cups']) > 0 or len(self.checked_cups) > 0:
            title = 'Currently running cups'
            for cup_name, cup in self.db[server]['cups'].items():
                body = '{p}\n• `{name}`'\
                    .format(p=body,
                            name=cup_name)
            for cup_name, tpl in self.checked_cups.items():
                body = '{p}\n• `{name}` _(checked only)_'\
                    .format(p=body,
                            name=cup_name)
        else:
            title = 'No cup is currently running.'
            error = True

        await self.embed(message, title, body, error=error)

        return True

    # Stop a running cup
    async def stop_cup(self, message, cup_name):
        server = message.server

        if not self.check_server(server):
            return False

        if not await self.wipe_teams(message, cup_name):
            return False

        if not await self.wipe_matches(message, cup_name):
            return False

        if not self.close_cup_db(server, cup_name):
            await self.reply(message, 'No such cup')
            return False

        # TODO do actual things when closing the cup
        return True
