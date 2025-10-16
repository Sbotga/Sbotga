import discord
from discord.ext import commands, tasks
from discord import app_commands

from discord.app_commands import locale_str
from COGS.discord_translations import translations

from main import DiscordBot

import time, csv, asyncio, datetime
from io import StringIO

import aiohttp

from DATA.game_api import methods

from DATA.helpers import discord_autocompletes as autocompletes
from DATA.helpers import converters
from DATA.helpers import embeds
from DATA.helpers import unblock

from DATA.data.pjsk import Song


class TasksAndUpdates(commands.Cog):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

        self.bot.get_constant = self.get_constant
        self.bot.get_constant_sync = self.get_constant_sync

        self.cog_tasks.start()
        self.hourly_task.start()

    @tasks.loop(hours=1)
    async def hourly_task(self):
        # runs hourly at :00 and 20 seconds (to allow the game to update)
        # timeout set to 3600 - 100 seconds, so 1 hour - 100 seconds.
        pass
        # need more ram for below code, maybe even spawn a subprocess (methods.py update can be run separately)
        # await unblock.to_process_with_timeout(methods.Tools.update_everything, False, timeout=3500) # updates master data and all relevant assets
        # for api in methods.all_apis:
        #     api.master_data_cache = {}

    @hourly_task.before_loop
    async def before_hourly(self):
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        next_hour = (now + datetime.timedelta(hours=1)).replace(
            minute=0, second=20, microsecond=0
        )
        wait_seconds = (next_hour - now).total_seconds()
        await asyncio.sleep(wait_seconds)

    def cog_unload(self):
        """Cancel the task to prevent orphaned tasks."""
        self.cog_tasks.cancel()
        self.hourly_task.cancel()

    @tasks.loop(seconds=60)
    async def cog_tasks(self):
        if self.bot.cache.constants_updated + 3600 < time.time():
            await self.update_constants()

    async def get_constant(
        self,
        music_id: int,
        difficulty: str,
        ap: bool,
        error_on_not_found: bool = False,
        include_source: bool = False,
        force_39s: bool = False,
    ) -> float | tuple:
        # Check if the constants were updated in the last 60 minutes
        if self.bot.cache.constants_updated + 3600 < time.time():
            await self.update_constants()
        return self.get_constant_sync(
            music_id, difficulty, ap, error_on_not_found, include_source, force_39s
        )

    def get_constant_sync(
        self,
        music_id: int,
        difficulty: str,
        ap: bool,
        error_on_not_found: bool = False,
        include_source: bool = False,
        force_39s: bool = False,
    ) -> float | tuple:
        key = (music_id, difficulty)
        diff = self.bot.cache.constants_override.get(key)
        source = "Community (not 39s)"
        if force_39s or (not diff):
            diff = self.bot.cache.constants.get(key)
            source = "Community (39s)"
        if not diff:
            if error_on_not_found:
                raise IndexError()
            diff = methods.Tools.get_music_diff(music_id, difficulty)
            source = "Not Community Rated"
        if include_source:
            return (
                diff - 1 if diff and not ap else diff if diff and ap else diff
            ), source
        else:
            return diff - 1 if diff and not ap else diff if diff and ap else diff

    async def update_constants(self):
        url = "https://docs.google.com/spreadsheets/d/1B8tX9VL2PcSJKyuHFVd2UT_8kYlY4ZdwHwg9MfWOPug/export?format=csv&gid=1855810409"
        url2 = "https://docs.google.com/spreadsheets/d/1Yv3GXnCIgEIbHL72EuZ-d5q_l-auPgddWi4Efa14jq0/export?format=csv&gid=182216"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    csv_data = await response.read()
                    await self.parse_csv(csv_data)
                    self.bot.cache.constants_updated = time.time()
            async with session.get(url2) as response:
                if response.status == 200:
                    csv_data = await response.read()
                    await self.parse_csv(csv_data, secondary=True)
                    self.bot.cache.constants_updated = time.time()

    async def parse_csv(self, csv_data: bytes, secondary: bool = False):
        # Decode CSV data and load into a dictionary
        decoded_data = csv_data.decode("utf-8")
        csv_file = StringIO(decoded_data)
        reader = csv.DictReader(csv_file)

        # Assuming the CSV contains columns 'Constant', 'Difficulty', 'Song ID'
        for row in reader:
            try:
                music_id = int(row["Song ID"])
                difficulty = row["Difficulty"].lower()
                constant = round(float(row["Constant"]), 1)

                assert difficulty in [
                    "easy",
                    "normal",
                    "hard",
                    "expert",
                    "master",
                    "append",
                ]

                if secondary:
                    self.bot.cache.constants_override[(music_id, difficulty)] = constant
                else:
                    self.bot.cache.constants[(music_id, difficulty)] = constant

            except (ValueError, KeyError, AssertionError) as e:
                pass


async def setup(bot: DiscordBot):
    await bot.add_cog(TasksAndUpdates(bot))
