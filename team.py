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

### Class that holds information about a role and a custom name
class CustomRole:
    def __init__(self, name, role):
        self.name = name
        self.role = role

    def __str__(self):
        return '{name} ({role})'\
            .format(name=self.name, role=str(self.role))

### Class that holds information about a cup
class Cup(CustomRole):
    def __init__(self, name, role, maps):
        CustomRole.__init__(self, name, role)
        self.maps = maps

### Class that holds information about a group
class Group(CustomRole):
    def __init__(self, id, name, role):
        self.id = id
        CustomRole.__init__(self, name, role)

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

