from twitchio.ext import commands as twitch_commands

from DATA.helpers.fuzzy_match import (
    fuzzy_match_to_dict_key,
    fuzzy_match_to_dict_key_partial,
)
from DATA.data.pjsk import Song, pjsk_data

# Notice: stripping the invisible character from extensions like 7TV


def CharacterConverter(ctx: twitch_commands.Context, arg: str) -> str | None:
    arg = arg.strip("󠀀")
    chars = {}

    chars.update(
        {
            value["characterVoice"]: ctx.bot.pjsk.characters_game[
                value["characterId"] - 1
            ]
            for value in ctx.bot.pjsk.characters
            if value.get("characterVoice")
        }
    )
    chars.update(
        {
            value["characterVoice"].split(" ")[0]: ctx.bot.pjsk.characters_game[
                value["characterId"] - 1
            ]
            for value in ctx.bot.pjsk.characters
            if value.get("characterVoice")
            and len(value.get("characterVoice", "").split(" ")) == 2
        }
    )
    chars.update(
        {
            value["characterVoice"].split(" ")[1]: ctx.bot.pjsk.characters_game[
                value["characterId"] - 1
            ]
            for value in ctx.bot.pjsk.characters
            if value.get("characterVoice")
            and len(value.get("characterVoice", "").split(" ")) == 2
        }
    )

    chars.update({value["givenName"]: value for value in ctx.bot.pjsk.characters_game})

    for value in ctx.bot.pjsk.characters_game:
        if value.get("firstName"):
            chars[str(value["givenName"]) + str(value["firstName"])] = value
            chars[str(value["firstName"]) + str(value["givenName"])] = value
            chars[str(value["firstName"])] = value

    res = fuzzy_match_to_dict_key(arg, chars, sensitivity=0.7)
    return chars[res] if res else None


def SongConverter(ctx: twitch_commands.Context, arg: str) -> Song | None:
    song: None | Song = None

    if arg == None:
        return song

    arg = arg.strip("󠀀")

    if arg and arg.isdigit() and arg not in ["39"]:
        arg = int(arg)
        song = ctx.bot.pjsk.songs.get(arg)

    if not song:
        arg = str(arg).lower().strip()
        try:
            arg = ctx.bot.pjsk.katsu.romaji(arg).strip("?").lower().strip()
        except:
            pass
        if arg in ctx.bot.pjsk.title_maps:
            song = ctx.bot.pjsk.songs[ctx.bot.pjsk.title_maps[arg]]
        else:
            matched_key = fuzzy_match_to_dict_key(
                arg, ctx.bot.pjsk.title_maps, sensitivity=0.5
            )
            if matched_key is not None:
                song = ctx.bot.pjsk.songs[ctx.bot.pjsk.title_maps[matched_key]]

    if not song:
        return song

    song_id = song["id"]
    difficulties = ctx.bot.pjsk.difficulties[song_id]

    return Song(song, difficulties)


def SongFromPJSK(pjsk: pjsk_data, arg: str, speed: bool = False) -> Song | None:
    song: None | Song = None
    if arg == None:
        return song
    arg = str(arg).strip("󠀀")
    if arg and arg.isdigit() and arg not in ["39"]:
        arg = int(arg)
        song = pjsk.songs.get(arg)

    if not song:
        arg = str(arg).lower().strip()
        if arg in pjsk.title_maps:
            song = pjsk.songs[pjsk.title_maps[arg]]
        if not speed:
            try:
                arg = pjsk.katsu.romaji(arg).strip("?").lower().strip()
            except:
                pass
            if arg in pjsk.title_maps:
                song = pjsk.songs[pjsk.title_maps[arg]]
    if not song:
        matched_key = fuzzy_match_to_dict_key(arg, pjsk.title_maps, sensitivity=0.5)
        if matched_key is not None:
            song = pjsk.songs[pjsk.title_maps[matched_key]]

    if not song:
        return song

    song_id = song["id"]
    difficulties = pjsk.difficulties[song_id]

    return Song(song, difficulties)


def CharFromPJSK(pjsk: pjsk_data, arg: str) -> dict | None:
    chars = {}

    chars.update(
        {
            value["characterVoice"]: pjsk.characters_game[value["characterId"] - 1]
            for value in pjsk.characters
            if value.get("characterVoice")
        }
    )
    chars.update(
        {
            value["characterVoice"].split(" ")[0]: pjsk.characters_game[
                value["characterId"] - 1
            ]
            for value in pjsk.characters
            if value.get("characterVoice")
            and len(value.get("characterVoice", "").split(" ")) == 2
        }
    )
    chars.update(
        {
            value["characterVoice"].split(" ")[1]: pjsk.characters_game[
                value["characterId"] - 1
            ]
            for value in pjsk.characters
            if value.get("characterVoice")
            and len(value.get("characterVoice", "").split(" ")) == 2
        }
    )

    chars.update({value["givenName"]: value for value in pjsk.characters_game})

    for value in pjsk.characters_game:
        if value.get("firstName"):
            chars[str(value["givenName"]) + str(value["firstName"])] = value
            chars[str(value["firstName"]) + str(value["givenName"])] = value
            chars[str(value["firstName"])] = value

    res = fuzzy_match_to_dict_key(arg, chars, sensitivity=0.6)
    return chars[res] if res else res


def DiffFromPJSK(arg: str) -> str | None:
    if arg == None:
        return None
    diffs = {
        "append": "append",
        "master": "master",
        "expert": "expert",
        "hard": "hard",
        "normal": "normal",
        "easy": "easy",
        "apd": "append",
        "mas": "master",
        "exp": "expert",
        "ex": "expert",
        "norm": "normal",
        "ez": "easy",
    }
    arg = str(arg).lower().strip().strip("󠀀")
    try:
        return diffs[arg]
    except:
        return None


def EventFromPJSK(pjsk: pjsk_data, arg: str) -> dict | None:
    res = fuzzy_match_to_dict_key_partial(arg, pjsk.all_events_raw, sensitivity=0.5)
    return pjsk.all_events_raw[res] if res else res


def Integer(ctx: twitch_commands.Context, arg: str) -> int | None:
    if arg == None:
        return None
    arg = str(arg).lower().strip().strip("󠀀")
    try:
        return int(arg)
    except:
        return None


def PJSKDifficulty(ctx: twitch_commands.Context, arg: str) -> str | None:
    if arg == None:
        return None
    diffs = {
        "append": "append",
        "master": "master",
        "expert": "expert",
        "hard": "hard",
        "normal": "normal",
        "easy": "easy",
        "apd": "append",
        "mas": "master",
        "exp": "expert",
        "ex": "expert",
        "norm": "normal",
        "ez": "easy",
    }
    arg = str(arg).lower().strip().strip("󠀀")
    try:
        return diffs[arg]
    except:
        return None
