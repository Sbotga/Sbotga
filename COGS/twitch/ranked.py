import twitchio
from twitchio.ext import commands

from main import TwitchBot

from DATA.helpers.user_cache import getch_user_id


class RankedCog(commands.Cog):
    def __init__(self, bot: TwitchBot):
        self.bot = bot

    @commands.group()
    async def ranked(self, ctx: commands.Context):
        if not (await self.bot.run_checks(ctx, activated_check=True)):
            return
        # why does twitchio not have subcommand invoked variable
        if (
            len(ctx.message.content.split(" ")) > 1
        ):  # maybe ctx.parent will be set if subcommand?
            pass
        else:
            ranked_data = await self.bot.user_data.get_ranked(
                str((await getch_user_id(self.bot, ctx.channel.name)))
            )
            total = ranked_data["wins"] + ranked_data["losses"] + ranked_data["draws"]
            await ctx.reply(
                f"Win/Draw/Loss — {ranked_data['wins']}:{ranked_data['draws']}:{ranked_data['losses']} — Max Win Streak {ranked_data['max_winstreak']} — Current Win Streak {ranked_data['winstreak']} — {round((ranked_data['wins']/total)*100) if total > 0 else 0}% Winrate"
            )

    @ranked.command()
    async def win(self, ctx: commands.Context):
        if not (
            await self.bot.run_checks(ctx, activated_check=True, permission_level=3)
        ):
            return
        await self.bot.command_ran(ctx)
        ranked_data = await self.bot.user_data.add_ranked_win(
            str((await getch_user_id(self.bot, ctx.channel.name)))
        )
        total = ranked_data["wins"] + ranked_data["losses"] + ranked_data["draws"]
        await ctx.reply(
            f"Win/Draw/Loss — {ranked_data['wins']}:{ranked_data['draws']}:{ranked_data['losses']} — Max Win Streak {ranked_data['max_winstreak']} — Current Win Streak {ranked_data['winstreak']} — {round((ranked_data['wins']/total)*100) if total > 0 else 0}% Winrate"
        )

    @ranked.command()
    async def loss(self, ctx: commands.Context):
        if not (
            await self.bot.run_checks(ctx, activated_check=True, permission_level=3)
        ):
            return
        await self.bot.command_ran(ctx)
        ranked_data = await self.bot.user_data.add_ranked_loss_or_draw(
            str((await getch_user_id(self.bot, ctx.channel.name)))
        )
        total = ranked_data["wins"] + ranked_data["losses"] + ranked_data["draws"]
        await ctx.reply(
            f"Win/Draw/Loss — {ranked_data['wins']}:{ranked_data['draws']}:{ranked_data['losses']} — Max Win Streak {ranked_data['max_winstreak']} — Current Win Streak {ranked_data['winstreak']} — {round((ranked_data['wins']/total)*100) if total > 0 else 0}% Winrate"
        )

    @ranked.command()
    async def draw(self, ctx: commands.Context):
        if not (
            await self.bot.run_checks(ctx, activated_check=True, permission_level=3)
        ):
            return
        await self.bot.command_ran(ctx)
        ranked_data = await self.bot.user_data.add_ranked_loss_or_draw(
            str((await getch_user_id(self.bot, ctx.channel.name))), ld="draw"
        )
        total = ranked_data["wins"] + ranked_data["losses"] + ranked_data["draws"]
        await ctx.reply(
            f"Win/Draw/Loss — {ranked_data['wins']}:{ranked_data['draws']}:{ranked_data['losses']} — Max Win Streak {ranked_data['max_winstreak']} — Current Win Streak {ranked_data['winstreak']} — {round((ranked_data['wins']/total)*100) if total > 0 else 0}% Winrate"
        )

    @ranked.command()
    async def reset(self, ctx: commands.Context):
        if not (
            await self.bot.run_checks(ctx, activated_check=True, permission_level=3)
        ):
            return
        await self.bot.command_ran(ctx)
        ranked_data = await self.bot.user_data.reset_ranked(
            str((await getch_user_id(self.bot, ctx.channel.name)))
        )
        total = ranked_data["wins"] + ranked_data["losses"] + ranked_data["draws"]
        await ctx.reply(
            f"Win/Draw/Loss — {ranked_data['wins']}:{ranked_data['draws']}:{ranked_data['losses']} — Max Win Streak {ranked_data['max_winstreak']} — Current Win Streak {ranked_data['winstreak']} — {round((ranked_data['wins']/total)*100) if total > 0 else 0}% Winrate"
        )


def prepare(bot: TwitchBot):
    bot.add_cog(RankedCog(bot))
