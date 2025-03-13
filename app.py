import os, importlib, asyncio, base64, json

import aiohttp

from typing import Dict, List

from DATA.CONFIGS import CONFIGS
from main import TwitchBot, DiscordBot

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

debug = False

imgs_json_path = "DATA/data/ASSETS/imgs.json"

if not os.path.exists(imgs_json_path):
    image_data = {}
else:
    with open(imgs_json_path, "r") as f:
        image_data = json.load(f)


class PJSKFastAPI(FastAPI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.url = "pjsk.econuker.xyz"
        self.protocol = "https"
        self.ws_protocol = "wss"
        self.debug = debug
        if debug:
            self.url = "localhost:3939"
            self.protocol = "http"
            self.ws_protocol = "ws"
        self.twitch_bot: TwitchBot = None
        self.discord_bot: DiscordBot = None
        self.active_connections: Dict[str, Dict[int, List[WebSocket]]] = {}

        async def send_image_update(
            bot: TwitchBot, user_id: str, num: int, action: str, url: str = None
        ):
            """
            Send an update to a specific user's image source.
            """
            old_url = url
            active_connections = self.active_connections
            user_key = f"user_{user_id}"
            message = {"action": action}
            if action == "update":
                message["url"] = url
                if url and url.startswith("http"):
                    if url in image_data:
                        base64_image = image_data[url]
                    else:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(url) as response:
                                if response.status != 200:
                                    raise TypeError(
                                        f"Could not fetch image. {await response.text()}"
                                    )
                                base64_image = base64.b64encode(
                                    await response.read()
                                ).decode("utf-8")

                                # Save to the file
                                image_data[url] = base64_image
                                with open(imgs_json_path, "w") as f:
                                    json.dump(image_data, f, indent=4)

                    message["url"] = f"data:image/png;base64,{base64_image}"
                    url = f"data:image/png;base64,{base64_image}"
                await bot.user_data.set_display(
                    user_id, num, {"url": old_url or url, "hidden": False}
                )
            elif action == "hide":
                await bot.user_data.set_display(
                    user_id,
                    num,
                    {
                        "url": await bot.user_data.get_display(user_id, num)["url"],
                        "hidden": True,
                    },
                )
            elif action == "show":
                url = await bot.user_data.get_display(user_id, num)["url"]
                await bot.user_data.set_display(
                    user_id, num, {"url": old_url or url, "hidden": False}
                )
                message["url"] = url

            if (
                user_key in active_connections
                and num in active_connections[user_key].copy()
            ):
                websockets = active_connections[user_key][num]
                for websocket in websockets.copy():
                    try:
                        await websocket.send_json(message)
                    except:
                        try:
                            active_connections[user_key][num].remove(websocket)
                        except ValueError:
                            pass

        self.send_image_update = send_image_update

    def update_bot_functions(self):
        self.twitch_bot.send_image_update = self.send_image_update
        self.twitch_bot.active_connections = self.active_connections


app = PJSKFastAPI(debug=debug)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# app.mount("/static", StaticFiles(directory="static"), name="static")
# templates = Jinja2Templates(directory="templates")


def loadRoutes(folder, main, cleanup: bool = True):
    global app
    """Load Routes from the specified directory."""
    for root, dirs, files in os.walk(folder, topdown=False):
        for file in files:
            if not "__pycache__" in root and os.path.join(root, file).endswith(".py"):
                route_name: str = (
                    os.path.join(root, file)
                    .removesuffix(".py")
                    .replace("\\", "/")
                    .replace("/", ".")
                )
                route_version = route_name.split(".")[0]
                if route_name.endswith(".index"):
                    route = importlib.import_module(route_name)
                    if hasattr(route, "donotload") and route.donotload:
                        continue
                    route_name = route_name.split(".")
                    del route_name[-1]
                    del route_name[0]
                    route_name = ".".join(route_name)
                    route.router.prefix = "/" + route_name.replace(".", "/")
                    route.router.tags = (
                        route.router.tags + [route_version]
                        if isinstance(route.router.tags, list)
                        else [route_version]
                    )
                    # route.router.name = route_name
                    route.setup()
                    app.include_router(route.router)
                    main.twitch_bot.print(
                        f"{main.twitch_bot.COLORS.cog_logs}[API] {main.twitch_bot.COLORS.normal_message}Loaded Route {main.twitch_bot.COLORS.item_name}{(folder + '.' + route_name.strip('.'))}"
                    )
                else:
                    route = importlib.import_module(route_name)
                    if hasattr(route, "donotload") and route.donotload:
                        continue
                    route_name = route_name.split(".")
                    del route_name[0]
                    route_name = ".".join(route_name)
                    route.router.prefix = "/" + route_name.replace(".", "/")
                    route.router.tags = (
                        route.router.tags + [route_version]
                        if isinstance(route.router.tags, list)
                        else [route_version]
                    )
                    # route.router.name = route_name
                    route.setup()
                    app.include_router(route.router)
                    main.twitch_bot.print(
                        f"{main.twitch_bot.COLORS.cog_logs}[API] {main.twitch_bot.COLORS.normal_message}Loaded Route {main.twitch_bot.COLORS.item_name}{folder + '.' + route_name}"
                    )


async def startup_event():
    import main

    app.twitch_bot = main.twitch_bot
    app.discord_bot = main.discord_bot
    app.update_bot_functions()
    folder = "API"
    if len(os.listdir(folder)) == 0:
        app.twitch_bot.warn("No routes loaded.")
    else:
        loadRoutes(folder, main)
        app.twitch_bot.success("Routes loaded!")


app.add_event_handler("startup", startup_event)

# uvicorn.run("app:app", port=CONFIGS.API.port, host="0.0.0.0")


async def start_fastapi():
    config = uvicorn.Config("app:app", host="0.0.0.0", port=CONFIGS.API.port)
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    raise SystemExit("Please run main.py")
