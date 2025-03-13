import discord
from discord.ext import commands
from discord import app_commands

from discord.app_commands import locale_str
from COGS.discord_translations import translations

from main import DiscordBot

import time, asyncio, importlib

from DATA.game_api import methods

from DATA.helpers import views
from DATA.helpers import discord_autocompletes

from DATA.helpers import embeds
from DATA.helpers.unblock import to_process_with_timeout

from DATA.game_api import proxy_service  # start the proxy service.


class DevCog(commands.Cog):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    def is_owner():
        async def predicate(ctx: commands.Context):
            return ctx.author.id in ctx.bot.owner_ids

        return commands.check(predicate)

    @commands.command()
    @is_owner()
    async def prepare_restart(self, ctx: commands.Context):
        self.bot.restarting = True
        await ctx.reply(
            embed=embeds.embed("Ok. (maybe wait a little before the actual restart)")
        )

    @commands.command()
    @is_owner()
    async def reload_translations(self, ctx: commands.Context):
        translations.reload()
        await ctx.reply(embed=embeds.embed("Done!"))

    # @commands.command(name="force_it")
    # @is_owner()
    # async def fit(self, ctx: commands.Context):
    #     for api in methods.all_apis:
    #         api.master_data_last_updated = [0]
    #     await ctx.reply("ow")

    @commands.command()
    @is_owner()
    async def restart_proxy(self, ctx: commands.Context):
        await ctx.reply(embed=embeds.embed("Ok.."))
        try:
            if self.bot.proxy_running:
                self.bot.proxy_running.terminate()
                await asyncio.sleep(3)
                self.bot.proxy_running.kill()
                await asyncio.sleep(2)
        except:
            pass
        importlib.reload(proxy_service)  # Ensure the latest code is used
        self.bot.proxy_running = proxy_service.run_proxy()

    @commands.command()
    @is_owner()
    async def cancel_restart(self, ctx: commands.Context):
        self.bot.restarting = False
        await ctx.reply(embed=embeds.embed("Ok.."))

    @commands.command()
    @is_owner()
    async def guess_answer(self, ctx: commands.Context):
        def get_view(bot: DiscordBot, data: dict) -> views.SbotgaView | None:
            if data["guessType"] in ["song", "character"]:
                if data["guessType"] == "song":
                    view = views.SongInfoButton(data["answer"])
                    aliases_view = views.SongAliasesButton(data["answer"])
                    view = views.merge_views(view, aliases_view)
                    if data["data"].get("is_chart"):
                        view2 = views.ReportBrokenChartButton(
                            data["data"]["region"], data["answer"], data["data"]["diff"]
                        )
                        view = views.merge_views(view, view2)
                    return view
                elif data["guessType"] == "character":
                    view = views.ViewCardButton(
                        data["data"]["card_id"], data["data"]["trained"]
                    )
                    view2 = views.CharacterInfoButton(data["answer"])
                    return views.merge_views(view, view2)
            else:
                return None

        data = self.bot.guess_channels.get(ctx.channel.id)
        if not data:
            return await ctx.reply("None.")
        embed = embeds.embed(
            title="Answer",
            description=f"Guess type: {data['guessType']}.",
        )
        embed.add_field(
            name="Answer",
            value=(
                (
                    f"The correct answer was **{data['answerName']}**."
                    + (
                        f"\n\n**This song has `{data['data']['notes']}` notes on Master.**"
                        if data["data"].get("notes")
                        else ""
                    )
                )
                if data["guessType"] != "event"
                else f"The correct answer was **{data['answerName']}** (`{data['data']['short']}`)."
            ),
            inline=False,
        )
        file = discord.utils.MISSING
        if data["answer_file_path"]:
            file = discord.File(data["answer_file_path"], "image.png")
            embed.set_image(url="attachment://image.png")

        view = get_view(self.bot, data)

        await ctx.reply(embed=embed, file=file, view=view)

    @commands.command()
    @is_owner()
    async def sync(self, ctx: commands.Context, guild: int = None):
        try:
            msg = await ctx.reply("Hold on...")
            if guild:
                await self.bot.tree.sync(guild=discord.Object(id=guild))
            else:
                await self.bot.tree.sync()
            embed = discord.Embed(
                title="Synced!",
                description=f"Wowwww more commands omg\n**Global**: `{', '.join([cmd.name for cmd in self.bot.tree._get_all_commands()])}`\n**This Guild**:`{(', '.join([cmd.name for cmd in self.bot.tree._get_all_commands(guild=ctx.guild)]) or 'None') if ctx.guild else 'Not In Guild'}`",
            )
            await msg.edit(content=None, embed=embed)
        except Exception as e:
            self.bot.traceback(e)

    @commands.command(
        name="accounts", description="View your currently linked accounts."
    )
    @is_owner()
    async def accounts_dev(self, ctx: commands.Context, user_id: int):
        regions = ["en", "jp", "tw", "kr", "cn"]
        embed = discord.Embed(
            title=f"Your PJSK Linked Accounts", color=discord.Color.blurple()
        )
        desc_text = ""
        for region in regions:
            pjsk_id = await self.bot.user_data.discord.get_pjsk_id(user_id, region)
            desc_text += f"**{region.upper()} PJSK Account:** {'`' + str(pjsk_id) + '`' if pjsk_id else 'Not Linked'}\n"
        embed.description = desc_text.strip()
        await ctx.reply(embed=embed)

    @commands.command()
    @is_owner()
    async def transfer(self, ctx: commands.Context, user_id: int, region: str):
        msg = await ctx.reply("Hold on...")
        data = await methods.Tools.get_user_and_reload_transfer(region.lower(), user_id)
        embed = discord.Embed(
            title="done",
            description=f'`{data["userInherit"]["inheritId"]}`\nPass: `{data["password"]}`',
        )
        await msg.edit(content=None, embed=embed)

    @commands.command()
    @is_owner()
    async def ban(self, ctx: commands.Context, user: discord.User):
        await self.bot.user_data.discord.set_banned(user.id, True)
        self.bot.ban_cache.pop(user.id, None)
        await ctx.reply(embed=embeds.embed(f"Rip {user.display_name}"))

    @commands.command()
    @is_owner()
    async def unban(self, ctx: commands.Context, user: discord.User):
        await self.bot.user_data.discord.set_banned(user.id, False)
        self.bot.ban_cache.pop(user.id, None)
        await ctx.reply(embed=embeds.embed(f"Wb {user.display_name}"))

    @commands.command()
    @is_owner()
    async def dev_link(
        self, ctx: commands.Context, user: discord.User, user_id: int, region: str
    ):
        msg = await ctx.reply("Hold on...")
        await self.bot.user_data.discord.update_pjsk_id(user.id, int(user_id), region)
        embed = discord.Embed(
            title="done",
            description=f"heh",
        )
        await msg.edit(content=None, embed=embed)

    # @commands.command()
    # @is_owner()
    # async def dev_unlink(
    #     self, ctx: commands.Context, user: discord.User, user_id: int, region: str
    # ):
    #     msg = await ctx.reply("Hold on...")
    #     await self.bot.user_data.discord.update_pjsk_id(user.id, int(user_id), region) # TODO: grab discord user id from pjsk id and unlink like that, as an option
    #     embed = discord.Embed(
    #         title="done",
    #         description=f"heh",
    #     )
    #     await msg.edit(content=None, embed=embed)

    @commands.command(name="force_troll")
    @is_owner()
    async def force_troll(self, ctx: commands.Context):
        self.bot.FORCE_TROLL_REACT = True
        await ctx.message.add_reaction("<:sbuga:1293557990397448285>")
        await asyncio.sleep(0.2)
        await ctx.message.remove_reaction("<:sbuga:1293557990397448285>", self.bot.user)

    @commands.command(name="reimport")
    @is_owner()
    async def reimport(self, ctx: commands.Context):
        """Reimport helpers."""
        items = ["views", "methods", "autocompletes", "CONFIGS", "user_data"]
        joiner = "`\n- `"
        await ctx.reply(f"Reimporting:\n- `{joiner.join(items)}`")

        importlib.reload(views)
        importlib.reload(methods)
        importlib.reload(discord_autocompletes)

        from DATA import user_data
        from DATA import CONFIGS

        importlib.reload(user_data)
        importlib.reload(CONFIGS)

        self.bot.user_data = user_data.user_data
        self.bot.user_data.db = self.bot.db
        await self.bot.user_data.fetch_data()
        self.bot.CONFIGS = CONFIGS.CONFIGS

    @commands.command(name="refresh")
    @is_owner()
    async def refresh(self, ctx: commands.Context):
        """Refresh an asset."""
        await ctx.reply("This may take a while, updating all master data.")
        try:

            def _run():
                for api in methods.all_apis:
                    api.get_bundle_metadata(force=True)
                for api in methods.all_apis:
                    api.update_master_data(force=True)
                for api in methods.all_apis:
                    api.master_data_cache = {}
                self.bot.pjsk.refresh_data()
                self.bot.constants_updated = 0  # force refresh when available

            await to_process_with_timeout(_run, timeout=600)  # 10 minutes
            await self.bot.pjsk.get_custom_title_defs()
            self.bot.pjsk.reload_song_aliases()
            embed = discord.Embed(
                title="✅ Refresh Successful",
                description=f"Successfully refreshed some data!",
                color=discord.Color.green(),
            )
            await ctx.reply(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Refresh Failed",
                description=f"Failed to refresh assets.\n```{e}```",
                color=discord.Color.red(),
            )
            await ctx.reply(embed=embed)

    @commands.command(name="guess_reset")
    @is_owner()
    async def guess_reset(
        self, ctx: commands.Context, user: discord.User, key: str, stat: str
    ):
        """Refresh an asset."""
        if stat == "all":
            stat = None
        try:
            await self.bot.user_data.discord.reset_guesses(user.id, key, stat)
            embed = discord.Embed(
                title="✅ Reset Successful",
                description=f"Successfully reset user's guess stats! Key: `{stat if stat else 'ALL'}`",
                color=discord.Color.green(),
            )
            await ctx.reply(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Reset Failed",
                description=f"Failed to reset guesses.\n```{e}```",
                color=discord.Color.red(),
            )
            await ctx.reply(embed=embed)

    @commands.command(name="reload")
    @is_owner()
    async def reload(self, ctx: commands.Context, cog: str):
        """Reload a specific cog."""
        try:
            await self.bot.reload_extension(
                self.bot.cogs_folder.strip("/\\").replace("/", ".").strip("/\\")
                + "."
                + cog
            )
            embed = discord.Embed(
                title="✅ Reload Successful",
                description=f"Successfully reloaded `{cog}`!",
                color=discord.Color.green(),
            )
            await ctx.reply(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Reload Failed",
                description=f"Failed to reload `{cog}`.\n```{e}```",
                color=discord.Color.red(),
            )
            await ctx.reply(embed=embed)

    @commands.command(name="load")
    @is_owner()
    async def load(self, ctx: commands.Context, cog: str):
        """Load a specific cog."""
        try:
            await self.bot.load_extension(
                self.bot.cogs_folder.strip("/\\").replace("/", ".").strip("/\\")
                + "."
                + cog
            )
            embed = discord.Embed(
                title="✅ Load Successful",
                description=f"Successfully loaded `{cog}`!",
                color=discord.Color.green(),
            )
            await ctx.reply(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Load Failed",
                description=f"Failed to load `{cog}`.\n```{e}```",
                color=discord.Color.red(),
            )
            await ctx.reply(embed=embed)

    @commands.command(name="unload")
    @is_owner()
    async def unload(self, ctx: commands.Context, cog: str):
        """Unload a specific cog."""
        try:
            await self.bot.unload_extension(
                self.bot.cogs_folder.strip("/\\").replace("/", ".").strip("/\\")
                + "."
                + cog
            )
            embed = discord.Embed(
                title="✅ Unload Successful",
                description=f"Successfully unloaded `{cog}`!",
                color=discord.Color.green(),
            )
            await ctx.reply(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Unload Failed",
                description=f"Failed to unload `{cog}`.\n```{e}```",
                color=discord.Color.red(),
            )
            await ctx.reply(embed=embed)


async def setup(bot: DiscordBot):
    await bot.add_cog(DevCog(bot))
