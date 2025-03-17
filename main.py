import time, asyncio, os, glob, re, shutil
from collections import deque

from typing import Dict, List, Union, Any

# TODO: switch all json to orjson

import asyncpg

from colorama import init as coloramainit

coloramainit(autoreset=True)

from twitchio.ext import commands as twitch_commands
from discord.ext import commands as discord_commands
import twitchio
import discord
from discord import app_commands

from fastapi import WebSocket

from COGS.discord_translations import SbotgaTranslator

from DATA.helpers.logging import LOGGING
from DATA.helpers.user_cache import getch_user_id, getch_user_name
from DATA.helpers.discord_autocompletes import autocompletes
from DATA.helpers import embeds

from DATA.data.pjsk import pjsk, pjsk_data

from DATA.CONFIGS import CONFIGS
from DATA.user_data import user_data

twitch_token = CONFIGS.tokens["twitch"]
discord_token = CONFIGS.tokens["discord"]


class TwitchBot(twitch_commands.Bot):
    def __init__(self, *args, **kwargs):
        self.__init_args = args
        self.__init_kwargs = kwargs

        self.CONFIGS = CONFIGS
        self.COLORS = LOGGING.COLORS
        self.pjsk = pjsk

        self.print = LOGGING.print
        self.info = LOGGING.infoprint
        self.error = LOGGING.errorprint
        self.warn = LOGGING.warnprint
        self.success = LOGGING.successprint
        self.traceback = LOGGING.tracebackprint

        self.task_running = False
        self.send_image_update = lambda *args: None
        self.user_data = user_data

        self.active_connections: Dict[str, Dict[int, List[WebSocket]]] = {}

    async def run_checks(
        self,
        ctx: twitch_commands.Context,
        activated_check: bool = False,
        game_check: bool = False,
        permission_level: int = 0,
    ):  # TODO: developer bypass
        """
        0 - all

        1 - subscribed

        2 - vip

        3 - mod

        4 - broadcaster

        5 - developer (me)
        """
        val = True
        if activated_check:
            if (
                str((await getch_user_id(self, ctx.channel.name)))
                in self.user_data.users_using
            ):
                pass
            else:
                val = False
        if game_check:
            streams = await self.fetch_streams(
                user_ids=[(await getch_user_id(self, ctx.channel.name))], type="live"
            )
            if len(streams) > 0:
                if streams[0].game_id != "279014883":
                    await self.command_ran(ctx, success=False)
                    await ctx.reply(
                        "Only available when the streamed game is Hatsune Miku: Colorful Stage!"
                    )
                    val = False
            else:
                pass
        if permission_level == 1:
            # subscribed
            if not (
                ctx.author.is_subscriber
                or ctx.author.is_vip
                or ctx.author.is_mod
                or ctx.author.is_broadcaster
            ):
                val = False
                await ctx.reply("You must be a subscriber!")
                await self.command_ran(ctx, success=False)
        elif permission_level == 2:
            # vip
            if not (
                ctx.author.is_vip or ctx.author.is_mod or ctx.author.is_broadcaster
            ):
                val = False
                await self.command_ran(ctx, success=False)
                await ctx.reply("You must be a VIP!")
        elif permission_level == 3:
            # mod
            if not (ctx.author.is_mod or ctx.author.is_broadcaster):
                val = False
                await self.command_ran(ctx, success=False)
                await ctx.reply("You must be a moderator!")
        elif permission_level == 4:
            # broadcaster
            if not (ctx.author.is_broadcaster):
                val = False
                await self.command_ran(ctx, success=False)
                await ctx.reply(f"You must be {ctx.channel.name}!")
        elif permission_level == 5:
            # developer
            if ctx.author.id != "673590022":
                val = False
        return val

    async def bot_tasks(self):
        while True:
            # TODO remove
            break
            # every 10 min, send reminder
            if (time.time() - user_data.last_reminder) > 600:
                user_ids = [int(uid) for uid in user_data.using_reminders]
                strims = await self.fetch_streams(
                    user_ids=user_ids, game_ids=[279014883], type="live"
                )
                for strim in strims:
                    print(strim)
                    for channel in self.connected_channels:
                        if channel.name == strim.user.name:
                            await channel.send("Remember to stay hydrated and stretch!")
                user_data.update_last_reminder()

            await asyncio.sleep(5)

    async def command_ran(
        self, ctx: twitch_commands.Context, success: bool = None, msg: bool = False
    ):
        cmdname = (
            ctx.command.full_name
            if ctx.command
            else ctx.message.content.strip().removeprefix("!").split()[0]
        )
        failsuccess = ""
        if success == False:
            failsuccess = f"{self.COLORS.error_logs}[FAIL] {self.COLORS.reset}"
        elif success == True:
            failsuccess = f"{self.COLORS.success_logs}[SUCCESS] {self.COLORS.reset}"
        LOGGING.print(
            failsuccess
            + f"{self.COLORS.command_logs}[COMMAND] {self.COLORS.user_name}{ctx.author.name}{self.COLORS.normal_message} ran command {self.COLORS.item_name}{cmdname}{self.COLORS.normal_message} on the channel {self.COLORS.item_name}{ctx.channel.name}{self.COLORS.normal_message}. Full command: {self.COLORS.item_name}{ctx.message.content}"
        )

    async def event_ready(self):
        print(f"Logged in as | {self.nick}")
        print(f"User id is | {self.user_id}")
        print(
            f"Connected to {', '.join([ch.name for ch in self.connected_channels]) or 'None'}"
        )
        cogspath = os.path.join("COGS/twitch", "")
        cogspathpy = [
            os.path.basename(f) for f in glob.glob(os.path.join(cogspath, "*.py"))
        ]
        cogs = [f"{cogspath[:-1]}." + os.path.splitext(f)[0] for f in cogspathpy]
        for cog in cogs:
            try:
                self.load_module(cog.replace("/", "."))
                self.print(
                    f"{self.COLORS.cog_logs}[COGS] {self.COLORS.normal_message}Loaded cog {self.COLORS.item_name}{cog}"
                )
            except twitch_commands.errors.InvalidCogMethod:
                pass
            except Exception as e:
                self.traceback(e)
        if self.task_running == False:
            asyncio.create_task(self.bot_tasks())
        to_join_users = []
        if len(self.user_data.to_join_ids) > 0:
            print(
                f"Fetching new channels to join {', '.join([str(id) for id in self.user_data.to_join_ids]) or 'None'}"
            )
            to_join = self.user_data.to_join_ids.copy()
            self.user_data.to_join_ids = []
            # (await bot.fetch_users(ids=[id]))
            for id in to_join:
                ua = await getch_user_name(self, id)
                if ua:
                    to_join_users.append(ua)
        print(f"Attempting to connect to {', '.join(to_join_users) or 'None'}")
        await self.join_channels(to_join_users)

    async def event_command_error(
        self, context: twitch_commands.Context, error: Exception
    ) -> None:
        if isinstance(error, twitch_commands.CommandNotFound):
            pass
        else:
            raise error

    async def start(self, token: str):
        super().__init__(token=token, *self.__init_args, **self.__init_kwargs)
        return await super().start()

    # @twitch_commands.command()
    # async def randompjskraid(self, ctx: twitch_commands.Context, filters: str = ""):
    #     if str((await getch_user_id(self, ctx.channel.name))) in user_data.users_using:
    #         pass
    #     else:
    #         return
    #     req_langs = ["en"]
    #     if filters == "all":
    #         req_langs = None
    #     if not ctx.author.is_broadcaster:
    #         return await ctx.reply(f"Only broadcaster can run this!")

    #     channel = await ctx.channel.user()
    #     target_streams = (await self.fetch_streams(game_ids=[279014883], languages=req_langs, type="live"))
    #     stream = (await self.fetch_streams(user_ids=[channel.id]))

    #     random.shuffle(target_streams)
    #     for stream in target_streams:
    #         try:
    #             await channel.start_raid(token=twitch_token, to_broadcaster_id=stream.user.id)
    #             return await ctx.reply(f"Raiding {stream.user.name}!")
    #         except twitchio.errors.Unauthorized as e:
    #             print(e)
    #             return await ctx.reply(f"Couldn't start raid: Please make me an editor and mod! (https://dashboard.twitch.tv/u/{channel.name}/community/roles)")
    #         except twitchio.errors.AuthenticationError as e:
    #             print(e)
    #             return await ctx.reply(f"Couldn't start raid: Please make me an editor and mod! (https://dashboard.twitch.tv/u/{channel.name}/community/roles)")
    #         except twitchio.errors.HTTPException as e:
    #             pass
    #     return await ctx.reply("No suitable channel found.")

    # @twitch_commands.command()
    # async def code(self, ctx: twitch_commands.Context, code: str):
    #     await ctx.send(f"The code is {code}")


