import twitchio
from twitchio.ext import commands

from main import TwitchBot

import random
from typing import Annotated

from DATA.helpers import converters
from DATA.data.pjsk import Song


class SongsCog(commands.Cog):
    def __init__(self, bot: TwitchBot):
        self.bot = bot

    @commands.command()
    async def randomsong(self, ctx: commands.Context):
        if not (await self.bot.run_checks(ctx, activated_check=True, game_check=True)):
            return
        await self.bot.command_ran(ctx)
        title = random.choice(list(self.bot.pjsk.title_maps.keys()))
        data = self.bot.pjsk.songs[self.bot.pjsk.title_maps[title]]
        song_id = self.bot.pjsk.title_maps[title]
        difficulties = self.bot.pjsk.difficulties[song_id]
        song = Song(data, difficulties)
        await ctx.reply(song.readable)

    @commands.command(aliases=["music"])
    async def song(
        self, ctx: commands.Context, *, song: Annotated[Song, converters.SongConverter]
    ):
        if not (await self.bot.run_checks(ctx, activated_check=True, game_check=True)):
            return
        await self.bot.command_ran(ctx)
        if not song:
            await ctx.reply("Song not found.")
        else:
            await ctx.reply(song.readable)


def prepare(bot: TwitchBot):
    bot.add_cog(SongsCog(bot))
