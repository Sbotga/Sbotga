from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import FileResponse
import os
from main import TwitchBot, DiscordBot

router = APIRouter()

# Path to the assets directory
ASSETS_DIR = "DATA/data/ASSETS/"


def setup():

    # Route for returning 'rodinntlg_eb.ttf'
    @router.get("/rodinntlg_eb")
    async def get_rodinntlg_eb():
        font_path = os.path.join(ASSETS_DIR, "rodinntlg_eb.otf")
        if not os.path.exists(font_path):
            raise HTTPException(status_code=404, detail="Font file not found")
        return FileResponse(font_path)

    # Route for returning 'rodinntlg_m.ttf'
    @router.get("/rodinntlg_m")
    async def get_rodinntlg_m():
        font_path = os.path.join(ASSETS_DIR, "rodinntlg_m.otf")
        if not os.path.exists(font_path):
            raise HTTPException(status_code=404, detail="Font file not found")
        return FileResponse(font_path)
