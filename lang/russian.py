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
Привет, {m_teamA} и {m_teamB}!

Этот текстовый канал доступен только для капитанов команд и судей турнира. Он предназначен для обмена информации по матчу между {teamA} и {teamB}.

Бан карты происходит посредством использования команды `!ban` поочередно, до тех пор пока не останется только одна. Команда, которая банит карту последней, выбирает за какую сторону начнёт играть используя `!side xxxx` (attack или defend), где

attack, blackwood - атака
defend, warface - защита.

Например, Команда А вводит `-piramida` для бана карты "Пирамида", Команда Б набирает `-d17`, исключая карту Д-17 и так далее, до тех пор, пока не останется только одна карта. Затем Команда А выбирает сторону используя `!side attack`.
{match_result_upload}
""",

    'bo2_title': 'BEST OF 2',
    'bo2_welcome_message': """
Привет, {m_teamA} и {m_teamB}!

Этот текстовый канал доступен только для капитанов команд и судей турнира. Он предназначен для обмена информации по матчу между {teamA} и {teamB}.

Выбор или бан карты производится путем ввода команд `!pick`, `!ban` и `!side` в порядке, описанном ниже:
Например, команда А вводит `-piramida` для бана карты "Пирамида", Команда Б набирает `-d17`, исключая карту Д-17. Затем по очереди команды выбирают карту используя `+Пунктназвачения` (для выбора карты "Пункт Назвачения"). Затем Команда А выбирает сторону на карте, выбранной противниками, используя `!side xxxx` (attack или defend), где

attack, blackwood - атака
defend, warface - защита.

Команда Б делает то же самое для карты, выбранной командой А.
{match_result_upload}
""",

    'bo3_title': 'BEST OF 3',
    'bo3_welcome_message': """
Привет, {m_teamA} и {m_teamB}!

Этот текстовый канал доступен только для капитанов команд и судей турнира. Он предназначен для обмена информации по матчу между {teamA} и {teamB}.

Выбор или бан карты производится путем ввода команд `!pick`, `!ban` и `!side` в порядке, описанном ниже:
Например, команда А вводит `-piramida` для бана карты "Пирамида", Команда Б набирает `-d17`, исключая карту Д-17. Затем по очереди команды выбирают карту используя `+Пунктназвачения` и так далее, до тех пор, пока не останется только одна карта. Последняя оставшаяся карта станет решающей в случае ничьей по результатам первых двух карт.

Команда А выбирает стороны на карте выбранной Командой Б используя `!side xxxx` (attack или defend), где:
attack, blackwood - атака
defend, warface - защита.

Затем Команда Б выбирает сторону на карте выбранной Командой А аналогичным способом. Сторону на последней решающей карте выбирает Команда А.
{match_result_upload}
""",

    'bo5_title': 'BEST OF 5',
    'bo5_welcome_message': """
Привет, {m_teamA} и {m_teamB}!

Этот текстовый канал доступен только для капитанов команд и судей турнира. Он предназначен для обмена информации по матчу между {teamA} и {teamB}.

Выбор или бан карты производится путем ввода команд `!pick`, `!ban` и `!side` в порядке, описанном ниже:
Например, команда А вводит `-piramida` для бана карты "Пирамида", Команда Б набирает `-d17`, исключая карту Д-17. Затем по очереди команды выбирают карту используя `+Пунктназвачения` и так далее, до тех пор, пока не останется только одна карта. Последняя оставшаяся карта станет решающей в случае ничьей по результатам первых двух карт.

Команда А выбирает стороны на карте выбранной Командой Б используя `!side xxxx` (attack или defend), где:
attack, blackwood - атака
defend, warface - защита.

Затем Команда Б выбирает сторону на карте выбранной Командой А аналогичным способом. Сторону на последней решающей карте выбирает Команда А.
{match_result_upload}
""",

    'match_result_upload': """
Чтобы загрузить итоги матча, необходимо перейти по ссылке ниже, нажать на "Результаты" и ввести данные:
{url}
- Best-of-1: итоги игры (например, 11-3)
- Остальные форматы: количество выигранных матчей (например, 2 - 1)
- Если противник не явился на матч, оставьте поля пустыми и поставьте соответствующую галочку в "Противник не появился" в дополнительных полях.
- Если при заполнении данных вы допустили ошибку, необходимо связаться с судьей.
""",

    'match_pick_ban_over': 'Выбор и бан карт завершены.',
    'match_not_your_turn': 'Сейчас не твоя очередь {}.',
    'match_invalid_turn': 'Сейчас очередь не {}, а **{}**.',
    'match_invalid_side': 'Некорректная сторона.',
    'match_invalid_map': 'Что-то пошло не так,  вероятно название карты введено некорректно.',
    'match_map_already_banned': 'Эта карта уже забанена, выбери другую.',
    'match_map_already_picked': 'Эта карта уже выбрана, выбери другую.',
    'match_pick_ban_title': 'Выбор и бан карт',
    'match_state_title': 'Текущий статус',
    'match_turn_span': 'Твоя очередь',
    'match_use_span': 'Использовать',
    'match_ban_sequence_finished': 'Бан карт завершен!',
    'match_sequence_finished': 'Выбор и бан карт завершены!',
    'match_map': 'Карта',
    'match_tiebreaker_map': 'Решающая карта',
    'match_good_luck': 'Удачи!',
    'match_warning': 'Не забудьте сделать скриншот итогов матча!',
}
