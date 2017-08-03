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

import discord
import asyncio
import csv
import random

from teamcaptain import TeamCaptain
from match import Match, MatchBo3
from inputs import sanitize_input, translit_input

welcome_message_bo1 =\
"""
Welcome {m_teamA} and {m_teamB}!
-- Match **BEST OF 1** --
This text channel will be used by the judge and team captains to exchange anything about the match between {teamA} and {teamB}.
This sequence is made using the `!ban` command team by team until one remains.
Last team to ban also needs to chose the side they will play on using `!side xxxx` (attack or defend).

For instance, team A types `!ban Pyramid` which will then ban the map _Pyramid_ from the match, team B types `!ban d17` which will ban the map D-17, and so on, until only one map remains. team B then picks the side using `!side attack`.
"""

welcome_message_bo3 =\
"""
Welcome {m_teamA} and {m_teamB}!
-- Match **BEST OF 3** --
This text channel will be used by the judge and team captains to exchange anything about the match between {teamA} and {teamB}.
This sequence is made using the `!pick`, `!ban` and `!side` commands one by one using the following order:

 - {teamA} bans, {teamB} bans,
 - {teamA} picks, {teamB} picks,
 - {teamA} bans, {teamB} bans,
 - Last map remaining is the draw map,
 - {teamB} picks the side (attack or defend).

For instance, team A types `!ban Yard` which will then ban the map _Yard_ from the match, team B types `!ban d17` which will ban the map D-17. team A would then type `!pick Destination`, picking the first map and so on, until only one map remains, which will be the tie-breaker map. team B then picks the side using `!side attack`.
"""

