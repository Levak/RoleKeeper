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

translation = {
    'bo1_title': 'BEST OF 1',
    'bo1_welcome_message': """
Welcome {m_teamA} and {m_teamB}!

This text channel will be used by the judge and team captains to exchange anything about the match between teams {teamA} and {teamB}.

The ban sequence is made using the `!ban` command team by team until one remains. Last team to ban also needs to chose the side they will play on using `!side xxxx` (attack or defend).

For instance, team A types `!ban Pyramid` which will then ban the map _Pyramid_ from the match, team B types `!ban d17` which will ban the map D-17, and so on, until only one map remains. team A then picks the side using `!side attack`.
{match_result_upload}
""",

    'bo2_title': 'BEST OF 2',
    'bo2_welcome_message': """
Welcome {m_teamA} and {m_teamB}!

This text channel will be used by the judge and team captains to exchange anything about the match between teams {teamA} and {teamB}.

The pick&ban sequence is made using the `!pick`, `!ban` and `!side` commands one by one using the order defined below.

For instance, team A types `!ban Yard` which will then ban the map _Yard_ from the match, team B types `!ban d17` which will ban the map D-17. team A would then type `!pick Destination`, picking the first map and so on. Team B then picks the side using `!side attack`.
{match_result_upload}
""",

    'bo3_title': 'BEST OF 3',
    'bo3_welcome_message': """
Welcome {m_teamA} and {m_teamB}!

This text channel will be used by the judge and team captains to exchange anything about the match between teams {teamA} and {teamB}.

The pick&ban sequence is made using the `!pick`, `!ban` and `!side` commands one by one using the order defined below.

For instance, team A types `!ban Yard` which will then ban the map _Yard_ from the match, team B types `!ban d17` which will ban the map D-17. team A would then type `!pick Destination`, picking the first map and so on, until only one map remains, which will be the tie-breaker map. Team B then picks the side using `!side attack`.
{match_result_upload}
""",

    'match_result_upload': """
To upload the match results, open the link below, click "Results" and enter the scores:
{url}
- For a best-of-1, enter the won round count (e.g. 11-3);
- For other modes, enter the number of won matches (e.g. 2-1);
- If your enemy did not appear, leave the fields blank and select "Enemy did not appear" in the "Additional fields" box;
- If you made a mistake when entering the results, contact a referee.
""",

    'match_pick_ban_over': 'Pick & Ban sequence is over!',
    'match_not_your_turn': 'Not your turn to {}!',
    'match_invalid_turn': 'Not a {} turn but a **{}** one!',
    'match_invalid_side': 'What side is that?',
    'match_invalid_map': 'That map is not in the map poll, or I didn\'t understand you',
    'match_map_already_banned': 'That map has already been banned, please choose another one',
    'match_map_already_picked': 'That map has already been picked, please choose another one',
    'match_pick_ban_title': 'Pick & ban sequence',
    'match_state_title': 'Current sequence status',
    'match_turn_span': 'Your turn',
    'match_use_span': 'Use',
    'match_ban_sequence_finished': 'Ban sequence finished!',
    'match_sequence_finished': 'Pick & Ban sequence finished!',
    'match_map': 'Map',
    'match_tiebreaker_map': 'Tie-breaker map',
    'match_good_luck': 'glhf!',
    'match_warning': 'And don\'t forget to screenshot all match results!'
}
