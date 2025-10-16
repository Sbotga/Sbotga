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
    async def main(request: Request, id: int, region: str, api_auth: str):
        discord_bot: DiscordBot = request.app.discord_bot
        allowed = ["pinkket"]
        needed_auths = [discord_bot.CONFIGS.API.guest_auths[value] for value in allowed]

        if api_auth not in needed_auths:
            raise HTTPException(status_code=403, detail="Proper auth pls")

        api = methods.Tools.get_api(region)

        prev_data = cached.get(region, {})
        cached[region] = prev_data
        prev_user_data = prev_data.get(id, {})

        if prev_user_data.get("updated", 0) + 300 > time.time():
            return JSONResponse(content=prev_user_data)

        cur = api.get_profile(id, forced=True)

        updated = time.time()

        def grab_data():
            data = {
                "updated": updated,
                "next_available_update": updated + 300,
                "user_id": id,
                "profile": cur,
            }
            return data

        data = await to_process_with_timeout(grab_data)
        cached[region][id] = data

        return JSONResponse(content=data)
