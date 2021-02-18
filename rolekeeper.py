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

import aiohttp
import uuid
import discord
import asyncio
import csv
import random
import re
import io
import datetime
import json
import threading
import atexit
import time

from team import Team, TeamCaptain, Cup, Group
from match import Match, MatchBo2, MatchBo3, MatchBo5, MatchFFA
from inputs import *
from db import open_db
from handle import Handle
from esports_driver import EsportsDriver

import locale_s

# Version of Shelf.sync that doesn't flush the cache
def shelf_invalidate(shelf):
    if shelf.writeback and shelf.cache:
        shelf.writeback = False
        for key, entry in shelf.cache.items():
            shelf[key] = entry
        shelf.writeback = True
    if hasattr(shelf.dict, 'reorganize'):
        shelf.dict.reorganize()
        print('reorganized')
    if hasattr(shelf.dict, 'sync'):
        shelf.dict.sync()
        print('synced')

class RoleKeeper:
    def __init__(self, client, config_file):
        self.client = client
        self.config_file = config_file
        self.db = {}
        self.cache = {}
        self.emotes = {}

        self.checked_cups = {}

        self.config = self.get_config(self.config_file)

        if not self.config:
            return

        for name in [ 'loading' ]:
            if 'emotes' in self.config and name in self.config['emotes']:
                self.emotes[name] = '<a:{name}:{id}>'\
                    .format(name=name,
                            id=self.config['emotes'][name])
            else:
                self.emotes[name] = ''

        for name in [ 'attacks', 'defends' ]:
            if 'emotes' in self.config and name in self.config['emotes']:
                self.emotes[name] = '<:{name}:{id}>'\
                    .format(name=name,
                            id=self.config['emotes'][name])
            else:
                self.emotes[name] = ''

        if 'lang' in self.config:
            locale_s.set_lang(self.config['lang'])

        atexit.register(self.atexit)

        autosave = 30*60
        if 'autosave' in self.config:
            autosave = self.config['autosave']

        self.sync_db_task = self.cron(autosave, self.sync_db)

    def get_config(self, path):
        try:
            with open(path, 'r') as f:
                config = json.load(f)
                return config
        except FileNotFoundError as e:
            print('ERROR while loading config.\n{}: "{}"'\
                  .format(e.strerror, e.filename))
            return None
        except Exception as e:
            print('ERROR while loading config.\n{}: line {} col {}'\
                  .format(e.msg, e.lineno, e.colno))
            return None

    def cron(self, secs, callback, *args):
        async def loop():
            while True:
                await asyncio.sleep(secs)
                callback(*args)

        return self.client.loop.create_task(loop())

    def sync_db(self):
        if self.db:
            for guild, db in self.db.items():
                if 'sroles' in db:
                    del db['sroles']
                print ('Automatically save DB "{}"'.format(guild.name))
                shelf_invalidate(db)

    def atexit(self):
        if self.sync_db_task:
            self.sync_db_task.cancel()

        if self.db:
            for guild, db in self.db.items():
                try:
                    print ('Closing DB "{}"'.format(guild.name))
                except BrokenPipeError:
                    pass
                shelf_invalidate(db)
                db.close()
            self.db = None

    def check_guild(self, guild):
        if guild.name not in self.config['guilds']:
            return False
        return True

    # Parse header from CSV file
    def parse_header(self, header):
        return { e: header.index(e) for e in header }

    # Parse players from CSV file
    def parse_players(self, csvfile, cup=None, groups={}):
        players = []

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

                nickname = row[header['Player']].strip()
                players.append(nickname)

        return players

    # Parse members from CSV file
    def parse_teams(self, csvfile, cup=None, groups={}):
        captains = {}

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
                if 'team_name' in header:
                    team_name = row[header['team_name']].strip()
                elif 'teamname' in header:
                    team_name = row[header['teamname']].strip()
                else:
                    team_name = row[header['team']].strip()
                nickname = row[header['nickname']].strip()

                # Remove extra spaces around the bang (#) sign
                discord_id_parts = discord_id.split('#')
                if len(discord_id_parts) >= 2:
                    discord_id = '{}#{}'.format(discord_id_parts[0].strip(), discord_id_parts[1].strip())

                # If the file doesn't contain groups, not a problem, just ignore it
                if 'group' not in header:
                    group_id = None
                else:
                    group_id = row[header['group']].strip()

                key = uuid.uuid4()
                group = None

                # If group is new to us, cache it
                if group_id:
                    if group_id not in groups:
                        group_name = self.get_role_name('group', arg=group_id)
                        group = Group(group_id, group_name, None)
                        groups[group_id] = group
                    else:
                        group = groups[group_id]

                captains[key] = \
                    TeamCaptain(discord_id, team_name, nickname, group, cup)
                captains[key].key = key # Workaround to avoid extra captain lookup

        print('Parsed teams:')
        # Print parsed members
        for m in captains:
            print('-> {}'.format(captains[m]))

        return captains, groups

    async def get_or_create_role(self, guild, role_name, color=None):
        role = discord.utils.get(guild.roles, name=role_name)

        if not role:
            role = await guild.create_role(
                name=role_name,
                permissions=discord.Permissions.none(),
                mentionable=True,
                color=discord.Colour(color))

            print('Create new role <{role}>'\
                  .format(role=role_name))

        role.name = role_name # This is a hotfix

        return role

    async def open_db(self, guild):
        if guild in self.db and self.db[guild]:
            return

        self.db[guild] = open_db(self.config['guilds'][guild.name]['db'])

        if 'cups' not in self.db[guild]:
            self.db[guild]['cups'] = {}

        for cup_name, cup_db in self.db[guild]['cups'].items():
            if 'cup' in cup_db:
                await cup_db['cup'].resume(guild, self, cup_db)

            if 'driver' in cup_db:
                await cup_db['driver'].resume(guild, self, cup_db)

            if 'teams' in cup_db:
                for _, team in cup_db['teams'].items():
                    await team.resume(guild, self, cup_db)

            if 'groups' in cup_db:
                for _, group in cup_db['groups'].items():
                    await group.resume(guild, self, cup_db)

            if 'captains' in cup_db:
                for _, captain in cup_db['captains'].items():
                    await captain.resume(guild, self, cup_db)

            if 'matches' in cup_db:
                for _, match in cup_db['matches'].items():
                    await match.resume(guild, self, cup_db)

        # Refill group cache
        self.cache_special_role(guild, 'referee')
        self.cache_special_role(guild, 'coreferee')
        self.cache_special_role(guild, 'streamer')

    def open_cup_db(self, guild, cup):
        cup.name = cup.name.upper()
        if cup.name not in self.db[guild]['cups']:
            self.db[guild]['cups'][cup.name] = { 'cup': cup }

        db = self.db[guild]['cups'][cup.name]

        if 'with_roles' not in db:
            db['with_roles'] = True

        if 'teams' not in db:
            db['teams'] = {}

        if 'groups' not in db:
            db['groups'] = {}

        if 'captains' not in db:
            db['captains'] = {}

        if 'matches' not in db:
            db['matches'] = {}

        return db

    def close_cup_db(self, guild, cup_name):
        cup_name = cup_name.upper()
        if cup_name not in self.db[guild]['cups']:
            return False

        del self.db[guild]['cups'][cup_name]
        return True

    def get_cup_db(self, guild, cup_name):
        if guild not in self.db:
            return None, "This guild is either not configured to run any cup" \
                + "or its Database is still loading"

        cup_name = cup_name.upper()

        # If we didn't say which cup we wanted
        if len(cup_name) == 0:
            num_cups = len(self.db[guild]['cups'])
            # If there is only 1 cup running, return it
            if num_cups == 1:
                return next(iter(self.db[guild]['cups'].values())), None
            elif num_cups == 0:
                return None, 'No cup is running!'
            # Else, this is ambiguous
            else:
                return None, 'There is more than one cup running!'

        # Else if the cup exists, return it
        elif cup_name in self.db[guild]['cups']:
            return self.db[guild]['cups'][cup_name], None

        # Else, fail
        else:
            return None, 'No such cup is running'

    def find_cup_db(self, guild, discord=None, captain=None, match=None, hunt=None):
        if guild not in self.db:
            return None, "This guild is not running any cups", None

        if discord: # SLOW!
            for cup_name, db in self.db[guild]['cups'].items():
                for id, captain in db['captains'].items():
                    if captain.discord == discord:
                        return db, None, captain
        elif captain:
            for cup_name, db in self.db[guild]['cups'].items():
                if captain in db['captains']:
                    return db, None, db['captains'][captain]
        elif match:
            for cup_name, db in self.db[guild]['cups'].items():
                if match in db['matches']:
                    return db, None, db['matches'][match]
        elif hunt:
            for cup_name, db in self.db[guild]['cups'].items():
                if 'hunt' in db \
                   and 'channel_id' in db['hunt'] \
                   and hunt.id == db['hunt']['channel_id']:
                    return db, None, hunt

        return None, 'No cup was found that contains this user or match', None

    # Acknowledgement that we are succesfully connected to Discord
    async def on_ready(self):

        for guild in self.client.guilds:
            print('Guild: {}'.format(guild))

            if self.check_guild(guild):
                await self.open_db(guild)
            else:
                print ('WARNING: Guild "{}" not configured!'.format(guild.name))

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
        if member.guild.name not in self.config['guilds']:
            return

        await self.handle_member_join(member)

    async def on_member_update(self, before, after):
        guild = after.guild if hasattr(after, 'guild') and after.guild \
                else before.guild if hasattr(before, 'guild') \
                     else None

        if not guild or guild.name not in self.config['guilds']:
            return

        # Try to find missing captains with rich-presence updates

        # App IDs to track
        app_ids = [
            554573575047348225, # Wf RU
            555316726745792534  # Wf international
        ]

        nickname = None
        for activity in after.activities + before.activities:
            if isinstance(activity, discord.Activity):
                if hasattr(activity, 'application_id') and hasattr(activity, 'large_image_text'):
                    if activity.application_id in app_ids:
                        nickname = activity.large_image_text
                        break

        # This event is indeed a rich-presence update for a tracked application
        if nickname:
            for cup_name, db in self.db[guild]['cups'].items():

                captain = db['captains-by-nick'][nickname] if nickname in db['captains-by-nick'] else None
                # Then only, search for the nicknames
                if captain and not captain.member:
                        print('Update "{}" via rich-presence from {}'.format(nickname, str(after)))
                        await self.update_captain(None, guild, after, nickname, cup_name)


    async def on_user_update(self, before, after):
        guild = after.guild if hasattr(after, 'guild') and after.guild \
                else before.guild if hasattr(before, 'guild') \
                     else None

        if not guild or guild.name not in self.config['guilds']:
            return

        before_discord_id = str(before)
        after_discord_id = str(after)

        # If it's not a discord ID change, ignore
        if before_discord_id == after_discord_id:
            return

        _, _, captain = self.find_cup_db(guild, captain=before.id)

        # A known captain changed ID
        if captain:
            print('"{}" changed discord ID to "{}"'\
                  .format(before_discord_id,
                          after_discord_id))
            captain.discord = after_discord_id
        else:
            # Try to find the captain discord ID in the DB
            _, error, _ = self.find_cup_db(after.guild, discord=after_discord_id)
            if not error:
                # If found, update him
                await self.handle_member_join(after)

    def get_nick_name(self, db, captain):
        nickname = captain.nickname
        if not db['with_roles']:
            try:
                nickname = self.config['nickname']\
                               .format(nick=captain.nickname,
                                       team=captain.team_name)
            except:
                pass

        # Maximum of 32 characters for the nickname
        space_left = 32 - len(nickname)
        if space_left < 0:
            nickname = '{}...'.format(nickname[:space_left - 3])

        return nickname

    def get_role_name(self, role_id, arg=None, arg2=None):
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
            role_name = role_name.format(arg, arg2)

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

    def cache_special_role(self, guild, role_id):
        role_name = self.get_role_name(role_id)
        if not role_name:
            return None

        # Trick to make sure the structures are there
        self.get_special_role(guild, role_id)

        role = discord.utils.get(guild.roles, name=role_name)

        self.cache[guild]['sroles'][role_id] = role
        if not self.cache[guild]['sroles'][role_id]:
            print ('WARNING: Missing role "{}" in {}'.format(role_name, guild.name))

    def get_special_role(self, guild, role_id):
        if not self.cache:
            self.cache = {}
        if guild not in self.cache:
            self.cache[guild] = {}
        if 'sroles' not in self.cache[guild]:
            self.cache[guild]['sroles'] = {}

        if role_id in self.cache[guild]['sroles']:
            return self.cache[guild]['sroles'][role_id]
        return None

    async def add_group(self, message, guild, group_id, cup_name):
        db, error = self.get_cup_db(guild, cup_name)
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
        group_role = await self.get_or_create_role(guild, group_name, color=role_color)
        group = Group(group_id, group_name, group_role)

        db['groups'][group_id] = group

        return True

    async def remove_group(self, message, guild, group_id, cup_name):
        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False

        # Check if group exists
        if group_id not in db['groups']:
            await self.reply(message, 'Group "{}" does not exist'.format(group_id))
            return False

        group = db['groups'][group_id]

        members = list(guild.members)
        # Remove the group from each captain using it
        for uuid, captain in db['captains'].items():
            if captain.group and captain.group.name == group.name:
                captain.group = None

                cpt = None
                for member in members:
                    if member.id == uuid:
                        cpt = member
                        break

                if not cpt:
                    continue

                try:
                    await cpt.remove_roles(group.role)
                    print ('Removed role "{grole}" from "{member}"'\
                           .format(member=str(member),
                                   grole=group.name))
                except:
                    print ('WARNING: Failed to remove role "{grole}" from "{member}"'\
                           .format(member=str(member),
                                   grole=group.name))
                    pass


        del db['groups'][group_id]

        return True

    async def add_captain(self, message, guild, member, team, nick, group_id, cup_name):
        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False

        discord_id = str(member)

        # If captain already exists, remove him
        if member.id in db['captains']:
            await self.remove_captain(message, guild, member, cup_name)

        # Check if destination group exists
        if group_id and group_id not in db['groups']:
            await self.reply(message, 'Group "{}" does not exist'.format(group_id))
            return False

        captain = \
            TeamCaptain(discord_id,
                        team,
                        nick,
                        db['groups'][group_id] if group_id else None,
                        db['cup'])
        captain.key = member.id # TODO Workaround

        # Add new captain to the list
        db['captains'][member.id] = captain
        db['captains-by-nick'][nick] = captain
        db['captains-by-team'][team] = captain

        # Trigger update on member
        await self.handle_member_join(member, db)

        return True

    async def update_captain(self, message, guild, member, nickname, cup_name):
        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False

        discord_id = str(member)

        # Make sure the captain doesn't already exists in DB
        if member.id in db['captains']:
            # If we wanted to update the same captain, nothing to do
            if db['captains'][member.id].nickname == nickname:
                return True

            # Maybe it was the team name?
            if db['captains'][member.id].team_name == nickname:
                return True

            await self.reply(message, '{} is already in the cup {}.\n'
                             'Maybe you wanted to use `!add_captain` instead?'\
                             .format(member.mention,
                                     db['cup'].name))
            return False

        found = False
        captain = db['captains-by-nick'][nickname] if nickname in db['captains-by-nick'] \
                  else db['captains-by-team'][nickname] if nickname in db['captains-by-team'] \
                       else None

        if not captain:
            await self.reply(message, 'Cannot find nickname "{}" in cup {}.'\
                             .format(md_normal(nickname),
                                     db['cup'].name))
            return False

        old_key = captain.key
        # Update captain key in DB
        db['captains'][member.id] = captain
        captain.key = member.id # TODO Workaround
        captain.discord = discord_id
        old_member = captain.member

        # Trigger update on member
        await self.handle_member_join(member, db)

        # Remove previous captain, may he joined or not
        if old_member and old_member != member:
            await self.remove_captain(message, guild, old_member, cup_name)
        else:
            del db['captains'][old_key]

        db['captains-by-nick'][captain.nickname] = captain
        db['captains-by-team'][captain.team_name] = captain

        return True

    async def update_team(self, message, guild, team_name, new_name, cup_name):
        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False

        team = None
        trole_name = None
        for tn, t in db['teams'].items():
            if t.name == team_name:
                team = t
                trole_name = tn
                break

        if not team:
            await self.reply(message, 'Team "{}" not found'.format(team_name))
            return False

        team.name = new_name
        new_role_name = self.get_role_name('team', arg=new_name)

        del db['teams'][trole_name]
        db['teams'][new_role_name] = team

        print('Renamed team "{}" to "{}"'.format(team_name, new_name))

        del db['captains-by-team'][team_name]
        for captain in db['captains'].values():
            if captain.team_name == team_name:
                captain.team_name = new_name
                db['captains-by-team'][new_name] = captain

        if team.role:
            try:
                await team.role.edit(name=new_role_name)
            except:
                print('WARNING: Failed to rename role to "{}"'.format(new_role_name))
                pass
        else:
            for captain in team.captains.values():
                new_nickname = self.get_nick_name(db, captain)

                try:
                    await captain.member.edit(nick=new_nickname)
                    print ('Renamed "{id}" to "{nick}"'\
                           .format(id=str(captain.member), nick=new_nickname))
                except:
                    print ('WARNING: Failed to rename "{id}" to "{nick}"'\
                           .format(id=str(captain.member), nick=new_nickname))
                    pass

        return True

    async def check_captain(self, message, guild, member, cup_name):
        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False

        if member.id not in db['captains']:
            await self.reply(message, '{} is not a known captain in cup {}'\
                             .format(member.mention,
                                     db['cup'].name))
            return False

        return True

    async def remove_captain(self, message, guild, member, cup_name):
        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False

        discord_id = str(member)

        if member.id not in db['captains']:
            await self.reply(message, '{} is not a known captain in cup {}'\
                             .format(member.mention,
                                     db['cup'].name))
            return False

        captain = db['captains'][member.id]

        # remove captain from existing match rooms
        for channel_name, match in db['matches'].items():
            if not captain.member or not match.is_in_match(captain.member):
                continue

            channel = discord.utils.get(guild.channels, name=channel_name)
            if channel:
                try:
                    await channel.set_permissions(member, overwrite=None)

                    print('Deleted permissions for "{discord}" in channel "<{channel}>"'\
                          .format(discord=discord_id,
                                  channel=channel_name))
                except:
                    print('WARNING: Failed to delete permissions for "{discord}" of channel "<{channel}>"'\
                          .format(discord=discord_id,
                                  channel=channel_name))

        role_list = []

        if captain.team and captain.team.role:
            role_list.append(captain.team.role)
        if captain.group and captain.group.role:
            role_list.append(captain.group.role)
        if captain.cup and captain.cup.role:
            role_list.append(captain.cup.role)

        role_names = [ r.name for r in role_list ]

        # Remove team, team captain and group roles from member
        try:
            await member.remove_roles(*role_list)

            print ('Removed roles <{roles}> from "{member}"'\
                   .format(member=discord_id,
                           roles=role_names))
        except:
            print ('WARNING: Failed to remove roles <{roles}> from "{member}"'\
                   .format(member=discord_id,
                           roles=role_names))
            pass

        # Check if the role is now orphan, and delete it

        members = list(guild.members)
        team = captain.team
        team_role = team.role if team else None
        trole_name = team_role.name if team_role else ''

        if team and team.captains and member.id in team.captains:
            del team.captains[member.id]

        if team_role and not any(r == team_role for m in members for r in m.roles):
            try:
                await team_role.delete()
                print ('Deleted role "{role}"'\
                       .format(role=trole_name))
            except:
                print ('WARNING: Failed to delete role "{role}"'\
                       .format(role=trole_name))
                pass

            if trole_name in db['teams']:
                del db['teams'][trole_name]

        # Reset member nickname
        try:
            await member.edit(nick=None)
            print ('Reset nickname for "{member}"'\
                   .format(member=discord_id))
        except:
            print ('WARNING: Failed to reset nickname for "{member}"'\
                   .format(member=discord_id))
            pass

        # Remove captain from DB
        if captain.nickname in db['captains-by-nick']:
            del db['captains-by-nick'][captain.nickname]
        if captain.team_name in db['captains-by-team']:
            del db['captains-by-team'][captain.team_name]
        if member.id in db['captains']:
            del db['captains'][member.id]

        return True

    # Go through the parsed captain list and create all team roles
    async def create_all_teams(self, guild, cup_name):
        db, error = self.get_cup_db(guild, cup_name)
        if error:
            print('ERROR create_all_teams: {}'.format(error))
            return False

        db['teams'] = {}
        for _, captain in db['captains'].items():
            team = await self.create_team(guild, db, captain.team_name)
            captain.team = team

        return True

    # Create team captain role
    async def create_team(self, guild, db, team_name):
        role_name = self.get_role_name('team', arg=team_name)

        if role_name in db['teams']:
            return db['teams'][role_name]

        if db['with_roles']:
            role_color = self.get_role_color('team')
            role = await self.get_or_create_role(guild, role_name, color=role_color)
        else:
            role = None

        team = Team(team_name, role)
        db['teams'][role_name] = team

        return team

    # Whenever a new member joins into the Discord guild
    # 1. Create a user group just for the Team captain
    # 2. Assign the special group to that Team captain
    # 3. Assign the global group to that Team captain
    # 4. Change nickname of Team captain
    async def handle_member_join(self, member, db=None):
        discord_id = str(member)
        guild = member.guild
        captain = None

        # If no db was provided
        if not db:
            # Find cup from discord_id
            db, error, captain = self.find_cup_db(guild, discord=discord_id)

            # User was not found by discord ID
            if error:
                db, error, captain = self.find_cup_db(guild, captain=member.id)

                # User was not found by unique ID
                if error:
                    return
        else:
            if member.id in db['captains']:
                captain = db['captains'][member.id]
            else:
                for _, c in db['captains'].items():
                    if c.discord == discord_id:
                        captain = c

        # Check that the captain is indeed in our list
        if not captain:
            await self.on_member_update(member, member)
            #print('WARNING: New user "{}" not in captain list'\
            #      .format(discord_id))
            return

        print('Team captain "{}" joined guild'\
              .format(discord_id))

        role_list = []

        # Create role
        team = await self.create_team(guild, db, captain.team_name)
        captain.team = team
        team.captains[member.id] = captain
        captain.member = member

        # Update captain key
        del db['captains'][captain.key]
        captain.key = member.id
        db['captains'][captain.key] = captain
        captain.discord = discord_id

        # Assign user roles
        if team and team.role and team.role not in member.roles:
            role_list.append(team.role)
        if captain.group and captain.group.role and captain.group.role not in member.roles:
            role_list.append(captain.group.role)
        if captain.cup and captain.cup.role and captain.cup.role not in member.roles:
            role_list.append(captain.cup.role)

        role_names = [ r.name for r in role_list ]
        if len(role_list) > 0:
            try:
                await member.add_roles(*role_list)
                print('Assigned roles <{role}> to "{id}"'\
                      .format(role=role_names, id=discord_id))
            except:
                print('ERROR: Missing one role out of {roles}'\
                      .format(roles=role_names))

        # Change nickname of team captain
        nickname = self.get_nick_name(db, captain)

        if nickname != member.nick:
            try:
                await member.edit(nick=nickname)
                print ('Renamed "{id}" to "{nick}"'\
                       .format(id=discord_id, nick=nickname))
            except:
                print ('WARNING: Failed to rename "{id}" to "{nick}"'\
                       .format(id=discord_id, nick=nickname))
                pass

        # Add captain from existing match rooms
        for channel_name, match in db['matches'].items():
            if not match.is_in_match(member):
                continue

            channel = discord.utils.get(guild.channels, name=channel_name)
            if channel:
                try:
                    overwrite = discord.PermissionOverwrite()
                    overwrite.read_messages = True
                    overwrite.send_messages = True
                    await channel.set_permissions(member, overwrite=overwrite)

                    print('Edited permissions for channel "<{channel}>"'\
                          .format(channel=channel_name))
                except:
                    print('WARNING: Failed to edited permissions of channel "<{channel}>"'\
                          .format(channel=channel_name))



    # Send a message in a channel
    async def send(self, channel, msg):
        acc = ''
        for l in msg.splitlines():
            if len(acc) + len(l) >= 2000:
                await channel.send(content=acc)
                acc = l
            else:
                acc = '{}\n{}'.format(acc, l)

        return await channel.send(content=acc)


    # Reply to a message in a channel
    async def reply(self, message, reply):
        if not message:
            print('INFO: {}'.format(reply))
            return

        msg = '{} {}'.format(message.author.mention, reply)

        return await self.send(message.channel, msg)

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
    MATCH_BO5 = 5

    REUSE_UNK = 0
    REUSE_YES = 2
    REUSE_NO  = 3

    # Create a match against 2 team roles
    async def matchup_role(self, message, guild, _roleteamA, _roleteamB, cat_id, cup_name, mode=MATCH_BO1, flip_coin=False, reuse=REUSE_UNK, url=None):
        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False, None

        if flip_coin:
            randomized = [ _roleteamA, _roleteamB ]
            random.shuffle(randomized)
            roleteamA, roleteamB = randomized[0], randomized[1]
        else:
            if message.content.find(_roleteamA.mention) > message.content.find(_roleteamB.mention):
                roleteamA, roleteamB = _roleteamB, _roleteamA
            else:
                roleteamA, roleteamB = _roleteamA, _roleteamB

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
            return False, None

        return await self.matchup(message, guild, teamA, teamB, cat_id, cup_name,
                                  mode=mode, flip_coin=flip_coin, reuse=reuse, url=url)

    # Create a match against 2 team captains
    async def matchup_cpt(self, message, guild, _cptteamA, _cptteamB, cat_id, cup_name, mode=MATCH_BO1, flip_coin=False, reuse=REUSE_UNK, url=None):
        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False, None

        if flip_coin:
            randomized = [ _cptteamA, _cptteamB ]
            random.shuffle(randomized)
            cptteamA, cptteamB = randomized[0], randomized[1]
        else:
            if message.content.find(_cptteamA.mention) > message.content.find(_cptteamB.mention):
                cptteamA, cptteamB = _cptteamB, _cptteamA
            else:
                cptteamA, cptteamB = _cptteamA, _cptteamB

        teamA = None
        teamB = None
        for team_name, team in db['teams'].items():
            for id in team.captains.keys():
                if not teamA and id == cptteamA.id:
                    teamA = team
                elif not teamB and id == cptteamB.id:
                    teamB = team

        if not teamA:
            await self.reply(message, '{} is not a captain of a known team'.format(cptteamA.mention))
            return False, None
        if not teamB:
            await self.reply(message, '{} is not a captain of a known team'.format(cptteamB.mention))
            return False, None

        return await self.matchup(message, guild, teamA, teamB, cat_id, cup_name,
                                  mode=mode, flip_coin=flip_coin, reuse=reuse, url=url)


    # Create a match against 2 teams
    async def matchup_team(self, message, guild, _teamA, _teamB, cat_id, cup_name, mode=MATCH_BO1, flip_coin=False, reuse=REUSE_UNK, url=None):
        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False, None

        if flip_coin:
            randomized = [ _teamA, _teamB ]
            random.shuffle(randomized)
            teamA, teamB = randomized[0], randomized[1]
        else:
            if message.content.find(_teamA) > message.content.find(_teamB):
                teamA, teamB = _teamB, _teamA
            else:
                teamA, teamB = _teamA, _teamB

        notfound = None
        roleA_name = self.get_role_name('team', arg=teamA)
        roleB_name = self.get_role_name('team', arg=teamB)

        if roleA_name in db['teams']:
            teamA = db['teams'][roleA_name]
        else:
            notfound = teamA

        if roleB_name in db['teams']:
            teamB = db['teams'][roleB_name]
        else:
            notfound = teamB

        if notfound:
            await self.reply(message, '"{}" is not a known team'.format(notfound))
            return False, None

        return await self.matchup(message, guild, teamA, teamB, cat_id, cup_name,
                                  mode=mode, flip_coin=flip_coin, reuse=reuse, url=url)

    # Get a unique channel name
    async def new_channel_name(self, guild, message, db, base_name, reuse=REUSE_UNK):
        channel_name = base_name
        channel = None
        index = 1
        index_str = ''

        while True:
            channel_name = '{}{}'.format(base_name, index_str)
            channel = discord.utils.get(guild.channels, name=channel_name)

            # Channel already exists, but we do not know if we should reuse it
            if (channel or channel_name in db['matches']) and reuse == self.REUSE_UNK:
                await self.reply(message, 'Room `{}` already exists!\nAdd `reuse` in the command to reuse the same channel or `new` to create a new one.'.format(channel_name))
                return None, None

            if not (channel or channel_name in db['matches']) or reuse == self.REUSE_YES:
                break

            index = index + 1
            index_str = '_r{}'.format(index)

        return channel_name, channel

    # Create a match against 2 team handles
    # 1. Create the text channel
    # 2. Add permissions to read/send to both teams, and the judge
    # 3. Send welcome message
    # 4. Register the match to internal logic for commands like !ban x !pick x
    async def matchup(self, message, guild, teamA, teamB, cat_id, cup_name, mode=MATCH_BO1, flip_coin=False, reuse=REUSE_UNK, url=None):
        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False, None

        # Backward compatibility
        if not hasattr(db['cup'], 'maps_key') and hasattr(db['cup'], 'maps'):
            maps = db['cup']['maps']
        elif db['cup'].maps_key not in self.config['maps']:
            await self.reply(message, 'Unknown map pool key: {}'.format(db['cup'].maps_key))
            return False, None
        else:
            maps = list(self.config['maps'][db['cup'].maps_key])

        # Create the match
        if mode == self.MATCH_BO5:
            match = MatchBo5(teamA, teamB, maps, bot=self)
        elif mode == self.MATCH_BO3:
            match = MatchBo3(teamA, teamB, maps, bot=self)
        elif mode == self.MATCH_BO2:
            match = MatchBo2(teamA, teamB, maps, bot=self)
        else:
            match = Match(teamA, teamB, maps, bot=self)

        if url:
            match.url = url

        # Create the text channel
        teamA_name_safe = sanitize_input(translit_input(teamA.name))
        teamB_name_safe = sanitize_input(translit_input(teamB.name))
        topic = 'Match {} vs {}'.format(teamA.name, teamB.name)

        ref_role = self.get_special_role(guild, 'referee')
        coref_role = self.get_special_role(guild, 'coreferee')

        read_perms = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        no_perms = discord.PermissionOverwrite(read_messages=False)

        channel_name = 'match_{}_vs_{}'.format(teamA_name_safe, teamB_name_safe)  # TODO cup
        channel_name, channel = await self.new_channel_name(guild, message, db, channel_name, reuse=reuse)
        if not channel_name:
            return False, None

        category = None
        if 'categories' in self.config['guilds'][guild.name] \
           and cat_id in self.config['guilds'][guild.name]['categories']:
            cat_name = self.config['guilds'][guild.name]['categories'][cat_id]
            for ch in guild.channels:
                if cat_name.lower() in ch.name.lower():
                    category = ch

        if cat_id and len(cat_id) > 0 and not category:
            await self.reply(message, ':warning: Cannot find category with ID "{}"'.format(cat_id))

        if not channel:
            try:
                overrides = {
                    guild.default_role: no_perms,
                    guild.me: read_perms,
                    ref_role: read_perms
                }

                if coref_role:
                    overrides[coref_role] = read_perms

                for captain in teamA.captains.values():
                    if captain.member:
                        overrides[captain.member] = read_perms
                for captain in teamB.captains.values():
                    if captain.member:
                        overrides[captain.member] = read_perms

                channel = await guild.create_text_channel(
                    channel_name,
                    overwrites=overrides,
                    category=category)

                print('Created channel "<{channel}>"'\
                      .format(channel=channel_name))
            except Exception as e:
                print('WARNING: Failed to create channel "<{channel}>"'\
                      .format(channel=channel_name))
                raise e

            try:
                await channel.edit(topic=topic)

                print('Set topic for channel "<{channel}>" to "{topic}"'\
                      .format(channel=channel_name, topic=topic))
            except:
                print('WARNING: Failed to set topic for channel "<{channel}>"'\
                      .format(channel=channel_name))
        else:
            print('Reusing existing channel "<{channel}>"'\
                  .format(channel=channel_name))

        # Start the match
        db['matches'][channel_name] = match
        handle = Handle(self, channel=channel)
        await match.begin(handle)

        return True, channel_name

    # Matchup for FFA cups - only text chat, no bot
    async def matchup_ffa(self, message, guild, round, match_num, cat_id, cup_name, reuse=REUSE_UNK, url=None, team_names=None, players_csv=None):
        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False, None

        # Search for all players
        players = []
        if players_csv:
            # Fetch the CSV file and parse it
            csv = await self.fetch_text_attachment(players_csv)

            if not csv:
                return False

            csv = io.StringIO(csv)
            player_names = self.parse_players(csv)
            csv.close()

            for player_name in player_names:
                found = False
                for captain in db['captains'].values():
                    if player_name == captain.nickname:
                        players.append(captain)
                        found = True
                        break

                if not found:
                    await self.reply(message, ':warning: Cannot find player "{}"'.format(player_name))

        elif team_names:

            for team_name in team_names:
                found = False
                for captain in db['captains'].values():
                    if captain.team and team_name == captain.team.name:
                        players.append(captain)
                        found = True
                        break

                if not found:
                    await self.reply(message, ':warning: Cannot find player from team "{}"'.format(team_name))

        else:
            await self.reply(message, 'A FFA match with no player? )))')
            return False, None

        match = MatchFFA(round, match_num, players)

        if url:
            match.url = url

        # Create the text channel
        round_safe = sanitize_input(translit_input(round))
        match_safe = sanitize_input(translit_input(match_num))
        topic = 'Round {} - Match {}'.format(round, match_num)

        ref_role = self.get_special_role(guild, 'referee')
        coref_role = self.get_special_role(guild, 'coreferee')

        read_perms = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        no_perms = discord.PermissionOverwrite(read_messages=False)

        channel_name = 'match_{}_{}'.format(round_safe, match_safe)  # TODO cup
        channel_name, channel = await self.new_channel_name(guild, message, db, channel_name, reuse=reuse)
        if not channel_name:
            return False, None

        category = None
        if 'categories' in self.config['guilds'][guild.name] \
           and cat_id in self.config['guilds'][guild.name]['categories']:
            cat_name = self.config['guilds'][guild.name]['categories'][cat_id]
            for ch in guild.channels:
                if cat_name.lower() in ch.name.lower():
                    category = ch

        if cat_id and len(cat_id) > 0 and not category:
            await self.reply(message, ':warning: Cannot find category with ID "{}"'.format(cat_id))

        if not channel:
            try:
                overrides = {
                    guild.default_role: no_perms,
                    guild.me: read_perms,
                    ref_role: read_perms
                }

                if coref_role:
                    overrides[coref_role] = read_perms

                for captain in players:
                    if captain.member:
                        overrides[captain.member] = read_perms

                channel = await guild.create_text_channel(
                    channel_name,
                    overwrites=overrides,
                    category=category)

                print('Created channel "<{channel}>"'\
                      .format(channel=channel_name))
            except:
                print('WARNING: Failed to create channel "<{channel}>"'\
                      .format(channel=channel_name))

            try:
                await channel.edit(topic=topic)

                print('Set topic for channel "<{channel}>" to "{topic}"'\
                      .format(channel=channel_name, topic=topic))
            except:
                print('WARNING: Failed to set topic for channel "<{channel}>"'\
                      .format(channel=channel_name))
        else:
            print('Reusing existing channel "<{channel}>"'\
                  .format(channel=channel_name))

        # Start the match
        db['matches'][channel_name] = match
        handle = Handle(self, channel=channel)
        await match.begin(handle)

        return True, channel_name


    # Returns if a member is a team captain in the given channel
    def is_captain_in_match(self, member, channel, force=False):
        guild = member.guild

        if guild not in self.db:
            return False

        db, error, _ = self.find_cup_db(guild, match=channel.name)
        if error:
            return False

        if channel.name not in db['matches']:
            return False

        if force:
            return True

        return db['matches'][channel.name].is_in_match(member)

    # Ban a map
    async def ban_map(self, message, map_unsafe, force=False):
        guild = message.author.guild
        channel = message.channel
        banned_map_safe = sanitize_input(translit_input(map_unsafe))

        db, error, _ = self.find_cup_db(guild, match=channel.name)
        if error:
            return False

        if channel.name not in db['matches']:
            return False

        handle = Handle(self, message=message)
        return await db['matches'][channel.name].ban_map(handle, banned_map_safe, force)

    # Pick a map
    async def pick_map(self, message, map_unsafe, force=False):
        guild = message.author.guild
        channel = message.channel
        picked_map_safe = sanitize_input(translit_input(map_unsafe))

        db, error, _ = self.find_cup_db(guild, match=channel.name)
        if error:
            return False

        if channel.name not in db['matches']:
            return False

        handle = Handle(self, message=message)
        return await db['matches'][channel.name].pick_map(handle, picked_map_safe, force)

    # Choose sides
    async def choose_side(self, message, side_unsafe, force=False):
        guild = message.author.guild
        channel = message.channel
        side_safe = sanitize_input(translit_input(side_unsafe))

        db, error, _ = self.find_cup_db(guild, match=channel.name)
        if error:
            return False

        if channel.name not in db['matches']:
            return False

        handle = Handle(self, message=message)
        return await db['matches'][channel.name].choose_side(handle, side_safe, force)

    # Undo action
    async def undo_map(self, message):
        guild = message.author.guild
        channel = message.channel

        db, error, _ = self.find_cup_db(guild, match=channel.name)
        if error:
            return False

        if channel.name not in db['matches']:
            return False

        handle = Handle(self, message=message)
        return await db['matches'][channel.name].undo_map(handle)

    # Close a match
    async def close_match(self, message):
        guild = message.author.guild
        channel = message.channel

        db, error, _ = self.find_cup_db(guild, match=channel.name)
        if error:
            return False

        if channel.name not in db['matches']:
            return False

        handle = Handle(self, message=message)
        return await db['matches'][channel.name].close_match(handle)

    # Broadcast information that the match is or will be streamed
    # 1. Notify captains match will be streamed
    # 2. Give permission to streamer to see match room
    # 3. Invite streamer to join it
    async def stream_match(self, message, match_id, streamer):
        guild = message.guild

        member = message.author if not streamer else streamer
        channel = discord.utils.get(guild.channels, name=match_id)
        db, error, _ = self.find_cup_db(guild, match=match_id)
        match = db['matches'][match_id] if db and match_id in db['matches'] else None

        # If we found a channel with the given name
        if not channel or error or not match:
            print(channel, error, match)
            await self.reply(message, 'This match does not exist!')
            return False

        # 1. Notify captains match will be streamed
        await channel.send(
            content=':eye::popcorn: _{} will stream this match!_ :movie_camera::satellite:\n'
            ':arrow_forward: _8.9. The teams whose match will be officially streamed will have '
            '**only** 10 minutes to assemble._\n'\
            .format(md_bold(member.nick if member.nick else member.name)))

        print('Notified "{channel}" the match will be streamed by "{member}"'\
              .format(channel=channel.name,
                      member=str(member)))

        if 'streamer_can_see_match' in self.config['guilds'][guild.name] \
           and self.config['guilds'][guild.name]['streamer_can_see_match']:

            # 2. Give permission to streamer to see match room
            overwrite = discord.PermissionOverwrite()
            overwrite.read_messages = True
            await channel.set_permissions(member, overwrite=overwrite)

            print('Gave permission to "{member}" to see channel "{channel}"'\
                  .format(channel=channel.name,
                  member=str(member)))

            # 3. Invite streamer to join it
            await self.reply(message, 'Roger! Checkout {}'.format(channel.mention))

        # 4. Mark the match as streamed
        await match.stream(self)

        return True

    # Broadcast information that the match will not be streamed anymore
    # 1. Notify captains match will not be streamed
    # 2. Remove permission to streamer to see match room
    async def unstream_match(self, message, match_id, streamer):
        guild = message.guild

        member = message.author if not streamer else streamer
        channel = discord.utils.get(guild.channels, name=match_id)
        db, error, _ = self.find_cup_db(guild, match=match_id)
        match = db['matches'][match_id] if db and match_id in db['matches'] else None

        # If we found a channel with the given name
        if not channel or error or not match:
            await self.reply(message, 'This match does not exist!')
            return False

        # If we found a channel with the given name
        if not channel:
            await self.reply(message, 'This match does not exist!')
            return False

        # 1. Notify captains match will not be streamed anymore
        await channel.send(
            content=':door::walking: _{} will not stream this match anymore_\n'
            ':arrow_forward: You can start the match without him\n'\
            .format(md_bold(member.nick if member.nick else member.name)))

        print('Notified "{channel}" the match will not be streamed anymore by "{member}"'\
              .format(channel=channel.name,
                      member=str(member)))

        if 'streamer_can_see_match' in self.config['guilds'][guild.name] \
           and self.config['guilds'][guild.name]['streamer_can_see_match']:

            # 2. Remove permission from streamer to see match room
            await channel.set_permissions(member, overwrite=None)
            print('Removed permission from "{member}" to see channel "{channel}"'\
                  .format(channel=channel.name,
                  member=str(member)))

        # 4. Unmark the match as being streamed
        await match.unstream()

        return True

    # Remove all teams
    # 1. Delete all existing team roles
    # 2. Find all members with role team captain
    # 3. Remove group role from member
    # 4. Remove team captain and group roles from member
    # 5. Reset member nickname
    async def wipe_teams(self, message, cup_name):
        guild = message.guild
        time_start = time.time()

        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False

        count = len(db['teams'])

        reply_txt = '{l} Deleting {count} teams... (this might take a while)'\
            .format(count=count,
                    l=self.emotes['loading'])

        reply = await self.reply(message, reply_txt)

        # 1. Delete all existing team roles
        for role_name, team in db['teams'].items():
            # If there is no role, skip deletion
            if not team.role:
                continue

            try:
                await team.role.delete()
                print ('Deleted role "{role}"'\
                       .format(role=role_name))
            except:
                print ('WARNING: Failed to delete role "{role}"'\
                       .format(role=role_name))
                pass

        db['teams'].clear()

        # 2. Find all members with role team captain
        members = list(guild.members)
        total = len(members)
        current_i = 0
        for member in members: # TODO go through db instead
            current_i = current_i + 1
            current_time = time.time()
            if current_time > time_start + 10:
                time_start = current_time
                try:
                    await reply.edit(content='{reply}{percent}%'\
                                     .format(reply=reply_txt,
                                             percent=int((current_i/total)*100) ))
                except:
                    pass

            if member.id not in db['captains']:
                continue

            discord_id = str(member)
            captain = db['captains'][member.id]

            print ('Found captain "{member}"'\
                   .format(member=discord_id))

            # 3. Remove group role from member
            role_list = []

            if captain.group and captain.group.role and captain.group.role in member.roles:
                role_list.append(captain.group.role)
            if captain.cup and captain.cup.role and captain.cup.role in member.roles:
                role_list.append(captain.cup.role)

            role_names = [ r.name for r in role_list ]

            # 4. Remove team captain and group roles from member
            if len(role_names) > 0:
                try:
                    await member.remove_roles(*role_list)
                    print ('Removed roles <{roles}> from "{member}"'\
                           .format(member=discord_id,
                                   roles=role_names))
                except:
                    print ('WARNING: Failed to remove roles <{roles}> from "{member}"'\
                           .format(member=discord_id,
                                   roles=role_names))
                    pass

            # 5. Reset member nickname
            if member.nick:
                try:
                    await member.edit(nick=None)
                    print ('Reset nickname for "{member}"'\
                           .format(member=discord_id))
                except:
                    print ('WARNING: Failed to reset nickname for "{member}"'\
                           .format(member=discord_id))

        db['captains'].clear()

        await reply.edit(content='{mention} Deleted {count} teams.'\
                         .format(mention=message.author.mention,
                                 count=count))

        return True

    WIPE_ALL=1
    WIPE_FINISHED=2
    WIPE_ROOMS=3
    WIPE_AUTO=4

    # Remove all match rooms
    # 1. Find all match channels that where created by the bot for this cup
    # 2. Delete channel
    async def wipe_matches(self, message, cup_name, mode=WIPE_ALL):
        guild = message.guild

        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False

        matches = list(db['matches'].items())
        count = len(matches)

        if mode == self.WIPE_ALL:
            db['matches'].clear()

        if mode != self.WIPE_AUTO:
            reply = await self.reply(message,
                                     '{l} Deleting {count} matches... (this might take a while)'\
                                     .format(count=count,
                                             l=self.emotes['loading']))
        else:
            reply = None

        for channel_name, match in matches:
            channel = discord.utils.get(guild.channels, name=channel_name)

            if not channel:
                count = count - 1
                continue

            if mode == self.WIPE_AUTO \
               and not match.auto_done:
                count = count - 1
                continue

            if mode == self.WIPE_FINISHED \
               and not match.is_done():
                count = count - 1
                continue

            try:
                await channel.delete()
                print ('Deleted channel "{channel}"'\
                       .format(channel=channel_name))
            except:
                print ('WARNING: Fail to Delete channel "{channel}"'\
                       .format(channel=channel_name))

        if reply:
            await reply.edit(content='{mention} Deleted {count} matches.'\
                             .format(mention=message.author.mention,
                                     count=count))

        return True

    # Helper function to delete messages one by one
    async def delete_messages_one_by_one(self, l):
        count = len(l)
        for msg in l:
            try:
                await msg.delete()
            except:
                count = count - 1
                print('WARNING: No permission to delete in "{}"'.format(msg.channel.name))
                pass

        return count


    # Remove all messages that are not pinned in a given channel
    async def wipe_messages(self, message, channel):
        guild = message.guild

        messages_to_delete = []
        old_messages_to_delete = []
        t_14days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=14)

        try:
            async for msg in channel.history(limit=1000):
                if not msg.pinned:
                    if msg.created_at < t_14days_ago:
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
                await channel.delete_messages(bulk_messages_to_delete)
                count += len(bulk_messages_to_delete)
            except:
                # If there is any error, try to delete them 1 by 1 instead
                count += await self.delete_messages_one_by_one(bulk_messages_to_delete)

        # Finally delete old messages
        count += await self.delete_messages_one_by_one(old_messages_to_delete)

        await reply.edit(content='{mention} Deleted {count} messages.'\
                         .format(mention=message.author.mention,
                                 count=count))
        print ('Deleted {count} messages in "{channel}"'\
               .format(count=count, channel=channel.name))

        return True

    # Announcement message
    async def announce(self, msg, message):
        guild = message.guild

        handle = Handle(self, message=message)
        await handle.broadcast('announcement', msg)

        return True

    # Export full list of members as CSV
    async def export_members(self, message):
        guild = message.guild

        csv = io.BytesIO()
        csv.write('#discord_id;roles;nickname\n'.encode())

        members = list(guild.members)
        for member in members:
            discord_id = str(member)
            csv.write('"{discord}";"{roles}";"{nickname}"\n'\
                      .format(discord=discord_id,
                              roles=','.join([ r.name for r in member.roles ]),
                              nickname=member.nick)\
                      .encode())

        csv.seek(0)

        member_count = len(members)
        filename = 'members-{}.csv'.format(self.config['guilds'][guild.name]['db'])
        msg = '{mention} Here is the list of all {count} members in this Discord guild'\
            .format(mention=message.author.mention,
                    count=member_count)

        try:
            await message.channel.send(file=discord.File(fp=csv,
                                                         filename=filename),
                                       content=msg)
            print ('Sent member list ({})'.format(member_count))
        except Exception as e:
            print ('ERROR: Failed to send member list ({})'.format(member_count))
            raise e

        csv.close()

        return True

    # Export pick&ban stats for a running cup
    async def export_stats(self, message, cup_name):
        guild = message.guild

        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False

        csv = io.BytesIO()
        csv.write('#action;map;count\n'.encode())

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
            csv.write('ban;{map};{count}\n'\
                      .format(map=bm,
                              count=count).encode())

        for pm, count in picked_maps.items():
            csv.write('pick;{map};{count}\n'\
                      .format(map=pm,
                              count=count).encode())

        for cs, count in sides.items():
            csv.write('side;{side};{count}\n'\
                      .format(side=cs,
                              count=count).encode())

        csv.seek(0)

        filename = 'stats-{}-{}.csv'\
            .format(self.config['guilds'][guild.name]['db'],
                    db['cup'].name)
        msg = '{mention} Here are the pick&ban stats'\
            .format(mention=message.author.mention)

        try:
            await message.channel.send(file=discord.File(fp=csv,
                                                         filename=filename),
                                        content=msg)
            print ('Sent pick&ban stats')
        except Exception as e:
            print ('ERROR: Failed to send pick&ban stats')
            raise e

        csv.close()

        return True

    # Export captain list for a running cup
    async def export_captains(self, message, cup_name):
        guild = message.guild

        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False

        csv = io.BytesIO()
        csv.write('#discord;nickname;team_name;group;did\n'.encode())

        for captain in db['captains'].values():
            discord_id = str(captain.member) if captain.member else captain.discord
            csv.write('{discord};{nick};{team};{group};{did}\n'\
                      .format(discord=discord_id,
                              nick=captain.nickname,
                              team=captain.team.name if captain.team else '',
                              group=captain.group.id if captain.group else '',
                              did=captain.member.id if captain.member else '').encode())

        csv.seek(0)

        filename = 'captains-{}-{}.csv'\
            .format(self.config['guilds'][guild.name]['db'],
                    db['cup'].name)
        msg = '{mention} Here is the captain list'\
            .format(mention=message.author.mention)

        try:
            await message.channel.send(file=discord.File(fp=csv,
                                                         filename=filename),
                                        content=msg)
            print ('Sent captain list')
        except Exception as e:
            print ('ERROR: Failed to send captain list')
            raise e

        csv.close()

        return True

    def discord_validate(self, did):
        return not did.startswith('@') \
            and not did.startswith('#') \
            and re.match('^.*[^ ]#[0-9]+$', did)

    async def fetch_text_attachment(self, attachment):
        if attachment and attachment.url:
            async with aiohttp.ClientSession() as client:
                async with client.get(attachment.url) as response:
                    assert response.status == 200, \
                        'Error code {} when fetching file {}'\
                            .format(response.status, attachment.url)

                    # If the file uses UTF-8 with BOM (wink wink Excel) then this will
                    # skip the header, otherwise, it will treat the document as UTF-8
                    return await response.text(encoding='utf-8-sig')
        else:
            return None

    async def pvpgg_parse_teams(self, link, captains):
        connector = aiohttp.TCPConnector(limit=20)
        client = aiohttp.ClientSession(connector=connector)

        m = re.search('/([0-9]+)/', link)
        cup_id = m.group(1)
        teams_url = 'https://pvp.gg/api/tournament/{cup_id}/players'.format(cup_id=cup_id)

        print('Parsing: {}'.format(teams_url))
        async with client.get(teams_url, params={'pageSize':1}) as response:
            pagen_json = await response.json()

        totalCount = pagen_json['pagen']['totalCount']

        print('Parsing: {}'.format(teams_url))
        async with client.get(teams_url, params={'pageSize':totalCount}) as response:
            teams_json = await response.json()

        captains_lookup = {}
        # TODO thread pool?
        for team in teams_json['players']:
            thash = team['hash']
            tname = team['name']

            team_url = 'https://pvp.gg/api/team/{thash}'.format(thash=thash)
            print('Parsing: {}'.format(team_url))
            async with client.get(team_url) as response:
                team_json = await response.json()

            for player in team_json['players']['main']:
                if player['isCaptain']:
                    captain_ign = player['gameNick']
                    captain_site = player['tnNick']
                    captains_lookup[captain_site] = captain_ign
                    break

        for captain in captains.values():
            if captain.nickname in captains_lookup:
                captain_tn = captain.nickname
                captain_ign = captains_lookup[captain.nickname]
                captain.nickname = captain_ign
                print('Found on PVP.GG that {n} is named {ign} in-game'\
                      .format(n=captain_tn,
                              ign=captain_ign))



    # Check a CSV file before launching a cup
    # 1. Parse the CSV file
    # 2. For all parsed captains:
    #    A. List all captains not in guild
    #    B. List all captains with invalid Discord ID
    #    C. List all captains with no Discord ID.
    async def check_cup(self, message, cup_name, attachment, pvpgg_link=None, checkonly=True):
        cup_name = cup_name.upper()
        guild = message.guild
        time_start = time.time()

        db, db_error = self.get_cup_db(guild, cup_name)

        reply_txt = '{l} Checking members{imported}...'\
            .format(l=self.emotes['loading'],
                    imported=' before import' if not checkonly else '')

        reply = await self.reply(message, reply_txt)

        print('Checking members for cup {cup}'.format(cup=cup_name))

        if attachment:
            # Fetch the CSV file and parse it
            csv = await self.fetch_text_attachment(attachment)

            if not csv:
                return False

            csv = io.StringIO(csv)
            captains, groups = self.parse_teams(csv)
            csv.close()

            # Do we need to parse pvp.gg?
            if pvpgg_link:
                await self.pvpgg_parse_teams(pvpgg_link, captains)

            # Save it for later in a scratchpad
            self.checked_cups[cup_name] = (captains, groups)

        elif cup_name in self.checked_cups:
            captains, groups = self.checked_cups[cup_name]

        elif checkonly and not db_error:
            captains, groups = db['captains'], db['groups']
            # Hot fix
            #for discord_id, captain in captains.items():
            #    if captain.member:
            #        captain.discord = discord_id

        else:
            await self.reply(message, 'I do not remember checking that cup and you did not attach a CSV file to check ¯\_(ツ)_/¯')
            await reply.delete()
            return False

        members = list(guild.members)

        # Check if there are not too many teams per groups and not duplicated entries
        temp_check_dict = {}
        temp_check_groups = {}
        for _, captain in captains.items():
            if captain.group:
                if captain.group not in temp_check_groups:
                    temp_check_groups[captain.group] = 0
                temp_check_groups[captain.group] += 1

            key = captain.nickname + captain.team_name
            if key not in temp_check_dict:
                temp_check_dict[key] = True
            else:
                await self.reply(message, 'Duplicate team: {}. Operation cancelled'\
                                 .format(captain.team_name))
                await reply.delete()
                return False

        for group, count in temp_check_groups.items():
            if count >= 100:
                await self.reply(message, 'Too many teams in group: {}. Operation cancelled'\
                                 .format(group))
                await reply.delete()
                return False

        # Maximum of 250 roles in a given guild
        can_create_roles = (len(captains) + len(guild.roles) < 240)

        # If this is not just a check, update database
        if not checkonly:
            captains, groups = self.checked_cups[cup_name]

            if db_error:
                await self.reply(message, db_error)
                await reply.delete()
                return False

            db['with_roles'] = can_create_roles

            for group_id, group in groups.items():
                role_color = self.get_role_color('group')
                group_role = await self.get_or_create_role(guild, group.name, color=role_color)
                group.role = group_role

            for _, captain in captains.items():
                captain.cup = db['cup']

            captains_by_nick = { c.nickname: c for _, c in captains.items() }
            captains_by_team = { c.team_name: c for _, c in captains.items() }

            if len(captains_by_nick) != len(captains):
                await self.reply(message, 'Duplicate Nickname(s)')
                await reply.delete()
                return False

            if len(captains_by_team) != len(captains):
                await self.reply(message, 'Duplicate Team name(s)')
                await reply.delete()
                return False

            db['captains'] = captains
            db['captains-by-nick'] = captains_by_nick
            db['captains-by-team'] = captains_by_team

            db['groups'] = groups # TODO cup-ref?

            await self.create_all_teams(guild, cup_name)

            # Visit all members of the guild
            for member in members:
                await self.handle_member_join(member, db)

            # If cup was in scratchpad, remove it
            if cup_name in self.checked_cups:
                del self.checked_cups[cup_name]

        # Collect missing captain Discords
        missing_discords = []
        invalid_discords = []
        missing_members = []
        total = len(captains)
        current_i = 0
        for captain in captains.values():
            current_i = current_i + 1
            current_time = time.time()
            if current_time > time_start + 10:
                time_start = current_time
                try:
                    await reply.edit(content='{reply}{percent}%'\
                                     .format(reply=reply_txt,
                                             percent=int((current_i/total)*100) ))
                except:
                    pass

            group_s = ', {}'.format(captain.group.role.name) if captain.group and captain.group.role else ''
            if not captain.discord:
                missing_discords.append('{n} (Team {t}{g})'\
                                        .format(n=md_inline_code(captain.nickname),
                                                t=md_inline_code(captain.team_name),
                                                g=group_s))
            elif not self.discord_validate(captain.discord):
                invalid_discords.append('{n} (Team {t}{g}): {d}'\
                                        .format(n=md_inline_code(captain.nickname),
                                                t=md_inline_code(captain.team_name),
                                                d=md_inline_code(captain.discord),
                                                g=group_s))
            elif not discord.utils.find(lambda m: captain.member and str(m) == str(captain.member) or str(m) == captain.discord, members):
                missing_members.append('{n} (Team {t}{g}): {d}'\
                                       .format(n=md_inline_code(captain.nickname),
                                               t=md_inline_code(captain.team_name),
                                               d=md_inline_code(captain.discord),
                                               g=group_s))

        report = ''

        if len(missing_members) > 0:
            report = '{}\n\n:shrug: **Missing members**\n• {}'.format(report, '\n• '.join(missing_members))
        if len(missing_discords) > 0:
            report = '{}\n\n:mag: **Missing Discord IDs**\n• {}'.format(report, '\n• '.join(missing_discords))
        if len(invalid_discords) > 0:
            report = '{}\n\n:no_entry_sign: **Invalid Discord IDs**\n• {}'.format(report, '\n• '.join(invalid_discords))

        total = len(captains)
        if len(report) > 2000:
            csv = io.BytesIO()
            csv.write(report.encode())
            csv.seek(0)
            filename = 'check-{}-{}.txt'.format(self.config['guilds'][guild.name]['db'], cup_name)

            try:
                await message.channel.send(file=discord.File(fp=csv,
                                                             filename=filename))
            except Exception as e:
                print ('ERROR: Failed to send report')

            csv.close()
            report = ''

        if not db_error:
            title = 'Running cup {}'.format(cup_name)
            body = ('{r}\n\n**{count}/{total} teams are ready**.\n'
            'Use `!update_captain @xxx nickname` to fix the missing/invalid discord ids.').format(
                r=report,
                total=total,
                count=total \
                - len(missing_members) \
                - len(missing_discords) \
                - len(invalid_discords))
        elif checkonly:
            title = 'Checked cup {}'.format(cup_name)
            body = ('{r}\n\n**Ready to import {count}/{total} teams.**\n'
                      'Use `!start_cup {cup}` to start it.').format(
                r=report,
                cup=cup_name,
                total=total,
                count=total \
                - len(missing_members) \
                - len(missing_discords) \
                - len(invalid_discords))
        else:
            title = 'Started cup {}'.format(cup_name)
            body = '{r}\n\n**Imported {count}/{total} teams**.'.format(
                r=report,
                total=total,
                count=total \
                - len(missing_members) \
                - len(missing_discords) \
                - len(invalid_discords))

        #await self.reply(message, report)
        await self.embed(message, title, body)
        await reply.delete()

        return True

    # Start a cup
    async def start_cup(self, message, cup_name, attachment, selected_maps_key=None):
        cup_name = cup_name.upper()
        guild = message.guild

        cup_role_name = self.get_role_name('captain', arg=cup_name)
        role_color = self.get_role_color('captain')
        cup_role = await self.get_or_create_role(guild, cup_role_name, color=role_color)

        if not selected_maps_key:
            selected_maps_key = self.config['guilds'][guild.name]['default_maps'];

        if selected_maps_key not in self.config['maps']:
            await self.reply(message, 'Unknown map pool key: {}'.format(selected_maps_key))
            return False

        cup = Cup(cup_name, cup_role, selected_maps_key)

        self.open_cup_db(guild, cup)

        if not await self.check_cup(message, cup_name, attachment, checkonly=False):
            return False

        return True

    # List active cups
    async def list_cups(self, message):
        guild = message.guild

        error = False
        body = ''

        if len(self.db[guild]['cups']) > 0 or len(self.checked_cups) > 0:
            title = 'Currently running cups'
            for cup_name, cup in self.db[guild]['cups'].items():
                body = '{p}\n• `{name}` - {num}/{total}'\
                    .format(p=body,
                            name=cup_name,
                            num=sum(1 for _, c in cup['captains'].items() if c.member),
                            total=len(cup['captains']))
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
        cup_name = cup_name.upper()
        guild = message.guild

        if cup_name.upper() in self.checked_cups:
            del self.checked_cups[cup_name.upper()]
            return True

        await self.desync_cup(message, cup_name)

        await self.stop_hunt(message, cup_name)

        if not await self.wipe_teams(message, cup_name):
            return False

        if not await self.wipe_matches(message, cup_name):
            return False

        if not self.close_cup_db(guild, cup_name):
            await self.reply(message, 'No such cup')
            return False

        return True

    ## Register a driver to run a given cup
    async def sync_cup(self, message, cup_name, url, cat_id):
        guild = message.guild

        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False

        # If there was already a driver running, stop it
        if 'driver' in db:
            await db['driver'].stop()
            del db['driver']

        # # Reload the driver module from sources
        # # while this is a work-in-progress
        # import sys
        # try:
        #     del sys.modules['esports_driver']
        # except KeyError:
        #     pass

        # from esports_driver import EsportsDriver

        driver = EsportsDriver(self, db, url, cup_name, cat_id)

        db['driver'] = driver

        handle = Handle(self, message=message)
        driver.start(guild, handle)
        # TODO

        return True

    ## Unregister the running driver for the given cup
    async def desync_cup(self, message, cup_name):
        guild = message.guild

        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False

        if 'driver' not in db:
            return False

        await db['driver'].stop()
        del db['driver']

        return True

    def is_carousel_enabled(self):
        return 'carousel' in self.config \
            and self.config['carousel'] \
            and 'visible' in self.config['carousel'] \
            and self.config['carousel']['visible']

    def is_broadcast_enabled(self, guild):
        if guild not in self.db:
            return False

        db = self.db[guild]

        if 'bcast' not in db:
            return False

        return db['bcast']

    BCAST_OFF = 0
    BCAST_ON = 1

    ## Set broadcast mode
    async def broadcast_mode(self, message, mode):
        guild = message.guild

        db = self.db[guild]
        new_mode = True if mode == RoleKeeper.BCAST_ON else False
        db['bcast'] = new_mode

        return True

    ## Reload config
    async def reload_config(self, message):
        guild = message.guild

        self.config = self.get_config(self.config_file)

        return self.config != None

    ## Open captain hunt
    async def start_hunt(self, message, cup_name, channel):
        guild = message.guild

        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False

        # If there was already a hunt running, stop it
        if 'hunt' in db:
            del db['hunt']

        hunt = {
            'channel_id': channel.id
        }

        # TODO Welcome message?

        db['hunt'] = hunt

        return True

    ## Message in captain hunt channel
    async def on_hunt_message(self, message, db):
        guild = message.guild

        if not db:
            # Find cup from channel
            db, error, _ = self.find_cup_db(guild, hunt=message.channel)

            # Hunt was not found
            if error:
                return

        ret = False
        cup_name = db['cup'].name
        information = message.content.strip()

        matching_nickname = db['captains-by-nick'][information] if information in db['captains-by-nick'] else None
        matching_teamname = db['captains-by-team'][information] if information in db['captains-by-team'] else None

        # If no match, gently delete the message after 5 seconds
        if (not matching_nickname) and (not matching_teamname):
            await message.add_reaction('\N{NO ENTRY}')
            await asyncio.sleep(5)
            await message.delete()
            return

        # Look up in team names first
        elif matching_teamname and (not matching_nickname):
            captain = matching_teamname
            ret = await self.update_captain(None, guild, message.author, captain.nickname, cup_name)

        # Then only, search for the nicknames
        elif (not matching_teamname) and matching_nickname:
            captain = matching_nickname
            ret = await self.update_captain(None, guild, message.author, captain.nickname, cup_name)

        # More than one match
        else:
            ref_role = self.get_special_role(guild, 'referee')
            if ref_role:
                await self.send(message.channel,
                                '{ref}: More than one result for {info} in cup {cup}'\
                                .format(ref=ref_role.mention,
                                        info=information,
                                        cup=db['cup'].name))
            ret = False


        await message.add_reaction('\N{WHITE HEAVY CHECK MARK}' if ret else '\N{NO ENTRY}')

    ## Close captain hunt
    async def stop_hunt(self, message, cup_name):
        guild = message.guild

        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False

        if 'hunt' not in db:
            return False

        # TODO Goodbye message?

        del db['hunt']

        return True


    ## Update captain info
    ## - Update group assignation
    ## - Update captain nickname
    ## - Update captain discord ID
    async def update_cup(self, message, cup_name, attachment):
        guild = message.guild

        db, error = self.get_cup_db(guild, cup_name)
        if error:
            await self.reply(message, error)
            return False

        reply = await self.reply(message,
                                 '{l} Updating members...'\
                                 .format(l=self.emotes['loading']))

        print('Update members for cup {cup}'.format(cup=cup_name))

        if not attachment:
            return False

        # Fetch the CSV file and parse it
        csv = await self.fetch_text_attachment(attachment)

        if not csv:
            return False

        csv = io.StringIO(csv)
        captains, groups = self.parse_teams(csv, cup=db['cup'], groups=db['groups'])
        csv.close()

        for group_id, group in groups.items():
            if group.role:
                continue
            role_color = self.get_role_color('group')
            group_role = await self.get_or_create_role(guild, group.name, color=role_color)
            group.role = group_role

        remove_discord_list = []
        update_discord_list = []
        update_group_list = []
        count = 0
        for new_key, new_captain in captains.items():
            old_captain = None
            old_key = None

            for old_key, cpt in db['captains'].items():
                # No discord id change
                if len(new_captain.discord) > 0 and cpt.discord == new_captain.discord:
                    old_captain = cpt
                    break
                # Try to find him via nickname
                elif cpt.nickname == new_captain.nickname:
                    old_captain = cpt
                    break
                # then by team name (TODO can be several captains per team)
                elif cpt.team_name == new_captain.team_name:
                    old_captain = cpt
                    break

            # We still didn't find him, means he is new
            if not old_captain:
                # Add him to DB
                db['captains'][new_key] = new_captain
                team = await self.create_team(guild, db, new_captain.team_name)
                new_captain.team = team
                update_discord_list.append(new_captain)
                print('Add captain "{nick}" for team "{team}"'\
                      .format(nick=new_captain.nickname,
                              team=new_captain.team_name))
            elif old_captain.nickname != new_captain.nickname:
                old_captain.nickname = new_captain.nickname
                update_discord_list.append(old_captain)
                print('Rename captain "{nick}" of team "{team}"'\
                      .format(nick=new_captain.nickname,
                              team=new_captain.team_name))


            # We found him (either by nickname or team name)
            if old_captain:
                # ... and his discord id is different
                if new_captain.discord != old_captain.discord:

                    # Update key in DB
                    db['captains'][new_key] = old_captain

                    # If the captain is already in the guild
                    if old_captain.member:
                        # Remove him later
                        remove_discord_list.append(old_captain.member)
                    else:
                        # else, simply remove him from db
                        del db['captains'][old_key]

                    # Update the discord ID
                    old_captain.key = new_key
                    old_captain.discord = new_captain.discord
                    old_captain.member = None
                    update_discord_list.append(old_captain)

                    print ('Updated discord id for "{cpt}" to "{id}"'\
                           .format(cpt=old_captain.nickname,
                                   id=old_captain.discord))

                # ... or his group
                if old_captain.group != new_captain.group:
                    old_group = old_captain.group
                    old_captain.group = new_captain.group
                    update_group_list.append(old_captain)
                    print ('Changed group from {A} to {B} for "{cpt}"'\
                           .format(A=old_group.id if old_group else None,
                                   B=old_captain.group.id if old_captain.group else None,
                                   cpt=old_captain.nickname))

                    # If the captain is already in the guild
                    if old_captain.member:
                        # Change group role for member
                        try:
                            await old_captain.member.remove_roles(old_group.role)
                            await old_captain.member.add_roles(old_captain.group.role)

                            print ('Changed role <{roleA}> to <{roleB}> from "{member}"'\
                                   .format(member=old_captain.discord,
                                           roleA=old_group.role,
                                           roleB=old_captain.group.role))
                        except:
                            print ('WARNING: Failed to change role from "{member}"'\
                                   .format(member=old_captain.discord))


        captain_set = set()
        captain_set.update(remove_discord_list)
        captain_set.update(update_discord_list)
        captain_set.update(update_group_list)
        count = len(captain_set)

        members = list(guild.members)
        for captain in update_discord_list:
            member = discord.utils.find(lambda m: str(m) == captain.discord, members)
            if member:
                await self.handle_member_join(member, db)

        for member in remove_discord_list:
            print('Remove captain {}'.format(str(member)))
            await self.remove_captain(message, guild, member, cup_name)

        # Rebuild indexes
        db['captains-by-nick'] = { c.nickname: c for c in db['captains'].values() }
        db['captains-by-team'] = { c.team_name: c for c in db['captains'].values() }

        await reply.edit(content='{mention} Updated {count} captains.'\
                        .format(mention=message.author.mention,
                                count=count))
        print ('Updated {count} captains'\
               .format(count=count))

        return True
