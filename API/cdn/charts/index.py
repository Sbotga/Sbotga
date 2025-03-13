donotload = False

from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import FileResponse
from main import TwitchBot, DiscordBot

from DATA.game_api import methods

router = APIRouter()


def setup():
    @router.get("/")
    async def main(request: Request, id: int, difficulty: str):
        twitch_bot: TwitchBot = request.app.twitch_bot
        discord_bot: DiscordBot = request.app.discord_bot

        difficulty = difficulty.lower().strip()

        try:

            assert difficulty in [
                "easy",
                "normal",
                "hard",
                "expert",
                "master",
                "append",
            ]

            if difficulty == "append":
                region = methods.Tools.get_music_append_regions(id)
            else:
                region = [methods.Tools.get_music_region(id)]
            try:
                region = region[0]
                chart = await methods.Tools.get_chart(difficulty, id, region)

                return FileResponse(chart)
            except IndexError as e:
                return HTTPException(404)

        except:
            return HTTPException(404)
