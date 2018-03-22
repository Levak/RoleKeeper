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

from team import Team, TeamCaptain
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
    def parse_teams(self, server, csvfile): # TODO cup
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

                captains[key] = \
                    TeamCaptain(discord_id, team_name, nickname, group_id)

                # If group is new to us, cache it
                if group_id and group_id not in groups:
                    group_name = self.config['roles']['group'].format(group_id) # TODO cup
                    group = discord.utils.get(server.roles, name=group_name)
                    print('{id}: {g}'.format(id=group_id, g=group))
                    groups[group_id] = group

        print('Parsed teams:')
        # Print parsed members
        for m in captains:
            print('-> {}'.format(captains[m]))

        return captains, groups

    def open_db(self, server):
        if server in self.db and self.db[server]:
            self.db[server].close()

        self.db[server] = open_db(self.config['servers'][server.name]['db'])

        if 'matches' not in self.db[server]:
            self.db[server]['matches'] = {}

        if 'teams' not in self.db[server]:
            self.db[server]['teams'] = {}

        if 'captains' not in self.db[server]:
            self.db[server]['captains'] = {}

        if 'groups' not in self.db[server]:
            self.db[server]['groups'] = {}

        if 'sroles' not in self.db[server]:
            self.db[server]['sroles'] = {}

        # Refill group cache
        self.db[server]['sroles'] = {}
        self.cache_special_role(server, 'captain')
        self.cache_special_role(server, 'referee')
        self.cache_special_role(server, 'streamer')

    # Acknowledgement that we are succesfully connected to Discord
    async def on_ready(self):

        for server in self.client.servers:
            print('Server: {}'.format(server))

            if self.check_server(server):
                self.open_db(server)

            #await self.refresh(server)

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

    def cache_special_role(self, server, role_id):
        role_name = self.config['roles'][role_id]
        role = discord.utils.get(server.roles, name=role_name)
        self.db[server]['sroles'][role_id] = role
        if not self.db[server]['sroles'][role_id]:
            print ('WARNING: Missing role "{}" in {}'.format(role_name, server.name))

    def get_special_role(self, server, role_id):
        if role_id in self.db[server]['sroles']:
            return self.db[server]['sroles'][role_id]
        return None

    async def add_group(self, message, server, group_id): # TODO cup
        if not self.check_server(server):
            return False

        # Check if group exists
        if group_id in self.db[server]['groups']:
            await self.reply(message, 'Group "{}" already exists'.format(group_id))
            return False

        # If group is new to us, cache it
        group_name = self.config['roles']['group'].format(group_id) # TODO cup
        group = discord.utils.get(server.roles, name=group_name)

        if not group:
            await self.reply(message, 'Role "{}" does not exist'.format(group_name))
            return False

        self.db[server]['groups'][group_id] = group

        return True

    async def remove_group(self, message, server, group_id): # TODO cup
        if not self.check_server(server):
            return False

        # Check if group exists
        if group_id not in self.db[server]['groups']:
            await self.reply(message, 'Group "{}" does not exist'.format(group_id))
            return False

        # TODO what to do with all the captains in that group?

        del self.db[server]['groups'][group_id]

        return True

    async def add_captain(self, message, server, member, team, nick, group): # TODO cup
        if not self.check_server(server):
            return False

        discord_id = str(member)

        # If captain already exists, remove him
        if discord_id in self.db[server]['captains']:
            await self.remove_captain(message, server, member)

        # Check if destination group exists
        if group not in self.db[server]['groups']:
            await self.reply(message, 'Group "{}" does not exist'.format(group))
            return False

        # Add new captain to the list
        self.db[server]['captains'][discord_id] = \
            TeamCaptain(discord_id, team, nick, group)

        # Trigger update on member
        await self.handle_member_join(member)

        return True

    async def remove_captain(self, message, server, member):
        if not self.check_server(server):
            return False

        discord_id = str(member)

        if discord_id not in self.db[server]['captains']:
            await self.reply(message, '{} is not a known captain'.format(member.mention))
            return False

        captain = self.db[server]['captains'][discord_id]

        captain_role = self.get_special_role(server, 'captain') # TODO cup, which cup? not special?
        group_role = self.db[server]['groups'][captain.group] if captain.group else None
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
        if not any(r == team_role for m in server.members for r in m.roles):
            try:
                await self.client.delete_role(server, team_role)
                print ('Deleted role "{role}"'\
                       .format(role=trole_name))
            except:
                print ('WARNING: Failed to delete role "{role}"'\
                       .format(role=trole_name))
                pass
            del self.db[server]['teams'][trole_name]

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
        del self.db[server]['captains'][discord_id]

        return True

    # Refresh internal structures
    # 1. Reparse team captain file
    # 2. Refill group cache
    # 3. Visit all members with no role
    async def refresh(self, server):
        if not self.check_server(server):
            return False

        # TODO cups

        # TODO remove, use CSV upload instead
        # Reparse team captain file
        with open(self.config['servers'][server.name]['captains']) as csvfile:
            captains, groups = self.parse_teams(server, csvfile)

            self.db[server]['captains'] = captains # TODO Add cup
            self.db[server]['groups'] = groups # TODO cup/ref?

        await self.create_all_teams(server)

        # Visit all members with no role
        members = list(server.members)
        for member in members:
            if len(member.roles) == 1:
                print('- Member without role: {}'.format(member))
                await self.handle_member_join(member)


        return True

    # Go through the parsed captain list and create all team roles
    # TODO remove this
    async def create_all_teams(self, server):
        if not self.check_server(server):
            return False

        self.db[server]['teams'] = {}
        for _, captain in self.db[server]['captains'].items():
            team = await self.create_team(server, captain.team_name)
            captain.team = team

        return True

    # Create team captain role
    async def create_team(self, server, team_name):
        role_name = self.config['roles']['team'].format(team_name)

        if role_name in self.db[server]['teams']:
            return self.db[server]['teams'][role_name]

        role = discord.utils.get(server.roles, name=role_name)

        if not role:
            role = await self.client.create_role(
                server,
                name=role_name,
                permissions=discord.Permissions.none(),
                mentionable=True)

            print('Create new role <{role}>'\
                  .format(role=role_name))

        role.name = role_name # This is a hotfix

        team = Team(team_name, role)
        self.db[server]['teams'][role_name] = team

        return team

    # Whenever a new member joins into the Discord server
    # 1. Create a user group just for the Team captain
    # 2. Assign the special group to that Team captain
    # 3. Assign the global group to that Team captain
    # 4. Change nickname of Team captain
    async def handle_member_join(self, member):
        discord_id = str(member)
        server = member.server

        # TODO find cup from discord_id

        if discord_id not in self.db[server]['captains']:
            #print('WARNING: New user "{}" not in captain list'\
            #      .format(discord_id))
            return

        print('Team captain "{}" joined server'\
              .format(discord_id))

        captain = self.db[server]['captains'][discord_id]

        # Create role
        team = await self.create_team(server, captain.team_name) # TODO cup
        team_role = team.role if team else None
        captain.team = team

        # Assign user roles
        group_role = self.db[server]['groups'][captain.group] if captain.group else None
        captain_role = self.get_special_role(server, 'captain') # TODO cup, which cup? not special?

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
    async def matchup(self, message, server, _roleteamA, _roleteamB, mode=MATCH_BO1, flip_coin=False, reuse=REUSE_UNK): # TODO cup
        if not self.check_server(server):
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

        if roleteamA.name in self.db[server]['teams']:
            teamA = self.db[server]['teams'][roleteamA.name]
        else:
            notfound = roleteamA.name

        if roleteamB.name in self.db[server]['teams']:
            teamB = self.db[server]['teams'][roleteamB.name]
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

        if not channel:
            try:
                channel = await self.client.create_channel(
                    server,
                    channel_name,
                    (roleteamA, read_perms),
                    (roleteamB, read_perms),
                    (server.default_role, no_perms),
                    (server.me, read_perms),
                    (ref_role, read_perms))

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

        self.db[server]['matches'][channel_name] = match
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

        if channel.name not in self.db[server]['matches']:
            return False

        return self.db[server]['matches'][channel.name].is_in_match(member)

    # Ban a map
    async def ban_map(self, message, map_unsafe, force=False):
        server = message.author.server
        channel = message.channel
        banned_map_safe = sanitize_input(translit_input(map_unsafe))

        if not self.check_server(server):
            return False

        if channel.name not in self.db[server]['matches']:
            return False

        handle = Handle(self, message=message)
        return await self.db[server]['matches'][channel.name].ban_map(handle, banned_map_safe, force)

    # Pick a map
    async def pick_map(self, message, map_unsafe, force=False):
        server = message.author.server
        channel = message.channel
        picked_map_safe = sanitize_input(translit_input(map_unsafe))

        if not self.check_server(server):
            return False

        if channel.name not in self.db[server]['matches']:
            return False

        handle = Handle(self, message=message)
        return await self.db[server]['matches'][channel.name].pick_map(handle, picked_map_safe, force)

    # Choose sides
    async def choose_side(self, message, side_unsafe, force=False):
        server = message.author.server
        channel = message.channel
        side_safe = sanitize_input(translit_input(side_unsafe))

        if not self.check_server(server):
            return False

        if channel.name not in self.db[server]['matches']:
            return False

        handle = Handle(self, message=message)
        return await self.db[server]['matches'][channel.name].choose_side(handle, side_safe, force)

    # Broadcast information that the match is or will be streamed
    # 1. Notify captains match will be streamed
    # 2. Give permission to streamer to see match room
    # 3. Invite streamer to join it
    async def stream_match(self, message, match_id):
        server = message.server

        if not self.check_server(server):
            return False

        member = message.author
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

        if False: #TODO
            # 2. Give permission to streamer to see match room
            overwrite = discord.PermissionOverwrite()
            overwrite.read_messages = True
            await client.edit_channel_permissions(channel, member, overwrite)

            print('Gave permission to "{member}" to see channel "{channel}"'\
                  .format(channel=channel.name,
                  member=str(member)))

            # 3. Invite streamer to join it
            await self.reply(message, 'Roger! Checkout {}'.format(channel.mention)) #TODO

        return True

    # Remove all teams
    # 1. Delete all existing team roles
    # 2. Find all members with role team captain
    # 3. Remove group role from member
    # 4. Remove team captain and group roles from member
    # 5. Reset member nickname
    async def wipe_teams(self, server):
        if not self.check_server(server):
            return False

        captain_role = self.get_special_role(server, 'captain') # TODO cup, not special?

        # 1. Delete all existing team roles
        for role_name, team in self.db[server]['teams'].items():
            try:
                await self.client.delete_role(server, team.role)
                print ('Deleted role "{role}"'\
                       .format(role=role_name))
            except:
                print ('WARNING: Failed to delete role "{role}"'\
                       .format(role=role_name))
                pass

        self.db[server]['teams'].clear()

        # 2. Find all members with role team captain
        members = list(server.members)
        for member in members: # TODO go through db instead
            discord_id = str(member)
            if discord_id not in self.db[server]['captains']: # TODO cup
                continue

            captain = self.db[server]['captains'][discord_id] # TODO cup

            print ('Found captain "{member}"'\
                   .format(member=discord_id))

            # 3. Remove group role from member
            group_role = self.db[server]['groups'][captain.group] \
                         if captain.group in self.db[server]['groups'] \
                         else None

            crole_name = captain_role.name
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

        self.db[server]['captains'].clear() # TODO cup

        return True

    # Remove all match rooms
    # 1. Find all match channels that where created by the bot for this cup
    # 2. Delete channel
    async def wipe_matches(self, server):
        if not self.check_server(server):
            return False

        for channel_name in self.db[server]['matches'].keys(): # TODO cup
            channel = discord.utils.get(server.channels, name=channel_name)
            if channel:
                try:
                    await self.client.delete_channel(channel)
                    print ('Deleted channel "{channel}"'\
                           .format(channel=channel_name))
                except:
                    print ('WARNING: Fail to Delete channel "{channel}"'\
                           .format(channel=channel_name))

        self.db[server]['matches'].clear() # TODO cup

        return True

    # Remove all messages that are not pinned in a given channel
    async def wipe_messages(self, message, channel):
        server = message.server

        if not self.check_server(server):
            return False

        count = 0
        try:
            messages_to_delete = [
                msg async for msg in self.client.logs_from(channel) if not msg.pinned ]
            count = len(messages_to_delete)
        except:
            print('WARNING: No permission to read logs from "{}"'.format(channel.name))
            return False

        reply = await self.reply(message,
                                 'Clearing {count} message(s)... (this might take a while)'\
                                 .format(count=count))

        for msg in messages_to_delete:
            try:
                await self.client.delete_message(msg)
            except:
                count = count - 1
                print('WARNING: No permission to delete in "{}"'.format(channel.name))
                pass

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
    async def export_stats(self, message): # TODO cup
        server = message.server

        if not self.check_server(server):
            return False

        csv = io.BytesIO()
        csv.write('#action,map,count\n'.encode())

        banned_maps = {}
        picked_maps = {}
        sides = { 'attacks': 0, 'defends': 0 }

        for match in self.db[server]['matches'].values():
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

        filename = 'stats-{}.csv'.format(self.config['servers'][server.name]['db']) # TODO cup
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
    async def check_cup(self, message, name, attachment, checkonly=True):
        server = message.server

        if not self.check_server(server):
            return False

        # Fetch the CSV file and parse it
        r = requests.get(attachment['url'])

        print(r.encoding) # TODO Check UTF8 / ISO problems
        r.encoding = 'utf-8'

        csv = io.StringIO(r.text)
        captains, groups = self.parse_teams(server, csv) # TODO cup
        csv.close()

        members = list(server.members)

        if not checkonly:
            self.db[server]['captains'] = captains # TODO Add cup
            self.db[server]['groups'] = groups # TODO cup/ref?

            await self.create_all_teams(server)

            # Visit all members with no role
            for member in members:
                if True or len(member.roles) == 1:
                    #print('- Member without role: {}'.format(member))
                    await self.handle_member_join(member)

        # Collect missing captain Discords
        missing_discords = []
        invalid_discords = []
        missing_members = []
        for captain in captains.values():
            group_s = ', Group {}'.format(captain.group) if captain.group else ''
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

        total = len(captains)
        report = 'Imported {count}/{total} teams'.format(
            total=total,
            count=total \
            - len(missing_members) \
            - len(missing_discords) \
            - len(invalid_discords))

        if len(missing_members) > 0:
            report = '{}\n\n:shrug: **Missing members**\n - {}'.format(report, '\n - '.join(missing_members))
        if len(missing_discords) > 0:
            report = '{}\n\n:mag: **Missing Discord IDs**\n - {}'.format(report, '\n - '.join(missing_discords))
        if len(invalid_discords) > 0:
            report = '{}\n\n:no_entry_sign: **Invalid Discord IDs**\n - {}'.format(report, '\n - '.join(invalid_discords))

        await self.reply(message, report)

        return True

    # Start a cup
    # TODO: Maybe once the checkup is "ok", don't use CSV?
    async def start_cup(self, message, name, attachment):
        server = message.server

        if not self.check_server(server):
            return False

        if not await self.check_cup(message, name, attachment, checkonly=False):
            return False

        print(name) # TODO cup

        # TODO do actual things for the cup
        return True