class DiscordBot(discord_commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.restarting = False

        self.db: asyncpg.Pool = None

        self.executed_commands = deque()

        self.guess_channels: Dict[int, Dict[str, Union[int, str, Dict[str, str]]]] = {}
        self.existing_guess_ids: List[str] = []

        self.CONFIGS = CONFIGS
        self.COLORS = LOGGING.COLORS
        self.pjsk = pjsk

        self.constants = {}
        self.constants_override = {}
        self.constants_updated = 0

        self.ban_cache = {}

        self.print = LOGGING.print
        self.info = LOGGING.infoprint
        self.error = LOGGING.errorprint
        self.warn = LOGGING.warnprint
        self.success = LOGGING.successprint
        self.traceback = LOGGING.tracebackprint

        self.send_image_update = lambda *args: None
        self.user_data = user_data

        self.alias_adders = [1322836332065718282]  # alias adder roles

        self.autocompletes = autocompletes

        self.cogs_folder = os.path.join("COGS/discord", "")

    async def get_constant(
        self,
        music_id: int,
        difficulty: str,
        ap: bool,
        error_on_not_found: bool = False,
        include_source: bool = False,
        force_39s: bool = False,
    ):  # overwritten in tasks.py
        ...

    async def add_achievement(
        self,
        intage: discord.Interaction | discord.Message,
        achievement: str,
        rank: int = 1,
        user: discord.User = None,
        ephemeral: bool = False,
    ):  # overwritten in achievements.py
        ...

    async def add_currency(
        self,
        intage: discord.Interaction | discord.Message,
        currency: int,
        user: discord.User = None,
    ):  # overwritten in achievements.py
        ...

    async def add_experience(
        self,
        intage: discord.Interaction | discord.Message,
        xp: int,
        user: discord.User = None,
        ephemeral: bool = False,
        prog_bar: bool = True,
    ):  # overwritten in achievements.py
        ...

    async def grant_reward(
        self, user: discord.User, type: str, amount: str
    ):  # overwritten in achievements.py
        ...

    def get_constant_sync(
        self,
        music_id: int,
        difficulty: str,
        ap: bool,
        error_on_not_found: bool = False,
        include_source: bool = False,
        force_39s: bool = False,
    ):  # overwritten in tasks.py
        ...

    async def subscribed(self, user: discord.User) -> int:
        """
        0 - Not in server

        1 - Not subscribed

        2 - Donator

        3 - Currently subscribed (monthly)

        """
        guild = self.get_guild(1238684904804319243)
        if not guild:
            guild = await self.fetch_guild(1238684904804319243)
        try:
            member = await guild.fetch_member(user.id)
        except discord.NotFound:
            return 0
        roles = {
            "donator": [1326315299003437066, 2],
            "subscriber": [1326314167770157177, 3],
        }
        c_l = 1
        for role, data in roles.items():
            if data[0] in member._roles:
                if data[1] > c_l:
                    c_l = data[1]
        return c_l

    async def setup_hook(self):
        await discord_bot.tree.set_translator(SbotgaTranslator())


class DiscordBotTree(app_commands.CommandTree):
    def __init__(
        self,
        client,
        *,
        fallback_to_global=True,
        allowed_contexts=app_commands.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True
        ),
        allowed_installs=discord.utils.MISSING,
    ):
        super().__init__(
            client,
            fallback_to_global=fallback_to_global,
            allowed_contexts=allowed_contexts,
            allowed_installs=allowed_installs,
        )

        self.client: DiscordBot

    async def interaction_check(self, interaction: discord.Interaction):
        safety_blacklist = [872997090647756820, 1067376819847827496]
        if interaction.guild_id in safety_blacklist:
            await interaction.response.send_message(
                embed=embeds.error_embed(
                    "For your safety, you cannot run commands on this server, as you may be banned.\n\nPlease use this command in my DMS, or in another server instead."
                ),
                ephemeral=True,
            )
            return False
        if self.client.restarting:
            try:
                await interaction.response.send_message(
                    embed=embeds.error_embed(
                        "The bot is about to undergo a restart, please wait just a little.\n"
                        "ボットは再起動中です。少し待ってくださいね。\n"  # Japanese
                        "机器人即将重新启动，请稍等一下。\n"  # Simplified Chinese
                        "機器人即將重新啟動，請稍等一下。\n"  # Traditional Chinese
                        "봇이 곧 재시작할 예정입니다. 잠시 기다려주세요.\n"  # Korean
                        "Le bot est sur le point de redémarrer, veuillez patienter un moment.\n"  # French
                        "El bot está a punto de reiniciarse, por favor espera un momento.\n"  # Spanish
                        "O bot está prestes a reiniciar, por favor, aguarde um momento.\n"  # Portuguese
                        "Il bot sta per riavviarsi, attendi un attimo.\n"  # Italian
                        "Бот скоро перезапустится, подождите немного.\n"  # Russian
                    )
                )
            except:
                pass
            try:
                command = interaction.command
                cmdname = command.qualified_name
                fullcmd = f"/{cmdname}"

                def get_params(options: list) -> dict:
                    params = {}
                    for param in options:
                        if param.get("value"):
                            params[param["name"]] = param["value"]
                        else:
                            params.update(get_params(param.get("options", [])))
                    return params

                params = get_params(interaction.data.get("options", []))

                def format_param(name, value):
                    return f"{name}: {value}"

                fullcmd += (
                    f" {[format_param(n, v) for n, v in params.items()]}"
                    if params
                    else ""
                )
                LOGGING.warnprint(
                    f"{discord_bot.COLORS.error_logs}[SLASH COMMAND BLOCKED (prepare_restart)] {discord_bot.COLORS.user_name}{interaction.user.name}{discord_bot.COLORS.normal_message} ran command {discord_bot.COLORS.item_name}{cmdname}{discord_bot.COLORS.normal_message} on the guild {discord_bot.COLORS.item_name}{interaction.guild.name if interaction.guild else 'NO GUILD'}{discord_bot.COLORS.normal_message}. Full command: {discord_bot.COLORS.item_name}{fullcmd}"
                )
            except:
                pass
            return False
        if interaction.user.id in self.client.ban_cache:
            banned = self.client.ban_cache.get(interaction.user.id)
        else:
            banned = await self.client.user_data.discord.get_banned(interaction.user.id)
            self.client.ban_cache[interaction.user.id] = banned
        if banned:
            if interaction.command and interaction.command.qualified_name == "help":
                pass
            else:
                await interaction.response.send_message(
                    embed=embeds.error_embed(
                        "You're banned from the bot. Run </help:1326325488939040808> for links to the support server to appeal."
                    )
                )
                return False
        return True


