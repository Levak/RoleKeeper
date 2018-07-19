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
import asyncio
import traceback
import urllib
import datetime

from handle import Handle

import discord
import bs4 as BeautifulSoup


class EsportsDriver:
    def __init__(self, bot, db, url, cup_name, cat_id):
        self.bot = bot
        self.server = None
        self.db = db
        self.url = url
        self.cup_name = cup_name
        self.cat_id = cat_id

        self.max_advance = 0
        self.refresh_period = 60
        self.utc_offset = 0

        if bot and bot.config and 'driver' in bot.config:
            if 'max_advance' in bot.config['driver']:
                self.max_advance = bot.config['driver']['max_advance']
            if 'refresh_period' in bot.config['driver']:
                self.refresh_period = bot.config['driver']['refresh_period']
            if 'utc_offset' in bot.config['driver']:
                self.utc_offset = bot.config['driver']['utc_offset']

        self.match_status = {}
        self.cached_matches = {}
        self.handle = None
        self.status_handle = None

        self.alive = True
        self.started = False
        self.start_event = asyncio.Event(loop=self.bot.client.loop)
        self.create_queue = asyncio.Queue(loop=self.bot.client.loop)
        self.create_task = self.bot.client.loop.create_task(self.create_task_loop())
        self.parser_task = self.bot.client.loop.create_task(self.parser_task_loop())


        self.last_status_string = ''
        self.known_match_errors = {}

    ## Override pickle serialization
    def __getstate__(self):
        state = {
            'url': self.url,
            'cup_name': self.cup_name,
            'cat_id': self.cat_id,
            'handle': self.handle,
            'status_handle': self.status_handle,
            'alive': self.alive,
            'started': self.started,
        }

        return state

    async def resume(self, server, bot, db):
        started = self.started

        handle = self.handle
        if handle:
            await handle.resume(server, bot)

        status_handle = self.status_handle
        if status_handle:
            await status_handle.resume(server, bot)

        # Recreate the object
        self.__init__(bot, db, self.url, self.cup_name, self.cat_id)
        self.status_handle = status_handle

        # If the driver was running, start it again
        if started:
            self.start(server, handle)

    def start(self, server, handle):
        print('{}: Start sync'.format(server.name if server else ''))
        self.handle = handle
        self.server = server
        self.start_event.set()
        self.started = True

    async def stop(self):
        print('{}: Stop sync'.format(self.server.name if self.server else ''))
        self.alive = False

        await self.update_status(force=True)

        if self.create_task:
            self.create_task.cancel()

        if self.parser_task:
            self.parser_task.cancel()

    class MatchStatus:
        ERROR = -1
        WAITING = 0
        CREATING = 1
        PROGRESS = 2
        DONE = 3
        FINISHED = 4

        def __init__(self, bot, id, team1, team2):
            self.id = id
            self.team1 = team1
            self.team2 = team2
            self.url = None
            self.match = None
            self.channel = None
            self.round = None
            self.status = self.CREATING

            self.status_emojies = {
                self.FINISHED: ':first_place: ',
                self.DONE:     ':gun: ',
                self.PROGRESS: ':hammer: ',
                self.CREATING: bot.emotes['loading'],
                self.WAITING:  ':clock3: ',
                self.ERROR:    ':no_entry: '
            }

        def __str__(self):
            return '{se}{s}{round} [link]({url}) - {ch} **{t1}** vs **{t2}**{s}'\
                       .format(se=self.status_emojies[self.status] \
                               if self.status in self.status_emojies else self.status,
                               s='~~' if self.status == self.FINISHED else '',
                               round=self.round if self.round else '',
                               t1=self.team1,
                               t2=self.team2,
                               ch=self.channel.mention if self.channel else '',
                               url=self.url if self.url else '')

    def update_match_status(self,
                            status=None,
                            id=None,
                            team1=None,
                            team2=None,
                            url=None,
                            round=None,
                            finished=False,
                            waiting=False):

        #print('Update match status: ', status != None, id, team1, team2, url, round, finished)

        if id and team1 and team2:
            self.match_status[id] = EsportsDriver.MatchStatus(self.bot, id, team1, team2)
            match_status = self.match_status[id]
        elif status:
            match_status = status
        else:
            return

        if url:
            match_status.url = url
        if round:
            match_status.round = round

        if not match_status.match:
            match_status.match = self.get_match(match_status.id, match_status.team1, match_status.team2)

        if not match_status.channel:
            channel_name = self.get_channel(match_status.id)
            match_status.channel = discord.utils.get(self.server.channels,
                                                     name=channel_name) if channel_name else None

        if waiting:
            match_status.status = match_status.WAITING
        elif finished:
            match_status.status = match_status.FINISHED
            if match_status.match:
                match_status.match.auto_done = True
                if not match_status.match.is_done():
                    # TODO temporary... find a way to use await close_match(handle)
                    print('Automatically closed match: {}'.format(match_status.match.url))
        elif match_status.match:
            if match_status.status < match_status.DONE and match_status.match.is_done():
                match_status.status = match_status.DONE
            elif match_status.status < match_status.PROGRESS:
                match_status.status = match_status.PROGRESS

        if id in self.known_match_errors \
           and len(self.known_match_errors[id]) > 0:
            match_status.status = match_status.ERROR


    async def update_status(self, force=False):

        title = '{cup} status'\
            .format(cup=self.cup_name)

        status_arr = []
        all_status_arr = []
        for match_status in sorted(self.match_status.values(),
                                   key=lambda m: str(m.id)):
            if force:
                self.update_match_status(status=match_status)
            if match_status.status < match_status.FINISHED:
                status_arr.append(str(match_status))

            all_status_arr.append(str(match_status))

        MAX_STATUS_LINES = 16
        cropped = False
        if len(all_status_arr) <= MAX_STATUS_LINES:
            status_arr = all_status_arr
        elif len(status_arr) > MAX_STATUS_LINES:
            status_arr = status_arr[:MAX_STATUS_LINES]
            cropped = True

        status_string = '_Refreshed every {sec}sec_\n{status}\n{cropped}'\
            .format(status='\n'.join(status_arr),
                    sec=self.refresh_period,
                    cropped='[...]' if cropped else '')

        has_status_handle = self.status_handle and self.status_handle.message

        if force and not has_status_handle:
            return

        color = 0x2ecc71 if self.alive else 0

        if status_string != self.last_status_string or force:
            if not has_status_handle:
                message = await self.handle.embed(title, status_string, color)
                self.status_handle = Handle(self.bot, message=message)
                self.status_handle.member = self.handle.member
            else:
                await self.status_handle.edit_embed(title, status_string, color)
            self.last_status_string = status_string

    ## Asyncio task that waits on its queue for new match rooms to create in
    ## Discord
    async def create_task_loop(self):
        print ('Create task')

        await self.start_event.wait()

        while self.alive:
            try:
                if self.create_queue.qsize() == 0:
                    await self.update_status(force=True)

                item = await self.create_queue.get()
                match_id, match_url, team1_name, team2_name, mode, time = \
                    item[0], item[1], item[2], item[3], item[4], item[5]

                await self.garbage_collect()

                print (match_id, team1_name, team2_name, mode, time)

                await self.create_match(match_id, match_url, team1_name, team2_name, mode, time)

            except asyncio.CancelledError:
                break
            except:
                traceback.print_exc()
                await asyncio.sleep(60)
                pass

            #await asyncio.sleep(1.2)

        print ('End of create task')


    ## Asyncio task that regularly checks the esports page to see if there are
    ## new matches to create
    async def parser_task_loop(self):
        print ('Parser task')

        await self.start_event.wait()
        self._trigger_garbage_collector = True

        while self.alive:
            try:

                bracket_url = self.url
                if 'bracket' not in bracket_url:
                    bracket_url = urllib.parse.urljoin(bracket_url, 'bracket')

                if self.create_queue.qsize() == 0:
                    await self.parse_bracket(bracket_url)

            except asyncio.CancelledError:
                break
            except:
                traceback.print_exc()
                pass

            await asyncio.sleep(self.refresh_period)

        print ('End of parser task')

    ## Garbage collector for match rooms
    async def garbage_collect(self):
        if 'driver' not in self.bot.config \
           or 'autodelete' not in self.bot.config['driver'] \
           or self.bot.config['driver']['autodelete'] != True:
            return

        if not self._trigger_garbage_collector:
            return
        self._trigger_garbage_collector = False

        await self.bot.wipe_matches(self.handle.message if self.handle else None,
                                    self.cup_name,
                                    mode=self.bot.WIPE_AUTO)

    ## Display an error about a match only once.
    ##
    ## This is required since the driver regularly checks the same page is
    ## going to constantly spam Discord with the same error over and over
    ## again (e.g. missing captain).
    async def match_error(self, match_id, msg):
        if match_id not in self.known_match_errors:
            self.known_match_errors[match_id] = []

        # Should we skip that error?
        if msg in self.known_match_errors[match_id]:
            print('Skipped error for match {}: {}'.format(match_id, msg))
            return

        self.known_match_errors[match_id].append(msg)
        await self.handle.reply(msg)

    ## Parse the grid page to create all new matches
    async def parse_bracket(self, bracket_url):
        split_url = urllib.parse.urlsplit(self.url)
        base_url = urllib.parse.urlunsplit( (split_url.scheme, split_url.netloc, '', '', '') )

        connector = aiohttp.TCPConnector(limit=20)
        client = aiohttp.ClientSession(connector=connector)

        print('Parsing: {}'.format(bracket_url))
        async with client.get(bracket_url) as response:
            assert response.status == 200, \
                'Error code {} when accessing the grid'\
                    .format(response.status)
            bracket_text = await response.read()

        bracket_dom = BeautifulSoup.BeautifulSoup(bracket_text, "html.parser")

        co_matches = []
        matches = bracket_dom.find_all('div', attrs={'class': u'tn_match'})

        for match in matches:
            team1_d = match.find('div', attrs={'class': u'team1'})
            team2_d = match.find('div', attrs={'class': u'team2'})
            details_d = match.find('div', attrs={'class': u'match_detail_content'})

            team1_a = team1_d.find('a') if team1_d else None
            team2_a = team2_d.find('a') if team2_d else None

            team1_name = team1_a.string.strip() if team1_a else None
            team2_name = team2_a.string.strip() if team2_a else None

            if not team1_name or not team2_name:
                continue

            round_d = match.parent
            round_wrp_d = round_d.find('div', attrs={'class':u'round_name_wrapper'}) if round_d else None
            round_name_d = round_wrp_d.find('div', attrs={'class':u'fwb'}) if round_wrp_d else None
            round_name = round_name_d.string.strip() if round_name_d else ''

            finished = False
            match_url = None

            if match.has_attr('data-match_id'):
                match_id = match.attrs['data-match_id']
                match_url = urllib.parse.urljoin(base_url, 'match/{}'.format(match_id))

                server = self.server
                rk_match = self.get_match(match_id, team1_name, team2_name)

                if 'winner' in team1_d.attrs['class'] \
                   or 'winner' in team2_d.attrs['class'] \
                   or details_d:
                    finished = True
                elif not rk_match:
                    co_matches.append(
                        asyncio.ensure_future(
                            self.parse_match(client, match_url, match_id, team1_name, team2_name)))

            self.update_match_status(id=match_id,
                                     team1=team1_name,
                                     team2=team2_name,
                                     url=match_url,
                                     round=round_name,
                                     finished=finished)

        await self.update_status()
        if len(co_matches) > 0:
            print('Found {} new matches'.format(len(co_matches)))
            self._trigger_garbage_collector = True
            await asyncio.wait(co_matches)
            print('End of parsing')
        await self.update_status()
        client.close()

    ## Parse the match page to know who is banning first
    async def parse_match(self, client, match_url, match_id, team1_name, team2_name):
        match_text = ''
        async with client.get(match_url) as response:
            assert response.status == 200, \
                'Error code {} when accessing the match {}'\
                    .format(response.status, match_url)
            match_text = await response.read()

        print('Parsing: {}'.format(match_url))

        match_dom = BeautifulSoup.BeautifulSoup(match_text, "html.parser")

        date_d = match_dom.find('div', attrs={'class': u'match-data__date'})
        date_s = date_d.string.strip() if date_d else None
        utcoff = datetime.timedelta(hours=self.utc_offset)
        max_advance = datetime.timedelta(seconds=self.max_advance)
        utcnow = datetime.datetime.utcnow()
        unknown_date = False
        try:
            date = datetime.datetime.strptime(date_s, '%d.%m.%Y %H:%M') - utcoff \
                   if date_s else utcnow
        except:
            print('ERROR: Failed to parse date "{}" for match id "{}"'.format(date_s, match_id))
            unknown_date = True

        if utcnow < date - max_advance or unknown_date:
            if match_id in self.match_status:
                match_status = self.match_status[match_id]
                self.update_match_status(status=match_status, waiting=True)
                return


        strike_d = match_dom.find('div', attrs={'class': u'match-data__mapstrike'})
        strike_s = strike_d.find('strong') if strike_d else None
        strike_name = strike_s.string.strip() if strike_s else None

        # Swap the teams if it's not the team1 that bans first
        if strike_name and strike_name != team1_name:
            t = team1_name
            team1_name = team2_name
            team2_name = t

        mode_d = match_dom.find('div', attrs={'class': u'infoblock match-data'})
        mode_p = mode_d.find('p') if mode_d else None
        mode_name = mode_p.string.strip() if mode_p else None

        mode = self.bot.MATCH_BO1
        if mode_name == 'Best of 1':
            mode = self.bot.MATCH_BO1
        elif mode_name == 'Best of 2':
            mode = self.bot.MATCH_BO2
        elif mode_name == 'Best of 3':
            mode = self.bot.MATCH_BO3
        elif mode_name:
            print('Unknown mode for match {}: {}'.format(match_id, mode_name))
        else:
            print('No mode selected for match {}, using best-of-1'.format(match_id))

        self.create_queue.put_nowait( (match_id, match_url, team1_name, team2_name, mode, date) )

    ## Get the associated Rolekeeper match for given team names and add it to
    ## internal driver cache if found.
    def get_match(self, match_id, team1_name, team2_name):

        # If we didn't find the match id in our cache, we need to find it from
        # Rolekeeper DB
        if match_id not in self.cached_matches:

            for channel, rk_match in self.db['matches'].items():
                # TODO what to do for duplicate matches? (e.g. loser bracket)
                if (rk_match.teamA.name == team1_name \
                   and rk_match.teamB.name == team2_name) \
                    or (rk_match.teamA.name == team2_name \
                        and rk_match.teamB.name == team1_name):

                    self.cached_matches[match_id] = channel
                    self.known_match_errors[match_id] = []
                    break

        else:
            pass

        if match_id in self.cached_matches:
            if self.cached_matches[match_id] not in self.db['matches']:
                del self.cached_matches[match_id]
                if match_id in self.match_status:
                    del self.match_status[match_id]
                return self.get_match(match_id, team1_name, team2_name)

            return self.db['matches'][self.cached_matches[match_id]]
        else:
            return None

    def get_channel(self, match_id):
        if match_id in self.cached_matches:
            return self.cached_matches[match_id]
        else:
            return None

    ## Create the match room in Discord
    async def create_match(self, match_id, match_url, team1_name, team2_name, mode, time):
        captainA = None
        try:
            captainA = next(c for did, c in self.db['captains'].items() if c.team_name == team1_name)
        except StopIteration:
            await self.match_error(match_id, 'Cannot find ' + team1_name)
            return

        captainB = None
        try:
            captainB = next(c for did, c in self.db['captains'].items() if c.team_name == team2_name)
        except StopIteration:
            await self.match_error(match_id, 'Cannot find ' + team2_name)
            return

        cat_id = ''
        if captainA.group:
            cat_id = captainA.group.id
        elif captainB.group:
            cat_id = captainB.group.id

        if self.cat_id:
            cat_id = self.cat_id

        try:
            await self.bot.matchup(self.handle.message, \
                                   self.handle.message.server, \
                                   captainA.team, captainB.team, \
                                   cat_id, self.db['cup'].name, \
                                   mode=mode,
                                   url=match_url)
        except:
            await self.match_error(match_id, 'Error creating match {} vs {}'\
                                   .format(captainA.team.name,
                                           captainB.team.name))
            return

        # Cache the match
        _ = self.get_match(match_id, team1_name, team2_name)
