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
import datetime

class Handle:
    def __init__(self, bot, message=None, member=None, channel=None):
        self.bot = bot
        self.member = member
        self.channel = channel
        self.message = message

        if self.message:
            self.member = self.message.author
            self.channel = self.message.channel

        self.team = None

        if self.member:
            try:
                db, error, _ = bot.find_cup_db(self.member.server, captain=self.member.id)
                if not error:
                    self.team = db['captains'][self.member.id].team
            except KeyError:
                pass

    ## Override pickle serialization
    def __getstate__(self):
        state = dict(self.__dict__)

        # We cannot serialize Discord.Message because of WeakSet
        # thus, remove them

        state['bot'] = None

        state['_msg_ch'] = self.message.channel.id \
                           if self.message \
                              and self.message.channel \
                              else self.channel.id \
                                   if self.channel else None

        state['_msg_id'] = self.message.id \
                           if self.message else None

        state['_msg_am'] = self.message.author.id \
                           if  self.message \
                               and self.message.author \
                               else self.member.id \
                                    if self.member else None

        state['message'] = None
        state['member'] = None
        state['channel'] = None
        state['team'] = None

        return state

    ## Once the bot is ready, restore the message
    async def resume(self, server, bot):
        channel = discord.utils.get(server.channels, id=self._msg_ch) \
                  if self._msg_ch else None
        try:
            message = await bot.client.get_message(channel, self._msg_id) \
                      if channel and self._msg_id else None
        except:
            message = None
        member = discord.utils.get(server.members, id=self._msg_am) \
                 if self._msg_am else None

        if message:
            self.__init__(bot, message=message)
        elif channel and member:
            self.__init__(bot, channel=channel, member=member)


    def clone(self):
        h = Handle(self.bot)
        h.member = self.member
        h.channel = self.channel
        h.message = self.message
        h.team = self.team
        return h

    async def reply(self, msg):
        if self.member:
            return await self.send('{} {}'.format(self.member.mention, msg))
        else:
            return await self.send(msg)

    async def react(self, reaction, err_count=0):
        if not self.message:
            return None

        try:
            return await self.bot.client.add_reaction(self.message, reaction)
        except discord.errors.HTTPException as e:
            print('WARNING: HTTPexception: {}'.format(str(e)))
            err_count += 1
            if err_count > 5:
                return
            await asyncio.sleep(10)
            return await self.react(reaction, err_count=err_count)

    async def send(self, msg, err_count=0):
        try:
            return await self.bot.client.send_message(self.channel, msg)
        except discord.errors.HTTPException as e:
            print('WARNING: HTTPexception: {}'.format(str(e)))
            err_count += 1
            if err_count > 5:
                return
            await asyncio.sleep(10)
            return await self.send(msg, err_count=err_count)

    async def send_file(self, file, name, msg, err_count=0):
        try:
            return await self.bot.client.send_file(self.channel, file, filename=name, content=msg)
        except discord.errors.HTTPException as e:
            print('WARNING: HTTPexception: {}'.format(str(e)))
            err_count += 1
            if err_count > 5:
                return
            await asyncio.sleep(10)
            return await self.send_file(file, name, msg, err_count=err_count)

    async def edit(self, msg, err_count=0):
        try:
            return await self.bot.client.edit_message(self.message, msg)
        except discord.errors.HTTPException as e:
            print('WARNING: HTTPexception: {}'.format(str(e)))
            err_count += 1
            if err_count > 5:
                return
            await asyncio.sleep(10)
            return await self.edit(msg, err_count=err_count)

    async def embed(self, title, msg, color, fields=[], err_count=0):
        try:
            embed = discord.Embed(title=title,
                                  type='rich',
                                  description=msg,
                                  timestamp=datetime.datetime.utcnow(),
                                  color=color)
            for field in fields:
                embed.add_field(name=field['name'], value=field['value'], inline=False)

            return await self.bot.client.send_message(self.channel, embed=embed)
        except discord.errors.HTTPException as e:
            print('WARNING: HTTPexception: {}'.format(str(e)))
            err_count += 1
            if err_count > 5:
                return
            await asyncio.sleep(10)
            return await self.embed(title, msg, color, fields=fields, err_count=err_count)

    async def edit_embed(self, title, msg, color, fields=[], err_count=0):
        try:
            embed = discord.Embed(title=title,
                                  type='rich',
                                  description=msg,
                                  timestamp=datetime.datetime.utcnow(),
                                  color=color)
            for field in fields:
                embed.add_field(name=field['name'], value=field['value'], inline=False)

            return await self.bot.client.edit_message(self.message, embed=embed)
        except discord.errors.HTTPException as e:
            print('WARNING: HTTPexception: {}'.format(str(e)))
            err_count += 1
            if err_count > 5:
                return
            await asyncio.sleep(10)
            return await self.edit_embed(title, msg, color, fields=fields, err_count=err_count)

    async def delete(self, err_count=0):
        try:
            return await self.bot.client.delete_message(self.message)
        except discord.errors.HTTPException as e:
            print('WARNING: HTTPexception: {}'.format(str(e)))
            err_count += 1
            if err_count > 5:
                return
            await asyncio.sleep(10)
            return await self.delete(err_count=err_count)

    async def broadcast(self, bcast_id, msg):
        if not self.bot.is_broadcast_enabled(self.channel.server):
            return

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
