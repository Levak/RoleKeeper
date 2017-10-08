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

class Match:
    def __init__(self, teamA, teamB, maps):
        self.teams = [ teamA, teamB ]
        self.teamA = teamA
        self.teamB = teamB
        self.maps = maps
        self.banned_maps = []
        self.picked_maps = []
        self.chosen_side = None
        self.turn = 0
        self.sequence = [ (teamA, 'ban'), (teamB, 'ban'),
                          (teamA, 'ban'), (teamB, 'ban'),
                          (teamA, 'ban'), (teamB, 'ban'),
                          (teamB, 'side') ]

        self.sides = { 'defends': [ 'defends', 'defend', 'defense', 'defence', 'warface', 'def', 'd' ],
                       'attacks' : [ 'attacks', 'attack', 'attacking', 'blackwood', 'offense', 'att', 'a' ] }

    def is_in_match(self, member):
        return self.teamA in member.roles or self.teamB in member.roles

    def find_map(self, map_name):
        try:
            return next(m for m in self.maps \
                        if SequenceMatcher(None,
                                           sanitize_input(translit_input(m)),
                                           sanitize_input(translit_input(map_name))
                                       ).ratio() > 0.8)
        except StopIteration:
            return None

    async def check(self, action, handle, map_id, force=False):
        if self.turn >= len(self.sequence):
            await handle.reply("Pick & Ban sequence is over!")
            return False

        team, check_action = self.sequence[self.turn]

        if team != handle.team and not force:
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
        await self.status(handle)
        await handle.broadcast('match_created', ':sparkle: Match created: `{match_id}`\n**{teamA}** vs **{teamB}**\n'\
                               .format(teamA=self.teamA,
                                       teamB=self.teamB,
                                       match_id=handle.channel.name))


    async def ban_map(self, handle, banned_map, force=False):
        banned_map_id = self.find_map(banned_map)

        if not await self.check('ban', handle, banned_map_id, force):
            return

        self.banned_maps.append(banned_map_id)
        print('{ch}: {team} banned map {map}'\
              .format(ch=handle.channel,
                      team=handle.team,
                      map=banned_map_id))
        await self.update_turn(handle)

    async def pick_map(self, handle, picked_map, force=False):
        picked_map_id = self.find_map(picked_map)

        if not await self.check('pick', handle, picked_map_id, force):
            return

        self.picked_maps.append(picked_map_id)
        print('{ch}: {team} picked map {map}'\
              .format(ch=handle.channel,
                      team=handle.team,
                      map=picked_map_id))
        await self.update_turn(handle)

    async def choose_side(self, handle, chosen_side, force=False):
        try:
            side_id = next(k for k, side in self.sides.items() if chosen_side in side )
        except StopIteration:
            side_id = None

        if not await self.check('side', handle, side_id, force):
            return

        self.chosen_side = side_id
        print('{ch}: {team} chose side {side}'\
              .format(ch=handle.channel,
                      team=handle.team,
                      side=side_id))
        await self.update_turn(handle)

    async def update_turn(self, handle):
        self.turn += 1
        await self.status(handle)
        if self.turn >= len(self.sequence):
            await self.summary(handle)

    async def status(self, handle):
        msg = '\n'.join([' - {:<15} {:>6}'.format(m, '[ban]' if m in self.banned_maps else '[pick]' if m in self.picked_maps else '~  ') for m in self.maps ])
        if self.turn >= len(self.sequence):
            turn = ''
        else:
            turn = 'Your turn {team}! Use `!{action} xxxxx`.'\
                .format(team=self.sequence[self.turn][0].mention,
                        action=self.sequence[self.turn][1])

        await handle.send('Current sequence status ({i}/{n}):\n```\n{msg}\n```\n{turn}'\
                          .format(i=self.turn,
                                  n=len(self.sequence),
                                  msg=msg,
                                  turn=turn))

    async def summary(self, handle):
        map_id = next(e for e in self.maps if e not in self.banned_maps)
        await handle.send('Ban sequence finished!\n\nMap to play: **{map1}** ({teamB} **{side}**)\nglhf!\n\n:warning: **And dont forget to screenshot the end result**! :warning: '\
                          .format(teamA=self.teamA,
                                  teamB=self.teamB,
                                  map1=map_id,
                                  side=self.chosen_side))

        await handle.broadcast('match_starting', ':arrow_forward: Match starting: `{match_id}`\n**{teamA}** vs **{teamB}**\n - Map: **{map1}** ({teamB} **{side}**)\n'\
                               .format(teamA=self.teamA,
                                       teamB=self.teamB,
                                       map1=map_id,
                                       side=self.chosen_side,
                                       match_id=handle.channel.name))


class MatchBo2(Match):
    def __init__(self, teamA, teamB, maps):
        Match.__init__(self, teamA, teamB, maps)

        self.sequence = [ (teamA, 'ban'), (teamB, 'ban'),
                          (teamA, 'pick'), (teamB, 'pick'),
                          (teamB, 'side') ]

    async def summary(self, handle):
        await handle.send('Pick & ban sequence finished!\n\nMap 1: **{map1}** ({teamB} **{side}**)\nMap 2: **{map2}** ({teamA} **{side}**)\nglhf!\n\n:warning: **And dont forget to screenshot all match results**! :warning:'\
                          .format(teamA=self.teamA,
                                  teamB=self.teamB,
                                  map1=self.picked_maps[0],
                                  map2=self.picked_maps[1],
                                  side=self.chosen_side))

        await handle.broadcast('match_starting', ':arrow_forward: Match starting: `{match_id}`\n**{teamA}** vs **{teamB}**\n - Map 1: **{map1}** ({teamB} **{side}**)\n - Map 2: **{map2}** ({teamA} **{side}**)\n'\
                          .format(teamA=self.teamA,
                                  teamB=self.teamB,
                                  map1=self.picked_maps[0],
                                  map2=self.picked_maps[1],
                                  side=self.chosen_side,
                                  match_id=handle.channel.name))

class MatchBo3(Match):
    def __init__(self, teamA, teamB, maps):
        Match.__init__(self, teamA, teamB, maps)

        self.sequence = [ (teamA, 'ban'), (teamB, 'ban'),
                          (teamA, 'pick'), (teamB, 'pick'),
                          (teamA, 'ban'), (teamB, 'ban'),
                          (teamB, 'side') ]

    async def summary(self, handle):
        map_id = next(e for e in self.maps if e not in self.banned_maps and e not in self.picked_maps)
        await handle.send('Pick & ban sequence finished!\n\nMap 1: **{map1}** ({teamB} **{side}**)\nMap 2: **{map2}** ({teamA} **{side}**)\nTie-breaker map: **{map3}** ({teamB} **{side}**)\nglhf!\n\n:warning: **And dont forget to screenshot all match results**! :warning:'\
                          .format(teamA=self.teamA,
                                  teamB=self.teamB,
                                  map1=self.picked_maps[0],
                                  map2=self.picked_maps[1],
                                  map3=map_id,
                                  side=self.chosen_side))

        await handle.broadcast('match_starting', ':arrow_forward: Match starting: `{match_id}`\n**{teamA}** vs **{teamB}**\n - Map 1: **{map1}** ({teamB} **{side}**)\n - Map 2: **{map2}** ({teamA} **{side}**)\n - Tie-breaker map: **{map3}** ({teamB} **{side}**)\n'\
                          .format(teamA=self.teamA,
                                  teamB=self.teamB,
                                  map1=self.picked_maps[0],
                                  map2=self.picked_maps[1],
                                  map3=map_id,
                                  side=self.chosen_side,
                                  match_id=handle.channel.name))
