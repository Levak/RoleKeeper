#! /usr/bin/env python3

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
import sys

from rolekeeper import RoleKeeper

import json

def get_config(path):
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

client = discord.Client()




##############################################################################
# The following is a hack to backport category support in discord.py 'async' #
##############################################################################

import types

def http_create_channel(self, guild_id, name, channel_type, parent_id=None, permission_overwrites=None):
    payload = {
        'name': name,
        'type': channel_type
    }

    if permission_overwrites is not None:
        payload['permission_overwrites'] = permission_overwrites

    if parent_id is not None:
        payload['parent_id'] = parent_id

    return self.request(discord.http.Route('POST', '/guilds/{guild_id}/channels', guild_id=guild_id), json=payload)

client.http.create_channel = types.MethodType(http_create_channel, client.http)


@asyncio.coroutine
def create_channel(self, server, name, *overwrites, category=None, type=None):
    if type is None:
        type = discord.ChannelType.text

    perms = []
    for overwrite in overwrites:
        target = overwrite[0]
        perm = overwrite[1]
        if not isinstance(perm, discord.PermissionOverwrite):
            raise discord.InvalidArgument('Expected PermissionOverwrite received {0.__name__}'.format(type(perm)))

        allow, deny = perm.pair()
        payload = {
            'allow': allow.value,
            'deny': deny.value,
            'id': target.id
        }

        if isinstance(target, discord.User):
            payload['type'] = 'member'
        elif isinstance(target, discord.Role):
            payload['type'] = 'role'
        else:
            raise discord.InvalidArgument('Expected Role, User, or Member target, received {0.__name__}'.format(type(target)))

        perms.append(payload)

    parent_id = category.id if category else None
    data = yield from self.http.create_channel(server.id, name, str(type), parent_id=parent_id, permission_overwrites=perms)
    channel = discord.Channel(server=server, **data)
    return channel

client.create_channel = types.MethodType(create_channel, client)

############################################################################
#                                End of hack                               #
############################################################################




@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')
    await rk.on_ready()


@client.event
async def on_member_join(member):
    await rk.on_member_join(member)

