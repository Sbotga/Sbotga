import twitchio
from twitchio.ext import commands

from main import TwitchBot

from DATA.helpers.user_cache import getch_user_id


class CountersCog(commands.Cog):
    def __init__(self, bot: TwitchBot):
        self.bot = bot

    @commands.command()
    async def counters(
        self, ctx: commands.Context, action: str = "", counter: str = None
    ):
        if not (await self.bot.run_checks(ctx, activated_check=True)):
            return
        await self.bot.command_ran(ctx)
        if action.lower() in ["add", "remove"]:
            if not (await self.bot.run_checks(ctx, permission_level=3)):
                return
            if action.lower() == "add":
                if counter:
                    counter = counter.strip()
                    if len(counter) > 25:
                        return await ctx.reply(
                            "The name of the counter cannot be longer than 25 characters."
                        )
                    if "".join(counter.split()) != counter:
                        return await ctx.reply(
                            "The counter must be a single word, no spaces!"
                        )
                    existing = await self.bot.user_data.get_counters(
                        str((await getch_user_id(self, ctx.channel.name)))
                    )
                    if len(existing) >= 10:
                        return await ctx.reply("You can't have more than 10 counters!")
                    await self.bot.user_data.add_counter(
                        str((await getch_user_id(self, ctx.channel.name))), counter
                    )
                    return await ctx.reply(f"Created counter: {counter}.")
                else:
                    return await ctx.reply(f"No counter specified to create.")
            if action.lower() == "remove":
                if counter:
                    counter = counter.strip()
                    existing = await self.bot.user_data.get_counters(
                        str((await getch_user_id(self, ctx.channel.name)))
                    )
                    if counter.lower() in existing:
                        ct = existing.get_key(counter)
                        await self.bot.user_data.remove_counter(
                            str((await getch_user_id(self, ctx.channel.name))),
                            counter,
                        )
                        return await ctx.reply(f"Deleted counter {ct}!")
                    else:
                        return await ctx.reply("Counter does not exist.")
                else:
                    return await ctx.reply(f"No counter specified to delete.")
        existing = await self.bot.user_data.get_counters(
            str((await getch_user_id(self, ctx.channel.name)))
        )
        if len(existing) == 0:
            existing = {"None": "asd"}
        return await ctx.reply(
            f"{ctx.channel.name}'s current counters: {', '.join(list(existing.keys()))}"
        )

    @commands.Cog.event()
    async def event_message(self, message: twitchio.Message) -> None:
        if message.echo:
            return
        ctx = commands.Context(message=message, bot=self.bot)

        if not (await self.bot.run_checks(ctx, True, False)):
            return

        counters = await self.bot.user_data.get_counters(
            str((await message.channel.user()).id)
        )
        if (
            message.content
            and message.content.startswith("!")
            and message.content != "!"
        ):
            if message.content.removeprefix("!").lower().strip().split()[0] in counters:
                await self.bot.command_ran(ctx, msg=True)
                msgcnt = message.content.removeprefix("!").lower().strip().split()
                counter = counters.get_key(msgcnt[0])
                action = msgcnt[1] if len(msgcnt) > 1 else None
                amount = msgcnt[2] if len(msgcnt) > 2 else None
                if action in ["add", "reset", "set"]:
                    if not (await self.bot.run_checks(ctx, permission_level=2)):
                        return
                    if action == "add":
                        if amount and amount.isdigit():
                            if int(amount) < 1:
                                return await ctx.reply(
                                    "Amount to add must be at least 1."
                                )
                        else:
                            amount = 1
                        if int(amount) > 1:
                            if not (await self.bot.run_checks(ctx, permission_level=3)):
                                return
                        new = await self.bot.user_data.add_to_counter(
                            str((await message.channel.user()).id),
                            counter,
                            int(amount),
                        )
                        return await ctx.reply(f"{counter} is now at {new}!")
                    elif action == "reset":
                        if not (await self.bot.run_checks(ctx, permission_level=3)):
                            return
                        await self.bot.user_data.reset_counter(
                            str((await message.channel.user()).id), counter
                        )
                        return await ctx.reply(f"Reset the {counter} counter!")
                    elif action == "set":
                        if not (await self.bot.run_checks(ctx, permission_level=3)):
                            return
                        if amount and amount.isdigit():
                            if int(amount) < 0:
                                return await ctx.reply(
                                    "Amount to set counter to must be at least 0."
                                )
                        else:
                            return await ctx.reply("No amount specified.")
                        await self.bot.user_data.set_counter(
                            str((await message.channel.user()).id),
                            counter,
                            int(amount),
                        )
                        return await ctx.reply(
                            f"The {counter} counter is now at {amount}!"
                        )
                return await ctx.reply(
                    f"The {counter} counter is currently at {counters[counter]}!"
                )


def prepare(bot: TwitchBot):
    bot.add_cog(CountersCog(bot))
