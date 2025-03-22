donotload = False

from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import FileResponse
from main import TwitchBot, DiscordBot

from DATA.game_api import methods
from DATA.helpers import pjsk_chart
from DATA.helpers.unblock import to_process_with_timeout

router = APIRouter()


def setup():
    @router.get("/")
    async def main(request: Request, id: int, difficulty: str, mirror: int = 0):
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

                if mirror == 1:
                    chart = await to_process_with_timeout(pjsk_chart.mirror, chart)

                return FileResponse(chart)
            except IndexError as e:
                return HTTPException(404)

        except:
            return HTTPException(404)
