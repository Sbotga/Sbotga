donotload = False

import time

from fastapi import APIRouter, Request, Response, HTTPException
from main import TwitchBot, DiscordBot

from DATA.game_api import methods

from sssekai.crypto.APIManager import decrypt, encrypt, SEKAI_APIMANAGER_KEYSETS
from msgpack import unpackb, packb

router = APIRouter()


def setup():
    @router.get("/")
    async def main(request: Request, user: int, region: str, api_auth: str):
        discord_bot: DiscordBot = request.app.discord_bot
        needed_auth = discord_bot.CONFIGS.API.protected_auth

        if api_auth != needed_auth:
            raise HTTPException(status_code=403, detail="Proper auth pls")

        ban_content = {"errorCode": "login_ban", "errorMessage": "", "httpStatus": 403}

        data = packb(ban_content)
        data_r = encrypt(data, SEKAI_APIMANAGER_KEYSETS[region])

        api = methods.Tools.get_api(region)
        data = api.attempt_get_user_data(user)
        time_left = None
        if data:
            current_time = time.time()
            cooldown_end = (data["now"] / 1000) + 300  # 5 minutes
            if cooldown_end > current_time:
                time_left = cooldown_end - time.time()

        if not time_left:
            return Response(status_code=200, content=data_r)

        return Response(
            status_code=503, content=data_r, headers={"Retry-After": str(time_left)}
        )

    @router.post("/data")
    async def data_update(request: Request, user: int, region: str, api_auth: str):
        discord_bot: DiscordBot = request.app.discord_bot
        needed_auth = discord_bot.CONFIGS.API.protected_auth

        data = await request.body()
        if api_auth != needed_auth:
            raise HTTPException(status_code=403, detail="Proper auth pls")

        api = methods.Tools.get_api(region)
        api.save_user_data_raw(data)

        print(f"User data updated: {user}")

        return Response(status_code=201)

    @router.post("/gameversion")
    async def data_update(request: Request, region: str, api_auth: str):
        discord_bot: DiscordBot = request.app.discord_bot
        needed_auth = discord_bot.CONFIGS.API.protected_auth

        data = await request.body()
        if api_auth != needed_auth:
            raise HTTPException(status_code=403, detail="Proper auth pls")

        api = methods.Tools.get_api(region)
        data = packb(api._update_gameversion_data())
        data_r = encrypt(data, SEKAI_APIMANAGER_KEYSETS[region])

        return Response(status_code=200, content=data_r)
