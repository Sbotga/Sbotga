import json, os, time

from twitchio import User
from twitchio.ext.commands import Bot

expiry = 864000  # 10 days
# twitch holds a name for 30 days after change

user_cache_path = "DATA/data/cached_users.json"

if not os.path.exists(user_cache_path):
    user_cache = {}
else:
    with open(user_cache_path, "r") as f:
        user_cache = json.load(f)


async def getch_user_id(bot: Bot, name: str) -> int | None:
    name_lower = name.lower()
    if name_lower in user_cache.keys():
        if (user_cache[name_lower]["last_updated"] + expiry) <= time.time():  # expired
            del user_cache[name_lower]
        else:
            return user_cache[name_lower]["id"]
    try:
        user = (await bot.fetch_users(names=[name]))[0].id
    except:
        return None
    user_cache[name_lower] = {"last_updated": time.time(), "id": user}
    with open(user_cache_path, "w") as f:
        json.dump(user_cache, f, indent=4)
    return user


async def getch_user_name(bot: Bot, id: int) -> str | None:
    for user, data in user_cache.copy().items():
        if id == data["id"]:
            if (data["last_updated"] + expiry) <= time.time():  # expired
                del user_cache[user]
            else:
                return user
    try:
        user = (await bot.fetch_users(ids=[id]))[0]
    except:
        return None
    user_cache[user.name.lower()] = {"last_updated": time.time(), "id": user.id}
    with open(user_cache_path, "w") as f:
        json.dump(user_cache, f, indent=4)
    return user.name.lower()


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
