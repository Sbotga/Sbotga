import twitchio
from twitchio.ext import commands

from main import TwitchBot

import random

import async_google_trans_new

from DATA.helpers.user_cache import getch_user_id
from DATA.data.quotes import quotes


class InfoCog(commands.Cog):
    def __init__(self, bot: TwitchBot):
        self.bot = bot

    @commands.command(aliases=["commands", "info", "cmds", "about"])
    async def help(self, ctx: commands.Context):
        if not (await self.bot.run_checks(ctx, activated_check=True)):
            return
        await self.bot.command_ran(ctx)
        cmds = self.bot.commands.copy()
        del cmds["activate"]
        if ctx.author.id:
            if (await getch_user_id(self.bot, ctx.channel.name)) == int(ctx.author.id):
                pass
            else:
                del cmds["deactivate"]
        else:
            del cmds["deactivate"]
        for name, cmd in cmds.copy().items():
            if cmd.parent or len(cmd.full_name.split(" ")) != 1:
                del cmds[name]
        await ctx.reply(
            f'https://docs.google.com/document/d/1lBut_KFx5uTD2GrCBh9K0hAkB6YbvZPrFowN6VPKNB8/ |---| Commands: {self.bot._prefix}{f", {self.bot._prefix}".join(cmds)}'  # TODO: prefix
        )

    @commands.command()
    async def pjskquote(self, ctx: commands.Context):
        if not (await self.bot.run_checks(ctx, activated_check=True)):
            return
        await self.bot.command_ran(ctx)
        await ctx.reply(random.choice(quotes["quote"]).replace("\n\n", " |====| "))

    @commands.command()
    async def random_number(self, ctx: commands.Context):
        if not (await self.bot.run_checks(ctx, activated_check=True)):
            return
        await self.bot.command_ran(ctx)
        await ctx.reply(f"Your random number (1-12) is {random.randint(1, 12)}")

    @commands.command()
    async def translate(self, ctx: commands.Context, *, text: str):
        if not (await self.bot.run_checks(ctx, activated_check=True)):
            return
        await self.bot.command_ran(ctx)
        result = (
            "Results inaccurate with romaji. Translation: "
        ) + await async_google_trans_new.AsyncTranslator(url_suffix="com").translate(
            text, lang_tgt="en", lang_src="jp"
        )
        chunks = [result[i : i + 250] for i in range(0, len(result), 250)]
        r = False
        for chunk in chunks:
            if not r:
                await ctx.reply(chunk)
                r = True
            else:
                await ctx.send(chunk)


def prepare(bot: TwitchBot):
    bot.add_cog(InfoCog(bot))
