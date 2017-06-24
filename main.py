#! /usr/bin/env python3
import discord
import asyncio

from rolekeeper import RoleKeeper

import json

def get_config(path):
    with open(path, 'r') as f:
        config = json.load(f)
    return config

client = discord.Client()

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
    is_admin = message.author.server_permissions.manage_roles
    is_ref = discord.utils.get(message.author.roles, name=rk.config['roles']['referee']) or is_admin
    is_captain_in_match = rk.is_captain_in_match(message.author, message.channel) or is_admin or is_ref
    is_streamer = discord.utils.get(message.author.roles, name=rk.config['roles']['streamer']) or is_admin

    command = message.content.split()[0]
    args = message.content.replace(command, '', 1).strip()

    if command == '!refresh' and is_admin:
        await rk.refresh(message.author.server)
    elif command == '!create_teams' and is_admin:
        await rk.create_all_roles(message.author.server)

    elif command == '!bo1' and is_admin:
        if len(message.role_mentions) == 2:
            await rk.matchup(message.author.server,
                             message.role_mentions[0],
                             message.role_mentions[1],
                             is_bo3=False)
        else:
            await rk.reply(message,
                           "Too much or not enough arguments:\n```!bo1 @xxx @yyy```")

    elif command == '!bo3' and is_ref:
        if len(message.role_mentions) == 2:
            await rk.matchup(message.author.server,
                             message.role_mentions[0],
                             message.role_mentions[1],
                             is_bo3=True)
        else:
            await rk.reply(message,
                           "Too much or not enough arguments:\n```!bo3 @xxx @yyy```")

    elif command == '!pick' and is_captain_in_match:
        await rk.pick_map(message.author, message.channel, args.split()[0], force=is_ref)
    elif command == '!ban' and is_captain_in_match:
        await rk.ban_map(message.author, message.channel, args.split()[0], force=is_ref)
    elif command == '!side' and is_captain_in_match:
        await rk.choose_side(message.author, message.channel, args.split()[0], force=is_ref)

    elif command == '!say' and is_ref:
        parts = args.split()
        channel_id = parts[0][2:-1]
        msg = args.replace(parts[0], '', 1)
        channel = discord.utils.get(message.author.server.channels, id=channel_id)
        await rk.client.send_message(channel, msg)

    elif command == '!stream' and is_streamer:
        await rk.stream_match(message, args.split()[0])

config = get_config('config.json')
rk = RoleKeeper(client, config)
client.run(config['app_bot_token'])
