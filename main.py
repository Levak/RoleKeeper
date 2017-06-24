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
    is_mod = message.author.server_permissions.manage_roles
    is_captain_in_match = rk.is_captain_in_match(message.author, message.channel)

    if message.content.startswith('!refresh') and is_mod:
        await rk.refresh(message.author.server)
    elif message.content.startswith('!create_teams') and is_mod:
        await rk.create_all_roles(message.author.server)

    elif message.content.startswith('!bo1 ') and is_mod:
        if len(message.role_mentions) == 2:
            await rk.matchup(message.author.server,
                             message.role_mentions[0],
                             message.role_mentions[1],
                             is_bo3=False)
        else:
            await rk.reply(message,
                           "Too much or not enough arguments:\n```!bo1 @xxx @yyy```")

    elif message.content.startswith('!bo3 ') and is_mod:
        if len(message.role_mentions) == 2:
            await rk.matchup(message.author.server,
                             message.role_mentions[0],
                             message.role_mentions[1],
                             is_bo3=True)
        else:
            await rk.reply(message,
                           "Too much or not enough arguments:\n```!bo3 @xxx @yyy```")

    elif message.content.startswith('!pick ') and (is_captain_in_match or is_mod):
        await rk.pick_map(message.author, message.channel, message.content.split()[1], force=is_mod)
    elif message.content.startswith('!ban ') and (is_captain_in_match or is_mod):
        await rk.ban_map(message.author, message.channel, message.content.split()[1], force=is_mod)
    elif message.content.startswith('!side ') and (is_captain_in_match or is_mod):
        await rk.choose_side(message.author, message.channel, message.content.split()[1], force=is_mod)

    elif message.content.startswith('!say ') and (is_mod):
        parts = message.content.split()
        channel_id = parts[1][2:-1]
        msg = ' '.join(parts[2:])
        channel = discord.utils.get(message.author.server.channels, id=channel_id)
        await rk.client.send_message(channel, msg)

config = get_config('config.json')
rk = RoleKeeper(client, config)
client.run(config['app_bot_token'])
