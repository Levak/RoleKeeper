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

import re
import transliterate

def sanitize_input(input):
    unsafe_chars = re.compile(r'[^a-zA-Z0-9]')
    return unsafe_chars.sub('', input.lower())

def translit_input(input):
    try:
        return transliterate.translit(input, reversed=True)
    except:
        return input

## When ` in input, use ``, count = 1, mod 2 = 1
## When `` in input, use `, count = 2, mod 2 = 0
def md_inline_code(input):
    if input.count('`') % 2 == 0:
        return '`{}`'.format(input)
    else:
        return '``{}``'.format(input)

def md_bold(input):
    return '**{}**'.format(input.replace('_', '\\_'))

def md_normal(input):
    return '{}'.format(input.replace('_', '\\_'))

def md_italic(input):
    return '_{}_'.format(input.replace('_', '\\_'))
