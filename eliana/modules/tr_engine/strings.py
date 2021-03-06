import yaml
from codecs import encode, decode
from requests import get

from eliana import LOGGER
from eliana.modules.sql.locales_sql import prev_locale

LANGUAGES = ['en', 'ar']
strings = {}
for i in LANGUAGES:
    strings[i] = yaml.full_load(open("eliana/modules/tr_engine/languages/" + i + ".yml", "r"))

def tld(chat_id, t, show_none=True):
    LANGUAGE = prev_locale(chat_id)

    if LANGUAGE:
        LOCALE = LANGUAGE.locale_name
        if LOCALE in ('en') and t in strings['en']:
            result = decode(
                encode(strings['en'][t], 'latin-1', 'backslashreplace'),
                'unicode-escape')
            return result
        elif LOCALE in ('ar') and t in strings['ar']:
            result = decode(
                encode(strings['ar'][t], 'latin-1', 'backslashreplace'),
                'unicode-escape')
            return result
            
    if t in strings['en']:
        result = decode(
            encode(strings['en'][t], 'latin-1', 'backslashreplace'),
            'unicode-escape')
        return result

    err = f"No string found for {t}.\nReport it to @KassemSYR."
    LOGGER.warning(err)
    return err


def tld_list(chat_id, t):
    LANGUAGE = prev_locale(chat_id)

    if LANGUAGE:
        LOCALE = LANGUAGE.locale_name
        if LOCALE in ('en') and t in strings['en']:
            return strings['en'][t]
        elif LOCALE in ('ar') and t in strings['es']:
            return strings['ar'][t]            

    if t in strings['en']:
        return strings['en'][t]

    LOGGER.warning(f"#NOSTR No string found for {t}.")
    return f"No string found for {t}.\nReport it in @HarukaAyaGroup."


# def tld_help(chat_id, t):
#     LANGUAGE = prev_locale(chat_id)
#     print("tld_help ", chat_id, t)
#     if LANGUAGE:
#         LOCALE = LANGUAGE.locale_name

#         t = t + "_help"

#         print("Test2", t)

#         if LOCALE in ('ru') and t in RussianStrings:
#             return RussianStrings[t]
#         elif LOCALE in ('ua') and t in UkrainianStrings:
#             return UkrainianStrings[t]
#         elif LOCALE in ('es') and t in SpanishStrings:
#             return SpanishStrings[t]
#         elif LOCALE in ('tr') and t in TurkishStrings:
#             return TurkishStrings[t]
#         elif LOCALE in ('id') and t in IndonesianStrings:
#             return IndonesianStrings[t]
#         else:
#             return False
#     else:
#         return False
