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

import asyncio

from difflib import SequenceMatcher
from inputs import sanitize_input, translit_input

bo1_title = 'BEST OF 1'
bo1_welcome_message =\
"""
Welcome {m_teamA} and {m_teamB}!

This text channel will be used by the judge and team captains to exchange anything about the match between teams {teamA} and {teamB}.

The ban sequence is made using the `!ban` command team by team until one remains. Last team to ban also needs to chose the side they will play on using `!side xxxx` (attack or defend).

For instance, team A types `!ban Pyramid` which will then ban the map _Pyramid_ from the match, team B types `!ban d17` which will ban the map D-17, and so on, until only one map remains. team A then picks the side using `!side attack`.
"""

bo2_title = 'BEST OF 2'
bo2_welcome_message =\
"""
Welcome {m_teamA} and {m_teamB}!

This text channel will be used by the judge and team captains to exchange anything about the match between teams {teamA} and {teamB}.

The pick&ban sequence is made using the `!pick`, `!ban` and `!side` commands one by one using the order defined below.

For instance, team A types `!ban Yard` which will then ban the map _Yard_ from the match, team B types `!ban d17` which will ban the map D-17. team A would then type `!pick Destination`, picking the first map and so on, until only one map remains, which will be the tie-breaker map. team B then picks the side using `!side attack`.
"""

bo3_title = 'BEST OF 3'
bo3_welcome_message =\
"""
Welcome {m_teamA} and {m_teamB}!

This text channel will be used by the judge and team captains to exchange anything about the match between teams {teamA} and {teamB}.

The pick&ban sequence is made using the `!pick`, `!ban` and `!side` commands one by one using the order defined below.

For instance, team A types `!ban Yard` which will then ban the map _Yard_ from the match, team B types `!ban d17` which will ban the map D-17. team A would then type `!pick Destination`, picking the first map and so on, until only one map remains, which will be the tie-breaker map. team B then picks the side using `!side attack`.
"""


