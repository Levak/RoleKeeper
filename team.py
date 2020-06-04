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

### Class that holds information about a role and a custom name
class CustomRole:
    def __init__(self, name, role):
        self.name = name
        self.role = role

    def __str__(self):
        return '{name} ({role})'\
            .format(name=self.name, role=str(self.role))

    ## Override pickle serialization
    def __getstate__(self):
        state = {
            'name': self.name,
            '_role_id': self.role.id if hasattr(self, 'role') and self.role else self._role_id,
        }

        return state

    async def resume(self, server, bot, db):
        if hasattr(self, '_role_id'):
            self.role = discord.utils.get(server.roles, id=self._role_id) \
                        if self._role_id else None

### Class that holds information about a cup
class Cup(CustomRole):
    def __init__(self, name, role, maps_key):
        CustomRole.__init__(self, name, role)
        self.maps_key = maps_key

    ## Override pickle serialization
    def __getstate__(self):
        state = super().__getstate__()
        state.update({
            'maps_key': self.maps_key
        })

        return state

### Class that holds information about a group
class Group(CustomRole):
    def __init__(self, id, name, role):
        self.id = id
        CustomRole.__init__(self, name, role)

    def __str__(self):
        return self.name

### Class that holds information about a team
class Team(CustomRole):
    def __init__(self, name, role):
        CustomRole.__init__(self, name, role)
        self.captains = {}

    def mention(self):
        if self.role:
            return self.role.mention
        elif len(self.captains) == 0:
            return self.name
        else:
            return ', '.join([ c.member.mention for c in self.captains.values() if c.member ])

    ## Override pickle serialization
    def __getstate__(self):
        state = super().__getstate__()
        state.update({
            'captains': self.captains
        })

        return state

### Class that holds information about a team captain
class TeamCaptain:
    def __init__(self, discord, team_name, nickname, group, cup):
        self.discord = discord
        self.team_name = team_name
        self.nickname = nickname
        self.group = group
        self.cup = cup

        # Team handle will be created later, once the captain is actually
        # imported into db
        self.team = None

        # Discord object will in be filled later
        self.member = None

    def __str__(self):
        return '{nick} - {team} - {g} ({id})'\
            .format(nick=self.nickname,
                    team=self.team_name,
                    id=self.discord,
                    g=self.group.name if self.group else '')


    ## Override pickle serialization
    def __getstate__(self):
        state = {
            'discord': self.discord,
            'team_name': self.team_name,
            'nickname': self.nickname,
            'group': self.group,
            'cup': self.cup,
            'team': self.team,
            '_member_id': self.member.id if hasattr(self, 'member') and self.member else self._member_id
        }

        return state

    async def resume(self, server, bot, db):
        if hasattr(self, '_member_id'):
            self.member = discord.utils.get(server.members, id=self._member_id) \
                          if self._member_id else None
