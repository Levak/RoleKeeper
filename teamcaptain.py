# Class that holds information about a team captain

class TeamCaptain:
    def __init__(self, discord, team, nickname, group):
        self.discord = discord
        self.team = team
        self.nickname = nickname
        self.group = group

    def __str__(self):
        return '{nick} - {team} - Group {g} ({id})'\
            .format(nick=self.nickname, team=self.team, id=self.discord, g=self.group)