@client.event
async def on_message(message):
    # If we are the one sending a message, skip
    if message.author == rk.client.user:
        return

    # If message is a DM
    if type(message.author) is discord.User:
        await rk.on_dm(message)
        return

    is_admin = message.author.server_permissions.manage_roles
    is_ref = discord.utils.get(message.author.roles, name=rk.config['roles']['referee']['name']) or is_admin
    is_captain_in_match = rk.is_captain_in_match(message.author, message.channel) or is_admin or is_ref
    is_streamer = discord.utils.get(message.author.roles, name=rk.config['roles']['streamer']['name']) or is_ref

    if len(message.content) <= 0:
        return

    command = message.content.split()[0]
    args = message.content.replace(command, '', 1).strip()

    reuse_mode = RoleKeeper.REUSE_UNK
    if ' reuse' in args:
        reuse_mode = RoleKeeper.REUSE_YES
        args = args.replace(' reuse', '')
    elif ' new' in args:
        reuse_mode = RoleKeeper.REUSE_NO
        args = args.replace(' new', '')

    parts = args.split()

    ret = False
    exception = None

    try:

        if False:
            pass

    # ADMIN COMMANDS
    #----------------

        elif command == '!wipe_matches' and is_admin:
            ret = await rk.wipe_matches(message,
                                        parts[0] if len(parts) > 0 else '')

        elif command == '!wipe_messages' and is_admin:
            if len(message.channel_mentions) < 1:
                await rk.reply(message,
                               'Not enough arguments:\n```!wipe_messages #channel```')
            else:
                ret = await rk.wipe_messages(message, message.channel_mentions[0])

        elif command == '!announce' and is_admin:
            ret = await rk.announce(args, message)

        elif command == '!members' and is_admin:
            ret = await rk.export_members(message)

        elif command == '!stats' and is_admin:
            ret = await rk.export_stats(message,
                                        parts[0] if len(parts) > 0 else '')

        elif command == '!start_cup' and is_admin:
            if len(parts) > 0:
                ret = await rk.start_cup(message,
                                         parts[0],
                                         message.attachments[0] if len(message.attachments) > 0 else None,
                                         selected_maps_key=parts[1] if len(parts) > 1 else None)
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!start_cup name [maps_key] [// TEAMS.csv]```')

        elif command == '!check_cup' and is_admin:
            if len(parts) > 0:
                ret = await rk.check_cup(message,
                                         parts[0],
                                         message.attachments[0] if len(message.attachments) > 0 else None)
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!check_cup name [// TEAMS.csv]```')

        elif command == '!stop_cup' and is_admin:
            if len(parts) > 0:
                ret = await rk.stop_cup(message,
                                        parts[0])
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!stop_cup name```')

        elif command == '!cups' and is_admin:
            ret = await rk.list_cups(message)

        # REF COMMANDS
        #--------------

        elif command == '!add_group' and is_ref:
            if len(parts) >= 1:
                ret = await rk.add_group(message,
                                         message.author.server,
                                         parts[0],
                                         parts[1] if len(parts) >= 2 else '')
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!add_group group [cup]```')

        elif command == '!remove_group' and is_ref:
            if len(parts) >= 1:
                ret = await rk.remove_group(message,
                                            message.author.server,
                                            parts[0],
                                            parts[1] if len(parts) >= 2 else '')
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!remove_group group [cup]```')

        elif command == '!add_captain' and is_ref:
            if len(message.mentions) == 1 and len(parts) >= 4:
                ret = await rk.add_captain(message,
                                           message.author.server,
                                           message.mentions[0], # TODO check it's the first argument?
                                           parts[1],
                                           parts[2],
                                           parts[3] if parts[3] != '-' else None,
                                           parts[4] if len(parts) > 4 else '')
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!add_captain @xxx team nick group|- [cup]```')

        elif command == '!remove_captain' and is_ref:
            if len(message.mentions) == 1:
                ret = await rk.remove_captain(message,
                                              message.author.server,
                                              message.mentions[0],
                                              parts[1] if len(parts) > 1 else '')
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!remove_captain @xxx [cup]```')

        elif command == '!bo1' and is_ref:
            if len(message.role_mentions) == 2:
                ret = await rk.matchup(message,
                                       message.author.server,
                                       message.role_mentions[0],
                                       message.role_mentions[1],
                                       parts[2][1:] \
                                        if len(parts) > 2 and parts[2].startswith('>')\
                                        else None,
                                       parts[3] \
                                        if len(parts) > 3 \
                                        else parts[2] \
                                         if len(parts) > 2 and not parts[2].startswith('>') \
                                         else '',
                                       mode=RoleKeeper.MATCH_BO1,
                                       reuse=reuse_mode)
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!bo1 @xxx @yyy [>category] [cup] [new/reuse]```')

        elif command == '!bo2' and is_ref:
            if len(message.role_mentions) == 2:
                ret = await rk.matchup(message,
                                       message.author.server,
                                       message.role_mentions[0],
                                       message.role_mentions[1],
                                       parts[2][1:] \
                                        if len(parts) > 2 and parts[2].startswith('>')\
                                        else None,
                                       parts[3] \
                                        if len(parts) > 3 \
                                        else parts[2] \
                                         if len(parts) > 2 and not parts[2].startswith('>') \
                                         else '',
                                       mode=RoleKeeper.MATCH_BO2,
                                       reuse=reuse_mode)
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!bo2 @xxx @yyy [>category] [cup] [new/reuse]```')

        elif command == '!bo3' and is_ref:
            if len(message.role_mentions) == 2:
                ret = await rk.matchup(message,
                                       message.author.server,
                                       message.role_mentions[0],
                                       message.role_mentions[1],
                                       parts[2][1:] \
                                        if len(parts) > 2 and parts[2].startswith('>')\
                                        else None,
                                       parts[3] \
                                        if len(parts) > 3 \
                                        else parts[2] \
                                         if len(parts) > 2 and not parts[2].startswith('>') \
                                         else '',
                                       mode=RoleKeeper.MATCH_BO3,
                                       reuse=reuse_mode)
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!bo3 @xxx @yyy [>category] [cup] [new/reuse]```')


        elif command == '!undo' and is_ref:
            ret = await rk.undo_map(message)

        elif command == '!say' and is_ref:
            if len(parts) > 1 or (len(parts) == 1 and len(message.attachments) > 0):
                channel_id = parts[0]
                if channel_id.startswith('<'):
                    channel_id = channel_id[2:-1]
                    channel = discord.utils.get(message.author.server.channels, id=channel_id)
                else:
                    channel = discord.utils.get(message.author.server.channels, name=channel_id)

                if channel:
                    msg = args.replace(parts[0], '', 1)
                    try:
                        if len(message.attachments) > 0:
                            for attachment in message.attachments:
                                attach = rk.fetch_text_attachment(attachment)
                                if attach:
                                    await rk.send(channel, attach)
                        else:
                            await rk.send(channel, msg)

                        ret = True
                    except:
                        await rk.reply(message,
                                       'I do not see channel `#{}`'.format(channel.name))
                else:
                    await rk.reply(message,
                                   'No channel named `#{}`'.format(channel_id))
            else:
                await rk.reply(message,
                               'Not enough arguments:\n```!say #channel message...```')

        # CAPTAIN COMMANDS
        #-------------------


        elif command == '!ban' and is_captain_in_match:
            ret = await rk.ban_map(message,
                                   parts[0] if len(parts) > 0 else '',
                                   force=is_ref)

        elif command == '!pick' and is_captain_in_match:
            ret = await rk.pick_map(message,
                                    parts[0] if len(parts) > 0 else '',
                                    force=is_ref)

        elif command == '!side'  and is_captain_in_match:
            ret = await rk.choose_side(message,
                                       parts[0] if len(parts) > 0 else '',
                                       force=is_ref)

        # STREAMER COMMANDS
        #-------------------

        elif command == '!stream' and is_streamer:
            if len(parts) > 0:
                ret = await rk.stream_match(message,
                                            parts[0],
                                            message.mentions[0] if len(message.mentions) > 0 else None)
            else:
                await rk.reply(message,
                               'Not enough arguments:\n```!stream channel_id [@streamer]```')


        # Unknown command, probably not for us:
        #-------------------------------------
        else:
            return

    except Exception as e:
        ret = False
        exception = e

    try:
        await rk.client.add_reaction(message,
                                     '\N{WHITE HEAVY CHECK MARK}' if ret else '\N{NO ENTRY}')
    except:
        pass

    if exception:
        raise exception

if __name__ == '__main__':

    config = None

    if len(sys.argv) > 1:
        config = get_config(sys.argv[1])
    else:
        print('Using default configuration file path: `config.json`')
        config = get_config('config.json')

    if config:
        rk = RoleKeeper(client, config)
        client.run(config['app_bot_token'])
