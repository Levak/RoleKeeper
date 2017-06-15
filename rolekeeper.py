import discord
import asyncio
import csv
import re
import random

from teamcaptain import TeamCaptain
from match import Match, MatchBo3

maps = [ 'Yard', 'D-17', 'Factory', 'District', 'Destination', 'Palace', 'Pyramide' ]

welcome_message_normal =\
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
    def __init__(self, client, teams_csv):
        self.client = client
        self.parse_teams(teams_csv)
        self.matches = {}

    # Parse members from CSV file
    def parse_teams(self, filepath):

        self.captains={}
        with open(filepath) as csvfile:
            reader = csv.reader(csvfile, delimiter=',', quotechar='"')
            for row in reader:
                if len(row) <= 0:
                    continue
                if row[0].startswith('#'):
                    continue
                discord_id = row[0].strip()
                team_name = row[1].strip()
                nickname = row[2].strip()
                group = row[3].strip()
                self.captains[discord_id] = TeamCaptain(discord_id, team_name, nickname, group)


        print('Parsed teams:')
        # Print parsed members
        for m in self.captains:
            print('-> {}'.format(self.captains[m]))

    # Acknowledgement that we are succesfully connected to Discord
    async def on_ready(self):
        self.groups = {}

        for server in self.client.servers:
            print('Server: {}'.format(server))

            self.groups[server] = {}
            for g in [ 'A', 'B', 'C', 'D', 'E', 'F' ]:
                group_name = 'Group {}'.format(g)
                group = discord.utils.get(server.roles, name=group_name)
                print(group)
                self.groups[server][g] = group

            self.groups[server]['captain'] = discord.utils.get(server.roles, name='Team Captains')
            self.groups[server]['modreferee'] = discord.utils.get(server.roles, name='WF_mods referees')
            self.groups[server]['referee'] = discord.utils.get(server.roles, name='Referees')

            await self.refresh(server)

    async def on_member_join(self, member):
        await self.handle_member_join(member)

    async def refresh(self, server):
        for member in server.members:
            if len(member.roles) == 1:
                print('- Member without role: {}'.format(member))
                await self.handle_member_join(member)

    async def create_all_roles(self, server):
        for _, captain in self.captains.items():
            # Create role
            role_name = '{} team'.format(captain.team)
            role = discord.utils.get(server.roles, name=role_name)
            if not role:
                role = await self.client.create_role(
                    server,
                    name=role_name,
                    permissions=discord.Permissions.none(),
                    mentionable=True)

                print('Create new role <{role}>'\
                      .format(role=role_name))


    # Whenever a new member joins into the Discord server
    # 1. Create a user group just for the Team captain
    # 2. Assign the special group to that Team captain
    # 3. Assign the global group to that Team captain
    # 4. Change nickname of Team captain
    async def handle_member_join(self, member):
        discord_id = '{}#{}'.format(member.name, member.discriminator)
        if discord_id not in self.captains:
            print('WARNING: New user "{}" not in captain list'\
                  .format(discord_id))
            return

        print('Team captain "{}" joined server'\
              .format(discord_id))

        captain = self.captains[discord_id]
        server = member.server

        # Create role
        role_name = '{} team'.format(captain.team)
        role = discord.utils.get(server.roles, name=role_name)
        if not role:
            role = await self.client.create_role(
                member.server,
                name=role_name,
                permissions=discord.Permissions.none(),
                mentionable=True)

            print('Create new role <{role}>'\
                  .format(role=role_name))

        # Assign user roles
        group_role = self.groups[server][captain.group]
        captain_role = self.groups[server]['captain']

        if role and captain_role and group_role:
            await self.client.add_roles(member, role, captain_role, group_role)
        else:
            print('ERROR: Missing one role out of R:{} C:{} G:{}'\
                  .format(role, captain_role, group_role))

        print('Assigned role <{role}> to "{id}"'\
              .format(role=role_name, id=discord_id))

        # Change nickname of team captain
        nickname = '{}'.format(captain.nickname)
        await self.client.change_nickname(member, nickname)

        print('Renamed "{id}" to "{nick}"'\
              .format(id=discord_id, nick=nickname))


    # Reply to a message in a channel
    async def reply(self, message, reply):
        await self.client.send_message(
            message.channel,
            '{} {}'.format(message.author.mention, reply))

    # Create a match against 2 teams
    # 1. Create the text channel
    # 2. Add permissions to read/send to both teams, and the judge
    # 3. Send welcome message
    # 4. TODO Register the match to internal logic for commands like !ban x !pick x
    async def matchup(self, server, _teamA, _teamB, is_bo3=False):
        randomized = [ _teamA, _teamB ]
        random.shuffle(randomized)
        teamA, teamB = randomized[0], randomized[1]

        unsafe_chars = re.compile(r'[^a-zA-Z0-9]')
        teamA_name_safe = unsafe_chars.sub('', teamA.name.replace(' team', '').lower())
        teamB_name_safe = unsafe_chars.sub('', teamB.name.replace(' team', '').lower())
        channel_name = 'match_{}_vs_{}'.format(teamA_name_safe, teamB_name_safe)

        mod_role = self.groups[server]['modreferee']
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
                (mod_role, read_perms),
                (ref_role, read_perms))

            print('Created channel "<{channel}>"'\
                  .format(channel=channel.name))
        else:
            print('Reusing existing channel "<{channel}>"'\
                  .format(channel=channel.name))

        if is_bo3:
            match = MatchBo3(teamA, teamB, maps)
            template = welcome_message_bo3
        else:
            match = Match(teamA, teamB, maps)
            template = welcome_message_normal

        self.matches[channel_name] = match
        handle = Handle(self, None, channel)
        msg = template.format(m_teamA=teamA.mention,
                              m_teamB=teamB.mention,
                              teamA=teamA.name,
                              teamB=teamB.name,
                              maps='\n'.join([ ' - {}'.format(m) for m in maps ]))

        await self.client.send_message(channel, msg)
        await match.status(handle)

    # Returns if a member is a team captain in the given channel
    def is_captain_in_match(self, member, channel):
        if channel.name not in self.matches:
            return False

        return self.matches[channel.name].is_in_match(member)

    # Ban a map
    async def ban_map(self, member, channel, map_unsafe, force=False):
        unsafe_chars = re.compile(r'[^a-zA-Z0-9]')
        banned_map_safe = unsafe_chars.sub('', map_unsafe.lower())

        if channel.name not in self.matches:
            return

        handle = Handle(self, member, channel)
        await self.matches[channel.name].ban_map(handle, banned_map_safe, force)

    # Pick a map
    async def pick_map(self, member, channel, map_unsafe, force=False):
        unsafe_chars = re.compile(r'[^a-zA-Z0-9]')
        picked_map_safe = unsafe_chars.sub('', map_unsafe.lower())

        if channel.name not in self.matches:
            return

        handle = Handle(self, member, channel)
        await self.matches[channel.name].pick_map(handle, picked_map_safe, force)

    # Choose sides
    async def choose_side(self, member, channel, side_unsafe, force=False):
        unsafe_chars = re.compile(r'[^a-zA-Z0-9]')
        side_safe = unsafe_chars.sub('', side_unsafe.lower())

        if channel.name not in self.matches:
            return

        handle = Handle(self, member, channel)
        await self.matches[channel.name].choose_side(handle, side_safe, force)

class Handle:
    def __init__(self, bot, member, channel):
        self.bot = bot
        self.member = member
        self.channel = channel

        if member:
            self.team = next(role for role in member.roles if role.name.endswith(' team'))
        else:
            self.team = None

    async def reply(self, msg):
        await self.bot.client.send_message(self.channel, '{} {}'.format(self.member.mention, msg))

    async def send(self, msg):
        await self.bot.client.send_message(self.channel, msg)