class Match:
    def __init__(self, teamA, teamB, maps):
        self.teams = [ teamA, teamB ]
        self.teamA = teamA
        self.teamB = teamB
        self.maps = maps
        self.banned_maps = []
        self.picked_maps = []
        self.picked_sides = []
        self.turn = 0

        self.mode_title = bo1_title
        self.mode_intro = bo1_welcome_message

        self.sequence = []
        for i in range(len(self.maps)):
            t = teamA if i % 2 == 0 else teamB
            a = 'side' if i >= len(self.maps) - 1 else 'ban'
            self.sequence.append( (t, a) )

        self.sides = { 'defends': [ 'defends', 'defend', 'defense', 'defence', 'warface', 'wf', 'def', 'd' ],
                       'attacks' : [ 'attacks', 'attack', 'attacking', 'blackwood', 'offense', 'bw', 'att', 'a' ] }

        self.status_handle = None
        self.turn_handle = None
        self.ended = False
        self.last_is_a_pick = True
        self.last_picked = False

    ## Override pickle serialization
    def __getstate__(self):
        state = dict(self.__dict__)

        # We cannot serialize Discord.Message because of WeakSet
        # thus, remove them
        state['status_handle'] = None
        state['turn_handle'] = None

        return state

    def is_in_match(self, member):
        return self.teamA.role in member.roles or self.teamB.role in member.roles

    def find_map(self, map_name):
        try:
            return next(m for m in self.maps \
                        if SequenceMatcher(None,
                                           sanitize_input(translit_input(m)),
                                           sanitize_input(translit_input(map_name))
                                       ).ratio() > 0.8)
        except StopIteration:
            return None

    def is_done(self):
        return self.turn >= len(self.sequence)

    async def check(self, action, handle, map_id, force=False):
        if self.is_done():
            await handle.reply("Pick & Ban sequence is over!")
            return False

        team, check_action = self.sequence[self.turn]

        if not force and team.name != handle.team.name:
            await handle.reply('Not your turn to {}!'.format(action))
            return False

        if action != check_action:
            await handle.reply('Not a {} turn but a **{}** one!'.format(action, check_action))
            return False

        if action == 'side':
            if map_id not in self.sides:
                await handle.reply("What side is that?")
                return False
            else:
                return True

        if not map_id:
            await handle.reply("That map is not in the map poll, or I didn't understand you")
            return False

        if map_id in self.banned_maps:
            await handle.reply("That map has already been banned, please choose another one")
            return False

        if map_id in self.picked_maps:
            await handle.reply("That map has already been picked, please choose another one")
            return False

        return True

    async def begin(self, handle):

        intro = self.mode_intro.format(m_teamA=self.teamA.role.mention,
                                       m_teamB=self.teamB.role.mention,
                                       teamA=self.teamA.name,
                                       teamB=self.teamB.name)

        seq = ''.join( [ '• {}: {}\n'.format(s[0].name, s[1]) for s in self.sequence ] )
        await handle.embed(self.mode_title, intro, 0,
                           fields=[ { 'name': 'Pick & ban sequence', 'value': seq } ])

        await self.status(handle)

        await handle.broadcast('match_created', ':sparkle: Match created: `{match_id}`\n**{teamA}** vs **{teamB}**\n'\
                               .format(teamA=self.teamA.name,
                                       teamB=self.teamB.name,
                                       match_id=handle.channel.name))


    async def ban_map(self, handle, banned_map, force=False):
        banned_map_id = self.find_map(banned_map)

        if not await self.check('ban', handle, banned_map_id, force):
            return False

        self.banned_maps.append(banned_map_id)
        print('{ch}: {team} banned map {map}'\
              .format(ch=handle.channel,
                      team=handle.team.name if handle.team else '<referee>',
                      map=banned_map_id))
        await self.update_turn(handle)
        return True

    async def pick_map(self, handle, picked_map, force=False):
        picked_map_id = self.find_map(picked_map)

        if not await self.check('pick', handle, picked_map_id, force):
            return False

        self.picked_maps.append(picked_map_id)
        print('{ch}: {team} picked map {map}'\
              .format(ch=handle.channel,
                      team=handle.team.name if handle.team else '<referee>',
                      map=picked_map_id))
        await self.update_turn(handle)
        return True

    async def choose_side(self, handle, chosen_side, force=False):
        try:
            side_id = next(k for k, side in self.sides.items() if chosen_side in side )
        except StopIteration:
            side_id = None

        if not await self.check('side', handle, side_id, force):
            return False

        self.picked_sides.append(side_id)
        print('{ch}: {team} chose side {side}'\
              .format(ch=handle.channel,
                      team=handle.team.name if handle.team else '<referee>',
                      side=side_id))
        await self.update_turn(handle)
        return True

    async def undo_map(self, handle):
        self.turn = self.turn - 1
        if self.turn < 0:
            self.turn = 0

        a = self.sequence[self.turn][1]
        s = True

        if a == 'side':
            if len(self.picked_sides) > 0:
                self.picked_sides.pop()
            else:
                s = False
        elif a == 'pick':
            if len(self.picked_maps) > 0:
                self.picked_maps.pop()
                if self.last_picked:
                    if len(self.picked_maps) > 0:
                        self.picked_maps.pop()
                        self.last_picked = False
                    else:
                        s = False
            else:
                s = False
        elif a == 'ban':
            if len(self.banned_maps) > 0:
                self.banned_maps.pop()
                if self.last_picked:
                    if len(self.picked_maps) > 0:
                        self.picked_maps.pop()
                        self.last_picked = False
                    else:
                        s = False
            else:
                s = False
        else:
            s = False

        if not s:
            await handle.reply('Cannot undo')
            return False

        print('{ch}: referee used undo'\
              .format(ch=handle.channel))

        await self.status(handle)
        return True

    async def update_turn(self, handle):
        self.turn += 1
        await self.status(handle)
        if self.turn >= len(self.sequence):
            await self.summary(handle)

    async def status(self, handle):
        msg = '\n'.join([ '{em} {fmt}{map}{fmt}'\
                          .format(map=m,
                                  fmt='~~' if m in self.banned_maps else '**' if m in self.picked_maps else '_',
                                  em=':hammer:' if m in self.banned_maps else ':point_right:' if m in self.picked_maps else ':grey_question:')\
                          for m in self.maps ])

        if self.turn_handle:
            await self.turn_handle.delete()
            self.turn_handle = None

        title = 'Current sequence status ({i}/{n}):'\
            .format(i=self.turn, n=len(self.sequence))

        status = 0x2ecc71 if self.turn < len(self.sequence) else 0x992d22

        if not self.status_handle:
            self.status_handle = handle.clone()
            self.status_handle.message = await handle.embed(title, msg, status)
        else:
            await self.status_handle.edit_embed(title, msg, status)

        # If 1 map is remaining, it's a pick
        if self.last_is_a_pick and \
           not self.last_picked and \
           len(self.maps) - len(self.banned_maps) - len(self.picked_maps) == 1:
            map_id = next(e for e in self.maps if e not in self.banned_maps and e not in self.picked_maps)
            self.picked_maps.append(map_id)
            self.last_picked = True

        if self.turn < len(self.sequence):
            turn = 'Your turn {team}! Use `!{action} {choice}`.{extra}'\
                .format(team=self.sequence[self.turn][0].role.mention,
                        action=self.sequence[self.turn][1],
                        choice='attack/defense' if self.sequence[self.turn][1] == 'side' else 'xxxxx',
                        extra=self.get_turn_info(self.sequence[self.turn]))

            self.turn_handle = handle.clone()
            self.turn_handle.message = await handle.send(turn)

    async def summary(self, handle):
        await handle.send('Ban sequence finished!\n\nMap to play: **{map1}** ({teamA} **{side}**)\nglhf!\n\n:warning: **And dont forget to screenshot the end result**! :warning: '\
                          .format(teamA=self.teamA.name,
                                  teamB=self.teamB.name,
                                  map1=self.picked_maps[0],
                                  side=self.picked_sides[0]))

        await handle.broadcast('match_starting', ':arrow_forward: Match is ready to start: `{match_id}`\n**{teamA}** vs **{teamB}**\n - Map: **{map1}** ({teamA} **{side}**)\n'\
                               .format(teamA=self.teamA.name,
                                       teamB=self.teamB.name,
                                       map1=self.picked_maps[0],
                                       side=self.picked_sides[0],
                                       match_id=handle.channel.name))

    def get_turn_info(self, turn_tuple):
        action = turn_tuple[1]
        if action == 'side' and len(self.picked_maps) > 0:
            map_side = self.picked_maps[len(self.picked_sides)]
            return '   Map {id}: **{map}**'\
                .format(id=len(self.picked_sides) + 1,
                        map=map_side)
        else:
            return ''