twitch_bot = TwitchBot(prefix=CONFIGS.defaultprefix, initial_channels=user_data.users)
intents = discord.Intents.default()
intents.message_content = True
discord_bot = DiscordBot(
    command_prefix=discord_commands.bot.when_mentioned,
    help_command=None,
    intents=intents,
    owner_ids=CONFIGS.discord_owners,
    tree_cls=DiscordBotTree,
)


async def on_tree_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
    item: discord.ui.Item = None,
):
    if isinstance(error, app_commands.errors.CommandNotFound) or isinstance(
        error, discord.errors.NotFound
    ):
        return
    if isinstance(
        error, app_commands.errors.CommandInvokeError
    ) and "NotFound: 404 Not Found" in str(error):
        return
    if isinstance(error, app_commands.CommandOnCooldown):
        return await interaction.response.send_message(
            f"Command is currently on cooldown! Try again in **{error.retry_after:.2f}** seconds!"
        )
    elif isinstance(error, app_commands.MissingPermissions):
        return await interaction.response.send_message(
            f"You're missing permissions to use that."
        )
    else:
        censored_error_str = f"{error}"

        def censor_non_discord_urls(text: str) -> str:
            url_pattern = r"(https?://[^\s]+)"

            def censor_url(match):
                url = match.group(0)
                if "discord.com" in url or "discord.gg" in url:
                    return url
                else:
                    parts = url.split("/")

                    # Censor subdomains, domains, and tlds
                    domain_parts = parts[2].split(".")
                    for i in range(len(domain_parts)):
                        domain_parts[i] = "[private]"
                    parts[2] = ".".join(domain_parts)

                    # Censor the path
                    if len(parts) > 3:
                        censored_path = "/".join(["[private]" for _ in parts[3:]])
                        parts = parts[:3] + [censored_path]

                    return "/".join(parts)

            return re.sub(url_pattern, censor_url, text)

        censored_error_str = censor_non_discord_urls(censored_error_str)
        errore = embeds.error_embed(
            f"Something went wrong!\n```{censored_error_str}```\n\nRun </help:1326325488939040808> for links to the support server to report this."
        )
        try:
            await interaction.edit_original_response(embed=errore)
        except:
            try:
                await interaction.followup.send(embed=errore)
            except:
                pass
        try:
            command = interaction.command
            cmdname = command.qualified_name
            fullcmd = f"/{cmdname}"

            def get_params(options: list) -> dict:
                params = {}
                for param in options:
                    if param.get("value"):
                        params[param["name"]] = param["value"]
                    else:
                        params.update(get_params(param.get("options", [])))
                return params

            params = get_params(interaction.data.get("options", []))

            def format_param(name, value):
                return f"{name}: {value}"

            fullcmd += (
                f" {[format_param(n, v) for n, v in params.items()]}" if params else ""
            )
            LOGGING.warnprint(
                f"{discord_bot.COLORS.error_logs}[SLASH COMMAND ERRORED] {discord_bot.COLORS.user_name}{interaction.user.name}{discord_bot.COLORS.normal_message} ran command {discord_bot.COLORS.item_name}{cmdname}{discord_bot.COLORS.normal_message} on the guild {discord_bot.COLORS.item_name}{interaction.guild.name if interaction.guild else 'NO GUILD'}{discord_bot.COLORS.normal_message}. Full command: {discord_bot.COLORS.item_name}{fullcmd}"
            )
        except:
            pass
        if item:
            print(f"In item {item}")
        raise error


