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

    if payload['type'] == 'text':
        payload['type'] = 0

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
async def on_member_update(before, after):
    await rk.on_member_update(before, after)

@client.event
async def on_message(message):
    # If we are the one sending a message, skip
    if message.author == rk.client.user:
        return

    # If message is a DM
    if type(message.author) is discord.User:
        await rk.on_dm(message)
        return

    # If message came from a non-configured server, skip
    if not rk.check_server(message.server):
        return

    is_admin = message.author.server_permissions.manage_roles
    is_ref = discord.utils.get(message.author.roles, name=rk.config['roles']['referee']['name']) or is_admin
    is_captain_in_match = rk.is_captain_in_match(message.author, message.channel, is_admin or is_ref)
    is_streamer = discord.utils.get(message.author.roles, name=rk.config['roles']['streamer']['name']) or is_ref

    if len(message.content) <= 0:
        return

    # Bypass command line when message is in a captain hunt channel
    _db, _error, _ = rk.find_cup_db(message.author.server, hunt=message.channel)
    if not _error and not is_ref:
        await rk.on_hunt_message(message, _db)
        return

    command = message.content.split()[0]
    args = message.content.replace(command, '', 1)
    command = command.lower()

    # Special shortcut for pick&ban
    if is_captain_in_match and len(command) > 1:
        if command.startswith('-'):
            args = command[1:] + ' ' + args
            command = '!ban'
        elif command.startswith('+'):
            args = command[1:] + ' ' + args
            command = '!pick'
        elif command.startswith('='):
            args = command[1:] + ' ' + args
            command = '!side'

    args = args.strip()

    reuse_mode = RoleKeeper.REUSE_UNK
    if args.endswith(' reuse'):
        reuse_mode = RoleKeeper.REUSE_YES
        args = args[:-6]
    elif args.endswith(' new'):
        reuse_mode = RoleKeeper.REUSE_NO
        args = args[:-4]

    parts = args.split()

    ret = False
    exception = None

    try:

        if False:
            pass

    # ADMIN COMMANDS
    #----------------

        elif command == '!wipe_matches' and is_admin:
            wipe_mode = None
            if 'finished' in args:
                wipe_mode = RoleKeeper.WIPE_FINISHED
                args = args.replace('finished', '', 1)
            elif 'rooms' in args:
                wipe_mode = RoleKeeper.WIPE_ROOMS
                args = args.replace('rooms', '', 1)
            elif 'all' in args:
                wipe_mode = RoleKeeper.WIPE_ALL
                args = args.replace('all', '', 1)
            else:
                await rk.reply(message,
                               'Not enough arguments:\n```!wipe_matches finished|rooms|all [cup]```')

            if wipe_mode:
                parts = args.split()
                ret = await rk.wipe_matches(message,
                                            parts[0] if len(parts) > 0 else '',
                                            mode=wipe_mode)

        elif command == '!wipe_messages' and is_admin:
            if len(message.channel_mentions) < 1:
                await rk.reply(message,
                               'Not enough arguments:\n```!wipe_messages #channel```')
            else:
                ret = await rk.wipe_messages(message, message.channel_mentions[0])

        elif command == '!announce' and is_admin:
            ret = await rk.announce(args, message)

        elif command == '!reconfig' and is_admin:
            ret = await rk.reload_config(message)

        elif command == '!broadcast' and is_admin:
            if len(parts) > 0:
                ret = await rk.broadcast_mode(message,
                                              RoleKeeper.BCAST_ON \
                                              if parts[0] == 'on' \
                                              else RoleKeeper.BCAST_OFF)
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!broadcast on/off```')

        elif command == '!members' and is_admin:
            ret = await rk.export_members(message)

        elif command == '!captains' and is_admin:
            ret = await rk.export_captains(message,
                                           parts[0] if len(parts) > 0 else '')

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

        elif command == '!update_cup' and is_admin:
            if len(parts) > 0 and len(message.attachments) > 0:
                ret = await rk.update_cup(message,
                                         parts[0],
                                         message.attachments[0])
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!update_cup name // TEAMS.csv```')

        elif command == '!stop_cup' and is_admin:
            if len(parts) > 0:
                ret = await rk.stop_cup(message,
                                        parts[0])
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!stop_cup name```')

        elif command == '!cups' and is_admin:
            ret = await rk.list_cups(message)

        elif command == '!start_hunt' and is_admin:
            channel = message.channel_mentions[0] if len(message.channel_mentions) > 0 else message.channel
            if len(parts) > 0:
                ret = await rk.start_hunt(message,
                                          parts[0],
                                          channel)
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!start_hunt cup [#channel]```')

        elif command == '!stop_hunt' and is_admin:
            if len(parts) > 0:
                ret = await rk.stop_hunt(message,
                                         parts[0])
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!stop_hunt cup```')

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

        elif command == '!update_captain' and is_ref:
            if len(message.mentions) == 1 and len(parts) > 1:
                ret = await rk.update_captain(message,
                                              message.author.server,
                                              message.mentions[0],
                                              parts[1],
                                              parts[2] if len(parts) > 2 else '')
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!update_captain @xxx nickname [cup]```')

        elif command == '!update_team' and is_ref:
            if len(parts) >= 2:
                ret = await rk.update_team(message,
                                           message.author.server,
                                           parts[0],
                                           parts[1],
                                           parts[2] if len(parts) > 2 else '')
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!update_team team_name new_name [cup]```')

        elif command == '!remove_captain' and is_ref:
            if len(message.mentions) == 1:
                ret = await rk.remove_captain(message,
                                              message.author.server,
                                              message.mentions[0],
                                              parts[1] if len(parts) > 1 else '')
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!remove_captain @xxx [cup]```')

        elif command == '!check_captain' and is_ref:
            if len(message.mentions) == 1:
                ret = await rk.check_captain(message,
                                              message.author.server,
                                              message.mentions[0],
                                              parts[1] if len(parts) > 1 else '')
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!check_captain @xxx [cup]```')

        elif is_ref and (command == '!bo1' or command == '!bo2' or command == '!bo3' or command == '!bo5'):
            mode = RoleKeeper.MATCH_BO1
            if command == '!bo2':
                mode = RoleKeeper.MATCH_BO2
            elif command == '!bo3':
                mode = RoleKeeper.MATCH_BO3
            elif command == '!bo5':
                mode = RoleKeeper.MATCH_BO5

            cat_id = parts[2][1:] \
                     if len(parts) > 2 and parts[2].startswith('>')\
                        else None
            cup_name = parts[3] \
                       if len(parts) > 3 \
                          else parts[2] \
                               if len(parts) > 2 and not parts[2].startswith('>') \
                                  else ''

            if len(message.role_mentions) == 2:
                ret, _ = await rk.matchup_role(message,
                                               message.author.server,
                                               message.role_mentions[0],
                                               message.role_mentions[1],
                                               cat_id,
                                               cup_name,
                                               mode=mode,
                                               reuse=reuse_mode)
            elif len(message.mentions) == 2:
                ret, _ = await rk.matchup_cpt (message,
                                               message.author.server,
                                               message.mentions[0],
                                               message.mentions[1],
                                               cat_id,
                                               cup_name,
                                               mode=mode,
                                               reuse=reuse_mode)
            elif len(parts) >= 2:
                ret, _ = await rk.matchup_team(message,
                                               message.author.server,
                                               parts[0],
                                               parts[1],
                                               cat_id,
                                               cup_name,
                                               mode=mode,
                                               reuse=reuse_mode)
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n'
                               '```{command} @xxx @yyy [>category] [cup] [new/reuse]```'\
                               .format(command=command))



        elif is_ref and command == '!ffa':
            cat_id = parts[-1][1:] \
                     if len(parts) > 2 and parts[-1].startswith('>') \
                        else parts[-2][1:] \
                             if len(parts) > 3 and parts[-2].startswith('>') \
                                else None

            cup_name = parts[-1][1:] \
                       if len(parts) > 3 and parts[-1].startswith('?') \
                          else parts[-2][1:] \
                               if len(parts) > 2 and parts[-2].startswith('?') \
                                  else ''

            round=parts[0] if len(parts) > 0 else None
            match=parts[1] if len(parts) > 1 else None

            if round and match and len(message.mentions) > 0:
                ret, _ = await rk.matchup_ffa (message,
                                               message.author.server,
                                               round,
                                               match,
                                               cat_id,
                                               cup_name,
                                               players=message.mentions,
                                               reuse=reuse_mode)
            elif round and match and len(message.attachments) > 0:
                ret, _ = await rk.matchup_ffa (message,
                                               message.author.server,
                                               round,
                                               match,
                                               cat_id,
                                               cup_name,
                                               players_csv=message.attachments[0],
                                               reuse=reuse_mode)
            elif round and match and len(parts) > 2:
                end = -2 if len(cup_name) > 0 and cat_id else -1 if len(cup_name) > 0 or cat_id else 0
                names = [ p.replace(',', '') for p in (parts[2:end] if end < 0 else parts[2:]) ]
                ret, _ = await rk.matchup_ffa (message,
                                               message.author.server,
                                               round,
                                               match,
                                               cat_id,
                                               cup_name,
                                               team_names=names,
                                               reuse=reuse_mode)
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n'
                               '```!ffa round match [@member1 @member2 ...|player1, player2, ...] [>category] [?cup] [new/reuse] [// Players.csv]```')



        elif command == '!undo' and is_ref:
            ret = await rk.undo_map(message)

        elif command == '!close' and is_ref:
            ret = await rk.close_match(message)

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
                                attach = await rk.fetch_text_attachment(attachment)
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

        elif command == '!sync_cup' and is_ref:
            if len(parts) >= 2:
                ret = await rk.sync_cup(message,
                                        parts[0],
                                        parts[1],
                                        parts[2][1:] \
                                        if len(parts) > 2 and parts[2].startswith('>')\
                                        else None)
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!sync_cup cup bracket_url [>category]```')

        elif command == '!desync_cup' and is_ref:
            if len(parts) >= 1:
                ret = await rk.desync_cup(message,
                                          parts[0])
            else:
                await rk.reply(message,
                               'Too much or not enough arguments:\n```!desync_cup cup```')

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

        elif command == '!side' and is_captain_in_match:
            ret = await rk.choose_side(message,
                                       parts[0] if len(parts) > 0 else '',
                                       force=is_ref)

        elif command == '!attack' and is_captain_in_match:
            ret = await rk.choose_side(message,
                                       'attack',
                                       force=is_ref)

        elif command == '!defense' and is_captain_in_match:
            ret = await rk.choose_side(message,
                                       'defense',
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

        elif command == '!unstream' and is_streamer:
            if len(parts) > 0:
                ret = await rk.unstream_match(message,
                                              parts[0],
                                              message.mentions[0] if len(message.mentions) > 0 else None)
            else:
                await rk.reply(message,
                               'Not enough arguments:\n```!unstream channel_id [@streamer]```')


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

    config_file = 'config.json'

    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    else:
        print('Using default configuration file path: `{}`'.format(config_file))

    rk = RoleKeeper(client, config_file)
    if rk.config:
        client.run(rk.config['app_bot_token'])
