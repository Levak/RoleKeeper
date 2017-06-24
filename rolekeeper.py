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

    async def on_member_join(self, member):
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
        self.groups[server] = {}

        # Reparse team captain file
        self.parse_teams(server, self.config['team_captain_file'][server.name])

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
        discord_id = '{}#{}'.format(member.name, member.discriminator)
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
        await self.client.send_message(
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

        maps = self.config['maps']

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
        await match.status(handle)

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
        await self.send('{} {}'.format(self.member.mention, msg))

    async def send(self, msg):
        await self.bot.client.send_message(self.channel, msg)
