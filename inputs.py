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
