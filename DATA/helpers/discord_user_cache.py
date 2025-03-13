import json, os, time

from discord import User
from discord.ext.commands import Bot

expiry = 86400  # 1 day
# discord is weird and can hold your username anywhere from 24h - idk
# so shrug?

user_cache_path = "DATA/data/cached_discord_users.json"

if not os.path.exists(user_cache_path):
    user_cache = {}
else:
    with open(user_cache_path, "r") as f:
        user_cache = json.load(f)


async def getch_user_name(
    bot: Bot, id: int, return_old_data: bool = False
) -> str | None:
    for user, data in user_cache.copy().items():
        if id == data["id"]:
            if (data["last_updated"] + expiry) <= time.time():  # expired
                if return_old_data:  # Don't care if it's expired
                    return user
                del user_cache[user]
            else:
                return user
    try:
        user = bot.get_user(id) or (await bot.fetch_user(id))
    except:
        return None
    user_cache[user.name.lower()] = {"last_updated": time.time(), "id": user.id}
    with open(user_cache_path, "w") as f:
        json.dump(user_cache, f, indent=4)
    return user.name.lower()


def save_user_name(id: int, name: str) -> str | None:
    name_lower = name.lower()
    if name_lower in user_cache.keys():
        if (user_cache[name_lower]["last_updated"] + expiry) <= time.time():  # expired
            del user_cache[name.lower()]
        else:
            return
    user_cache[name.lower()] = {"last_updated": time.time(), "id": id}
    with open(user_cache_path, "w") as f:
        json.dump(user_cache, f, indent=4)


def get_user_name_from_id(id: int) -> str | None:
    for user, data in user_cache.copy().items():
        if id == data["id"]:
            if (data["last_updated"] + expiry) <= time.time():  # expired
                return None
            else:
                return user
    return None


def get_user_id_from_name(name: str) -> int | None:
    name_lower = name.lower()
    if name_lower in user_cache.keys():
        if (user_cache[name_lower]["last_updated"] + expiry) <= time.time():  # expired
            return None
        else:
            return user_cache[name_lower]["id"]
    return None