discord_bot.tree.on_error = on_tree_error


@discord_bot.event
async def on_app_command_completion(
    interaction: discord.Interaction, command: app_commands.Command
):
    cmdname = command.qualified_name
    fullcmd = f"/{cmdname}"

    def get_params(options: list) -> dict:
        params = {}
        for param in options:
            if param.get("value"):
                params[param["name"]] = param["value"]
            else:
                params.update(get_params(param.get("options", [])))
        return params

    params = get_params(interaction.data.get("options", []))

    def format_param(name, value):
        return f"{name}: {value}"

    fullcmd += f" {[format_param(n, v) for n, v in params.items()]}" if params else ""
    LOGGING.print(
        f"{discord_bot.COLORS.command_logs}[SLASH COMMAND] {discord_bot.COLORS.user_name}{interaction.user.name}{discord_bot.COLORS.normal_message} ran command {discord_bot.COLORS.item_name}{cmdname}{discord_bot.COLORS.normal_message} on the guild {discord_bot.COLORS.item_name}{interaction.guild.name if interaction.guild else 'NO GUILD'}{discord_bot.COLORS.normal_message}. Full command: {discord_bot.COLORS.item_name}{fullcmd}"
    )


@discord_bot.event
async def on_command_error(ctx: discord_commands.Context, error: Exception):
    if isinstance(error, discord_commands.errors.CommandNotFound):
        return
    raise error


