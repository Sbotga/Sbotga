import twitchio
from twitchio.ext import commands

from main import TwitchBot

from DATA.helpers.user_cache import getch_user_id


class DevCog(commands.Cog):
    def __init__(self, bot: TwitchBot):
        self.bot = bot

    @commands.Cog.event()
    async def event_message(self, message: twitchio.Message) -> None:
        if message.echo:
            return
        ctx = commands.Context(message=message, bot=self.bot)
        if message.author.id and message.author.id == "673590022":
            if message.content.lower().startswith("!forceactivate "):
                adduser = message.content.lower().removeprefix("!forceactivate ")
                if len(adduser.split()) == 1 and adduser.lower() in [
                    user.lower() for user in self.bot.user_data.users
                ]:
                    user = (await self.bot.fetch_users(names=[adduser]))[0]
                    await self.bot.user_data.activate_user(str(user.id))
                    return await ctx.reply(f"ok ({user.id})")
                return await ctx.reply("not valid")
            if message.content.lower().startswith("!id "):
                adduser = message.content.lower().removeprefix("!id ")
                if len(adduser.split()) == 1 and adduser.lower() in [
                    user.lower() for user in self.bot.user_data.users
                ]:
                    user = (await self.bot.fetch_users(names=[adduser]))[0]
                    return await ctx.reply(f"ok ({user.id})")
                return await ctx.reply("not valid")
            if message.content.lower().startswith("!whitelist "):
                adduser = message.content.lower().removeprefix("!whitelist ")
                if len(adduser.split()) == 1:
                    adduser_id = await getch_user_id(self.bot, adduser)
                    if adduser_id == None:
                        return await ctx.reply("user not found")
                    adduser = await self.bot.user_data.whitelist_user(
                        adduser, adduser_id
                    )
                    await self.bot.join_channels([adduser])
                    await self.bot.command_ran(ctx, success=True, msg=True)
                    return await ctx.reply(
                        "ok (joining can take up to 5 minutes, can be instant)"
                    )
            elif message.content.lower().startswith("!unwhitelist "):
                removeuser = message.content.lower().removeprefix("!unwhitelist ")
                if len(removeuser.split()) == 1:
                    removeuser_id = await getch_user_id(self.bot, removeuser)
                    if removeuser_id == None:
                        return await ctx.reply("user not found")
                    removeuser = await self.bot.user_data.unwhitelist_user(
                        removeuser, removeuser_id
                    )
                    await self.bot.part_channels(removeuser)
                    await self.bot.command_ran(ctx, success=True, msg=True)
                    return await ctx.reply("ok")

            # TODO: blacklist user/unblacklist user


def prepare(bot: TwitchBot):
    bot.add_cog(DevCog(bot))
