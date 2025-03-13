import twitchio
from twitchio.ext import commands

from main import TwitchBot

import random, asyncio

from DATA.helpers.user_cache import getch_user_id


class SettingsCog(commands.Cog):
    def __init__(self, bot: TwitchBot):
        self.bot = bot

    @commands.command()
    async def activate(self, ctx: commands.Context):
        if (
            str((await getch_user_id(self.bot, ctx.channel.name)))
            in self.bot.user_data.users_using
        ):
            return
        if not (await self.bot.run_checks(ctx, permission_level=4)):
            return
        if ctx.author.id:
            if (await getch_user_id(self.bot, ctx.channel.name)) == int(ctx.author.id):
                chars = [".", "> ", "|", ",", "+", "*"]
                await ctx.send(f"{random.choice(chars)} Activating...")
                await asyncio.sleep(1)
                if ctx.channel.get_chatter(self.bot.nick).is_mod:
                    await self.bot.user_data.activate_user(
                        str((await getch_user_id(self.bot, ctx.channel.name)))
                    )
                    await ctx.reply(f"Bot activated! Run !help")
                    await self.bot.command_ran(ctx, success=True)
                else:
                    await ctx.reply(
                        f"{random.choice(chars)} Please mod bot and run !activate again."
                    )
                    await self.bot.command_ran(ctx, success=False)
            else:
                await self.bot.command_ran(ctx, success=False)

    @commands.command()
    async def toggle_reminders(self, ctx: commands.Context):
        if not (
            await self.bot.run_checks(ctx, activated_check=True, permission_level=3)
        ):
            return
        await self.bot.command_ran(ctx, success=True)
        on = self.bot.user_data.toggle_reminders(
            str((await getch_user_id(self.bot, ctx.channel.name)))
        )
        if on:
            await ctx.reply(
                "Turned hydration and stretch reminders on! They will appear every 10 minutes."
            )
        else:
            await ctx.reply("Turned hydration and stretch reminders off!")

    @commands.command()
    async def deactivate(self, ctx: commands.Context):
        if not (await self.bot.run_checks(ctx, activated_check=True)):
            return
        if ctx.author.id:
            if (await getch_user_id(self.bot, ctx.channel.name)) == int(ctx.author.id):
                await self.bot.command_ran(ctx, success=True)
                await self.bot.user_data.deactivate_user(
                    str((await getch_user_id(self.bot, ctx.channel.name)))
                )
                await ctx.reply("Bot deactivated!")
            else:
                await self.bot.command_ran(ctx, success=False)


def prepare(bot: TwitchBot):
    bot.add_cog(SettingsCog(bot))