@discord_bot.event
async def on_ready():
    print(f"Discord | Logged in as | {discord_bot.user.name}")
    print(f"Discord | User id is | {discord_bot.user.id}")
    cogspathpy = [
        os.path.basename(f)
        for f in glob.glob(os.path.join(discord_bot.cogs_folder, "*.py"))
    ]
    cogs = [
        f"{discord_bot.cogs_folder[:-1]}." + os.path.splitext(f)[0] for f in cogspathpy
    ]
    for cog in cogs:
        try:
            await discord_bot.load_extension(cog.replace("/", "."))
            discord_bot.print(
                f"{discord_bot.COLORS.cog_logs}[COGS] {discord_bot.COLORS.normal_message}Loaded cog {discord_bot.COLORS.item_name}{cog}"
            )
        except discord_commands.errors.ExtensionAlreadyLoaded:
            pass
        except Exception as e:
            discord_bot.traceback(e)
    discord_bot.info("Cleaning __pycache__ up!")
    for root, dirs, files in os.walk(os.getcwd(), topdown=False):
        if "__pycache__" in dirs:
            pycache_dir = os.path.join(root, "__pycache__")
            try:
                shutil.rmtree(pycache_dir)
            except Exception as e:
                discord_bot.warn(
                    f"An error occurred while deleting {discord_bot.COLORS.item_name}{pycache_dir}{discord_bot.COLORS.normal_message}: {discord_bot.COLORS.item_name}{e}"
                )
                discord_bot.traceback(e)


