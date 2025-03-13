donotload = False

import time

from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from main import TwitchBot, DiscordBot

from DATA.game_api import methods

router = APIRouter()

cached = {}


def setup():
    @router.get("/")
    async def main(request: Request, region: str, api_auth: str):
        discord_bot: DiscordBot = request.app.discord_bot
        allowed = ["sbuga.com"]
        needed_auths = [discord_bot.CONFIGS.API.guest_auths[value] for value in allowed]

        if api_auth not in needed_auths:
            raise HTTPException(status_code=403, detail="Proper auth pls")

        api = methods.Tools.get_api(region)

        prev_data = cached.get(region, {})

        if prev_data.get("updated", 0) + 300 > time.time():
            return JSONResponse(content=prev_data)

        updated = time.time()

        data = api.get_master_data("rankMatchSeasons.json")
        current = None
        for i in range(0, len(data)):
            startAt = data[i]["startAt"]
            endAt = data[i]["closedAt"]
            now = int(round(time.time() * 1000))
            if startAt < now < endAt:
                current = data[i]

        if not current:
            if (
                len(data) == 1
            ):  # 如果只有一个数据，有可能是开第一次排位之前，也有可能是第一次排位之后，排除第一个排位之前的
                if now < data[0]["startAt"]:
                    current = None
                else:
                    current = data[len(data) - 1]
            else:
                current = data[len(data) - 1]

        if not current:
            return JSONResponse(
                content={
                    "updated": updated,
                    "next_available_update": updated + 300,
                    "ranked_season": None,
                },
                status_code=404,
            )

        data = {
            "updated": updated,
            "next_available_update": updated + 300,
            "ranked_season": current,
            "top_100": api.get_ranked_leaderboard(),
        }
        cached[region] = data

        return JSONResponse(content=data)