class RoleKeeper:
    def __init__(self, client, config):
        self.client = client
        self.matches = {}
        self.config = config
        self.groups = {}
        self.captains = {}

    # Parse members from CSV file
    def parse_teams(self, server, filepath):
        captains = {}
        groups = {}


        with open(filepath) as csvfile:
            reader = csv.reader(csvfile, delimiter=',', quotechar='"')
            for row in reader:
                # Skip empty lines and lines starting with #
                if len(row) <= 0 or row[0].startswith('#'):
                    continue

                discord_id = row[0].strip()
                team_name = row[1].strip()
                nickname = row[2].strip()
                group_id = row[3].strip()

                captains[discord_id] = \
                    TeamCaptain(discord_id, team_name, nickname, group_id)

                # If group is new to us, cache it
                if group_id not in groups:
                    group_name = self.config['roles']['group'].format(group_id)
                    group = discord.utils.get(server.roles, name=group_name)
                    print('{id}: {g}'.format(id=group_id, g=group))
                    groups[group_id] = group

        print('Parsed teams:')
        # Print parsed members
        for m in captains:
            print('-> {}'.format(captains[m]))

        self.captains[server] = captains
        self.groups[server] = groups

    # Acknowledgement that we are succesfully connected to Discord
    async def on_ready(self):
        self.groups = {}

        for server in self.client.servers:
            print('Server: {}'.format(server))
            await self.refresh(server)

    async def on_dm(self, message):
        # If it is us sending the DM, exit
        if message.author == self.client.user:
            return

        # Apologize
        print('PM from {}: {}'.format(message.author, message.content))
        await self.reply(message,
                       ''':wave: Hello there!
                       I am sorry, I cannot answer your question, I am just a bot!
                       Feel free to ask a referee or admin instead :robot:''')

    async def on_member_join(self, member):
        if member.server.name not in self.config['servers']:
            return

        await self.handle_member_join(member)

    def cache_role(self, server, ref):
        role_name = self.config['roles'][ref]
        self.groups[server][ref] = discord.utils.get(server.roles, name=role_name)
        if not self.groups[server][ref]:
            print ('WARNING: Missing role "{}" in {}'.format(role_name, server.name))

    # Refresh internal structures
    # 1. Reparse team captain file
    # 2. Refill group cache
    # 3. Visit all members with no role
    async def refresh(self, server):
        if server.name not in self.config['servers']:
            print ('WARNING: Server "{}" not configured!'.format(server.name))
            return

        self.groups[server] = {}

        # Reparse team captain file
        self.parse_teams(server, self.config['servers'][server.name]['captains'])

        # Refill group cache
        self.cache_role(server, 'captain')
        self.cache_role(server, 'referee')
        self.cache_role(server, 'streamer')

        # Visit all members with no role
        for member in server.members:
            if len(member.roles) == 1:
                print('- Member without role: {}'.format(member))
                await self.handle_member_join(member)

    # Go through the parsed captain list and create all team roles
    async def create_all_roles(self, server):
        for _, captain in self.captains[server].items():
            await self.create_team_role(server, captain.team)

    # Create team captain role
    async def create_team_role(self, server, team_name):
        role_name = '{} team'.format(team_name)
        role = discord.utils.get(server.roles, name=role_name)
        if not role:
            role = await self.client.create_role(
                server,
                name=role_name,
                permissions=discord.Permissions.none(),
                mentionable=True)

            print('Create new role <{role}>'\
                  .format(role=role_name))

        return role

    # Whenever a new member joins into the Discord server
    # 1. Create a user group just for the Team captain
    # 2. Assign the special group to that Team captain
    # 3. Assign the global group to that Team captain
    # 4. Change nickname of Team captain
    async def handle_member_join(self, member):
        discord_id = str(member)
        server = member.server

        if discord_id not in self.captains[server]:
            print('WARNING: New user "{}" not in captain list'\
                  .format(discord_id))
            return

        print('Team captain "{}" joined server'\
              .format(discord_id))

        captain = self.captains[server][discord_id]

        # Create role
        team_role = await self.create_team_role(server, captain.team)

        # Assign user roles
        group_role = self.groups[server][captain.group]
        captain_role = self.groups[server]['captain']

        if team_role and captain_role and group_role:
            await self.client.add_roles(member, team_role, captain_role, group_role)
        else:
            print('ERROR: Missing one role out of R:{} C:{} G:{}'\
                  .format(team_role, captain_role, group_role))

        print('Assigned role <{role}> to "{id}"'\
              .format(role=team_role.name, id=discord_id))

        # Change nickname of team captain
        nickname = '{}'.format(captain.nickname)
        await self.client.change_nickname(member, nickname)

        print('Renamed "{id}" to "{nick}"'\
              .format(id=discord_id, nick=nickname))


    # Reply to a message in a channel
    async def reply(self, message, reply):
        return await self.client.send_message(
            message.channel,
            '{} {}'.format(message.author.mention, reply))

    # Create a match against 2 teams
    # 1. Create the text channel
    # 2. Add permissions to read/send to both teams, and the judge
    # 3. Send welcome message
    # 4. Register the match to internal logic for commands like !ban x !pick x
    async def matchup(self, server, _teamA, _teamB, is_bo3=False):
        randomized = [ _teamA, _teamB ]
        random.shuffle(randomized)
        teamA, teamB = randomized[0], randomized[1]

        teamA_name_safe = sanitize_input(translit_input(teamA.name.replace(' team', '')))
        teamB_name_safe = sanitize_input(translit_input(teamB.name.replace(' team', '')))
        channel_name = 'match_{}_vs_{}'.format(teamA_name_safe, teamB_name_safe)

        ref_role = self.groups[server]['referee']

        read_perms = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        no_perms = discord.PermissionOverwrite(read_messages=False)

        channel = discord.utils.get(server.channels, name=channel_name)

        if not channel:
            channel = await self.client.create_channel(
                server,
                channel_name,
                (teamA, read_perms),
                (teamB, read_perms),
                (server.default_role, no_perms),
                (server.me, read_perms),
                (ref_role, read_perms))

            print('Created channel "<{channel}>"'\
                  .format(channel=channel.name))
        else:
            print('Reusing existing channel "<{channel}>"'\
                  .format(channel=channel.name))

        maps = self.config['servers'][server.name]['maps']

        if is_bo3:
            match = MatchBo3(teamA, teamB, maps)
            template = welcome_message_bo3
        else:
            match = Match(teamA, teamB, maps)
            template = welcome_message_bo1

        self.matches[channel_name] = match
        handle = Handle(self, None, channel)
        msg = template.format(m_teamA=teamA.mention,
                              m_teamB=teamB.mention,
                              teamA=teamA.name,
                              teamB=teamB.name,
                              maps='\n'.join([ ' - {}'.format(m) for m in maps ]))

        await self.client.send_message(channel, msg)
        await match.begin(handle)

    # Returns if a member is a team captain in the given channel
    def is_captain_in_match(self, member, channel):
        if channel.name not in self.matches:
            return False

        return self.matches[channel.name].is_in_match(member)

    # Ban a map
    async def ban_map(self, member, channel, map_unsafe, force=False):
        banned_map_safe = sanitize_input(translit_input(map_unsafe))

        if channel.name not in self.matches:
            return

        handle = Handle(self, member, channel)
        await self.matches[channel.name].ban_map(handle, banned_map_safe, force)

    # Pick a map
    async def pick_map(self, member, channel, map_unsafe, force=False):
        picked_map_safe = sanitize_input(translit_input(map_unsafe))

        if channel.name not in self.matches:
            return

        handle = Handle(self, member, channel)
        await self.matches[channel.name].pick_map(handle, picked_map_safe, force)

    # Choose sides
    async def choose_side(self, member, channel, side_unsafe, force=False):
        side_safe = sanitize_input(translit_input(side_unsafe))

        if channel.name not in self.matches:
            return

        handle = Handle(self, member, channel)
        await self.matches[channel.name].choose_side(handle, side_safe, force)

    # Broadcast information that the match is or will be streamed
    # 1. Notify captains match will be streamed
    async def stream_match(self, message, match_id):
        member = message.author
        channel = discord.utils.get(member.server.channels, name=match_id)

        # If we found a channel with the given name
        if channel:

            # 1. Notify captains match will be streamed
            await self.client.send_message(
                channel, ':eye::popcorn: _**{}** will stream this match!_ :movie_camera::satellite:\n'
                ':arrow_forward: _8.6 Teams participating in a streamed match get an additional 10 minutes to prepare; the time of the match may change per the decision of the Staff/Organizers._\n'\
                .format(member.nick if member.nick else member.name))
            await self.reply(message, 'roger!')

            print('Notified "{channel}" the match will be streamed by "{member}"'\
                  .format(channel=channel.name,
                          member=str(member)))
        else:
            await self.reply(message, 'This match does not exist!')


    # Remove all teams
    # 1. Delete all existing team roles
    # 2. Find all members with role team captain
    # 3. Remove group role from member
    # 4. Remove team captain role from member
    # 5. Reset member nickname
    async def wipe_teams(self, server):
        captain_role = self.groups[server]['captain']

        # 1. Delete all existing team roles
        for role in server.roles:
            if role.name.endswith(' team'):
                await self.client.delete_role(server, role)
                print ('Deleted role "{role}"'\
                       .format(role=role.name))

        # 2. Find all members with role team captain
        for member in server.members:
            member_name = str(member)

            if captain_role in member.roles:

                print ('Found member "{member}" with role "{role}"'\
                       .format(member=member_name,
                               role=captain_role.name))

                # 3. Remove group role from member
                group_role = None
                discord_id = member_name
                if discord_id in self.captains[server]:
                    for role in member.roles:
                        if role.name.startswith('Group '): # TODO, use or remove /group
                            group_role = role
                            break

                    #captain = self.captains[server][discord_id]
                    #group_role = self.groups[server][captain.group]
                    del self.captains[server][discord_id]

                crole_name = captain_role.name
                grole_name = group_role.name if group_role else '<no group>'

                # 4. Remove team captain role from member
                try:
                    await self.client.remove_roles(member, captain_role, group_role)
                    print ('Remove roles "{crole}" and "{grole}" from "{member}"'\
                           .format(member=member_name,
                                   crole=crole_name,
                                   grole=grole_name))
                except:
                    pass

                # 5. Reset member nickname
                try:
                    await self.client.change_nickname(member, None)
                    print ('Reset nickname for "{member}"'\
                           .format(member=member_name))
                except:
                    pass

    # Remove all match rooms
    # 1. Find all channels matching match_* pattern
    # 2. Delete channel
    async def wipe_matches(self, server):
        channels_to_delete = [ ch for ch  in server.channels if ch.name.startswith('match_') ]
        for channel in channels_to_delete:
                await self.client.delete_channel(channel)
                print ('Deleted channel "{channel}"'\
                       .format(channel=channel.name))

    # Remove all messages that are not pinned in a given channel
    async def wipe_messages(self, message, channel):
        count = 0
        try:
            messages_to_delete = [
                msg async for msg in self.client.logs_from(channel) if not msg.pinned ]
            count = len(messages_to_delete)
        except:
            print('WARNING: No permission to read logs from "{}"'.format(channel.name))
            return

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

    # Announcement message
    async def announce(self, msg, message):
        handle = Handle(self, message.author, message.channel)
        await handle.broadcast('announcement', msg)



class Handle:
    def __init__(self, bot, member, channel):
        self.bot = bot
        self.member = member
        self.channel = channel

        self.team = None

        if member:
            try:
                self.team = next(role for role in member.roles if role.name.endswith(' team'))
            except StopIteration:
                pass

    async def reply(self, msg):
        return await self.send('{} {}'.format(self.member.mention, msg))

    async def send(self, msg):
        try:
            return await self.bot.client.send_message(self.channel, msg)
        except discord.errors.HTTPException as e:
            print('WARNING: HTTPexception: {}'.format(str(e)))
            await asyncio.sleep(10)
            return await self.send(msg)

    async def broadcast(self, bcast_id, msg):
        channels = []
        try:
            channels = self.bot.config['servers'][self.channel.server.name]['rooms'][bcast_id]
        except:
            print('WARNING: No broadcast configuration for "{}"'.format(bcast_id))
            pass

        for channel_name in channels:
            channel = discord.utils.get(self.channel.server.channels, name=channel_name)
            if channel:
                try:
                    await self.bot.client.send_message(channel, msg)
                except:
                    print('WARNING: No permission to write in "{}"'.format(channel_name))
                    pass
            else:
                print ('WARNING: Missing channel {}'.format(channel_name))