async def start_bot():
    if not discord_bot.db:
        db = await asyncpg.create_pool(
            CONFIGS.database_url,
            min_size=3,
            max_size=3,
        )
        discord_bot.db = db
        user_data.db = discord_bot.db
    await user_data.fetch_data()
    await pjsk.get_custom_title_defs()
    pjsk.reload_song_aliases()

    """CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    twitch_id BIGINT,
    activated BOOLEAN,
    whitelisted BOOLEAN,
    displays JSONB,
    discord_id BIGINT,
    pjsk_id_en BIGINT,
    pjsk_id_jp BIGINT,
    pjsk_id_tw BIGINT,
    pjsk_id_kr BIGINT,
    pjsk_id_cn BIGINT,
    guess_stats JSONB,
    settings JSONB;
    achievements JSONB DEFAULT '{}';
    currency BIGINT DEFAULT 0;
    experience BIGINT NOT NULL DEFAULT 0;
    blacklisted BOOLEAN 
);
CREATE TABLE counters (
    id SERIAL PRIMARY KEY,
    twitch_id BIGINT,
    counters JSON,
    FOREIGN KEY (id) REFERENCES users(id)
);
CREATE TABLE ranked (
    id SERIAL PRIMARY KEY,
    twitch_id BIGINT,
    wins INTEGER,
    losses INTEGER,
    draws INTEGER,
    max_winstreak INTEGER,
    winstreak INTEGER,
    FOREIGN KEY (id) REFERENCES users(id)
);
CREATE TABLE song_aliases (
    id SERIAL PRIMARY KEY,
    aliases JSON
);
CREATE TABLE guilds (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL UNIQUE,
    guessing_enabled BOOLEAN DEFAULT true
);
"""

    discord.utils.setup_logging()

    await asyncio.wait(
        [
            asyncio.create_task(twitch_bot.start(twitch_token)),
            asyncio.create_task(discord_bot.start(discord_token)),
            # asyncio.create_task(esclient.listen(port=4000))
        ]
    )


"""
https://discord.com/oauth2/authorize?client_id=1322253224799109281
"""

if __name__ == "__main__":
    from app import start_fastapi

    async def shutdown(loop, tasks):
        """
        Gracefully shut down all tasks and stop the event loop.
        """
        for task in tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        loop.stop()

    async def main():
        """
        Start both FastAPI and Discord bot, and handle shutdown gracefully.
        """
        loop = asyncio.get_running_loop()

        # Create tasks for FastAPI and the Discord bot
        tasks = [
            asyncio.create_task(start_bot()),
            asyncio.create_task(start_fastapi()),
        ]

        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.CancelledError:
            pass
        finally:
            await shutdown(loop, tasks)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
