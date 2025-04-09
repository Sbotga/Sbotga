donotload = False

from fastapi import APIRouter, Request, Response, HTTPException
from main import TwitchBot, DiscordBot

from DATA.helpers.converters import SongConverter, DiffFromPJSK

router = APIRouter()

from fastapi.responses import JSONResponse, PlainTextResponse
from DATA.game_api.methods import Tools


def setup():
    @router.get("/")
    async def main(request: Request, song: str):
        class FakeCtx:
            def __init__(self):
                self.bot = request.app.twitch_bot  # Any bot works here though

        song_obj = SongConverter(FakeCtx(), song)

        if song_obj:
            return {
                "jacket_url": song_obj.jacket_url,
                "difficulties": song_obj.difficulties,
                "id": song_obj.id,
                "name": song_obj.data["title"],
                "jp_exclusive": song_obj.jp_only,
            }
        else:
            return JSONResponse(content={"error": "Song not found"}, status_code=404)

    @router.get("/chart")
    async def main(request: Request, song: str, difficulty: str):
        class FakeCtx:
            def __init__(self):
                self.bot = request.app.twitch_bot  # Any bot works here though

        difficulty = DiffFromPJSK(difficulty)
        song_obj = SongConverter(FakeCtx(), song)

        if Tools.isleak(song_obj.id):
            pass
        elif song_obj and difficulty:
            try:
                chart_path = Tools.get_music_chart(song_obj.id, difficulty)
                with open(chart_path, "r") as f:
                    chart_contents = f.read()
                return PlainTextResponse(content=f)
            except:
                pass

        return JSONResponse(
            content={"error": "Song and difficulty not found"}, status_code=404
        )
