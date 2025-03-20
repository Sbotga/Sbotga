donotload = False

from fastapi import APIRouter, Request, Response, HTTPException
from main import TwitchBot, DiscordBot

from DATA.helpers.converters import SongConverter

router = APIRouter()

from fastapi.responses import JSONResponse


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
