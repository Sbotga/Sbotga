donotload = False

import time

from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from main import TwitchBot, DiscordBot

from DATA.game_api import methods

from DATA.helpers.unblock import to_process_with_timeout

router = APIRouter()

cached = {}


def setup():
    @router.get("/")
    async def main(request: Request, region: str, api_auth: str):
        discord_bot: DiscordBot = request.app.discord_bot
        allowed = ["jiiku831"]
        needed_auths = [discord_bot.CONFIGS.API.guest_auths[value] for value in allowed]

        if api_auth not in needed_auths:
            raise HTTPException(status_code=403, detail="Proper auth pls")

        api = methods.Tools.get_api(region)

        prev_data = cached.get(region, {})

        if prev_data.get("updated", 0) + 300 > time.time():
            return JSONResponse(content=prev_data)

        cur = api.get_current_event()

        if not cur:
            updated = time.time()
            return JSONResponse(
                content={
                    "updated": updated,
                    "next_available_update": updated + 300,
                    "event_id": cur,
                },
                status_code=404,
            )

        updated = time.time()

        def grab_data():
            data = {
                "updated": updated,
                "next_available_update": updated + 300,
                "event_id": cur,
                "top_100": api.get_event_leaderboard(),
                "border": api.get_event_border(),
            }
            return data

        data = await to_process_with_timeout(grab_data)
        cached[region] = data

        return JSONResponse(content=data)