class MatchBo2(Match):
    def __init__(self, teamA, teamB, maps):
        Match.__init__(self, teamA, teamB, maps)

        assert len(self.maps) >= 2, 'Not enough maps'

        self.mode_title = bo2_title
        self.mode_intro = bo2_welcome_message

        self.last_is_a_pick = False

        self.sequence = []
        last_i = len(self.maps) - 1
        pick_n = 0

        for i in range(max(0, len(self.maps) - 5) + 4):
            t = teamA if i % 2 == (1 if pick_n == 2 else 0) else teamB
            a = 'side' if pick_n == 2 \
                else 'pick' if i >= last_i - 4 \
                     else 'ban'
            if a == 'pick':
                pick_n += 1
            self.sequence.append( (t, a) )

    async def summary(self, handle):
        await handle.send('Pick & ban sequence finished!\n\nMap 1: **{map1}** ({teamB} **{side1}**)\nMap 2: **{map2}** ({teamA} **{side2}**)\nglhf!\n\n:warning: **And dont forget to screenshot all match results**! :warning:'\
                          .format(teamA=self.teamA.name,
                                  teamB=self.teamB.name,
                                  map1=self.picked_maps[0],
                                  map2=self.picked_maps[1],
                                  side1=self.picked_sides[0],
                                  side2=self.picked_sides[1]))

        await handle.broadcast('match_starting', ':arrow_forward: Match is ready to start: `{match_id}`\n**{teamA}** vs **{teamB}**\n - Map 1: **{map1}** ({teamB} **{side1}**)\n - Map 2: **{map2}** ({teamA} **{side2}**)\n'\
                          .format(teamA=self.teamA.name,
                                  teamB=self.teamB.name,
                                  map1=self.picked_maps[0],
                                  map2=self.picked_maps[1],
                                  side1=self.picked_sides[0],
                                  side2=self.picked_sides[1],
                                  match_id=handle.channel.name))

class MatchBo3(Match):
    def __init__(self, teamA, teamB, maps):
        Match.__init__(self, teamA, teamB, maps)

        assert len(self.maps) >= 5, 'Not enough maps'

        self.mode_title = bo3_title
        self.mode_intro = bo3_welcome_message

        self.sequence = []
        last_i = len(self.maps) - 1
        pick_n = 0

        for i in range(last_i + 2):
            t = teamA if i % 2 == (1 if i >= last_i else 0) else teamB
            a = 'side' if i >= last_i \
                else 'pick' if i == last_i - 3 or i == last_i - 4 \
                     else 'ban'
            if a == 'pick':
                pick_n += 1
            self.sequence.append( (t, a) )

        self.sequence.append( (self.sequence[-1][0], 'side') )

    async def summary(self, handle):
        await handle.send('Pick & ban sequence finished!\n\nMap 1: **{map1}** ({teamB} **{side1}**)\nMap 2: **{map2}** ({teamA} **{side2}**)\nTie-breaker map: **{map3}** ({teamA} **{side3}**)\nglhf!\n\n:warning: **And dont forget to screenshot all match results**! :warning:'\
                          .format(teamA=self.teamA.name,
                                  teamB=self.teamB.name,
                                  map1=self.picked_maps[0],
                                  map2=self.picked_maps[1],
                                  map3=self.picked_maps[2],
                                  side1=self.picked_sides[0],
                                  side2=self.picked_sides[1],
                                  side3=self.picked_sides[2]))

        await handle.broadcast('match_starting', ':arrow_forward: Match is ready to start: `{match_id}`\n**{teamA}** vs **{teamB}**\n - Map 1: **{map1}** ({teamB} **{side1}**)\n - Map 2: **{map2}** ({teamA} **{side2}**)\n - Tie-breaker map: **{map3}** ({teamA} **{side3}**)\n'\
                          .format(teamA=self.teamA.name,
                                  teamB=self.teamB.name,
                                  map1=self.picked_maps[0],
                                  map2=self.picked_maps[1],
                                  map3=self.picked_maps[2],
                                  side1=self.picked_sides[0],
                                  side2=self.picked_sides[1],
                                  side3=self.picked_sides[2],
                                  match_id=handle.channel.name))
