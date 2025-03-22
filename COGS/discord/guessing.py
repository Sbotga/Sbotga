import asyncio
import discord
from discord.ext import commands, tasks
from discord import app_commands

from discord.app_commands import locale_str
from COGS.discord_translations import translations

from main import DiscordBot

import time, os, secrets, random, io

from typing import Tuple, Coroutine, Callable, Any

from PIL import Image
import numpy as np

from DATA.data.pjsk import Song
from DATA.helpers.discord_user_cache import getch_user_name, save_user_name

from DATA.helpers import views
from DATA.helpers.discord_emojis import emojis
from DATA.helpers import converters
from DATA.helpers.tools import generate_secure_string
from DATA.helpers import discord_autocompletes as autocompletes
from DATA.helpers import embeds
from DATA.helpers.unblock import to_process_with_timeout
from DATA.helpers import tools
from DATA.helpers import pjsk_chart

from DATA.game_api import methods

# TODO: translate get_view (and views.py i suppose)

# See also to modify: DATA/helpers/discord_autocompletes.autocompletes.py
TYPE_TO_NAME = {
    "jacket": "Jacket",
    "jacket_30px": "Jacket 30px",
    "jacket_bw": "Jacket Black and White",
    "jacket_challenge": "Jacket Challenge",
    "character": "Character",
    "character_bw": "Character Black and White",
    "chart": "Chart",
    "chart_append": "Chart Append",
    "event": "Event",
    "notes": "Song Note Count",
}


def get_view(
    bot: DiscordBot, data: dict, timeout: int = None
) -> views.SbotgaView | None:

    button_timeout = timeout or 15

    class play_again_view(views.SbotgaView):
        def __init__(
            self,
            play_again_func: Callable[
                [discord.Interaction, str], Coroutine[Any, Any, None]
            ],
            guessing: str,
        ):
            super().__init__(timeout=button_timeout)

            self.play_again_func = play_again_func
            self.guessing = guessing

        @discord.ui.button(style=discord.ButtonStyle.primary, label="Play Again")
        async def play_again(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            button.disabled = True
            await interaction.message.edit(view=button._view)
            await self.play_again_func(interaction, self.guessing)

    play_again = play_again_view(data["func"], data["guessing"])

    if data["guessType"] in ["song", "character"]:
        if data["guessType"] == "song":
            view = views.SongInfoButton(data["answer"])
            aliases_view = views.SongAliasesButton(data["answer"])
            view = views.merge_views(
                play_again, view, aliases_view, timeout=button_timeout
            )
            if data["data"].get("is_chart"):
                view2 = views.ReportBrokenChartButton(
                    data["data"]["region"], data["answer"], data["data"]["diff"]
                )
                view = views.merge_views(view, view2, timeout=button_timeout)
            return view
        elif data["guessType"] == "character":
            view = views.ViewCardButton(
                data["data"]["card_id"], data["data"]["trained"]
            )
            view2 = views.CharacterInfoButton(data["answer"])
            return views.merge_views(play_again, view, view2, timeout=button_timeout)
    else:
        return play_again


class GuessCog(commands.Cog):
    def __init__(self, bot: DiscordBot):
        # These only apply if message_content intent is ON.
        # Otherwise, they are all ignored.
        self.guess_prefix = "-"
        self.use_prefix = True
        self.no_ping = True
        self.deprecate_ping = True

        assert self.use_prefix or (not self.no_ping and not self.deprecate_ping)

        self.tip_embeds = [
            discord.Embed(
                description="**TIP - Did you know you can guess in the bot's DMs? A 100% private guessing space!**",
                color=discord.Color.green(),
            ),
            discord.Embed(
                description="**TIP - Giving up? You can end a guess early with the `/guess end` command!**",
                color=discord.Color.green(),
            ),
            discord.Embed(
                description="**TIP - Having trouble on a guess? Perhaps the `/guess hint` command will help!**",
                color=discord.Color.green(),
            ),
            discord.Embed(
                description="**TIP - You can check your guess statistics with `/guess stats`!**",
                color=discord.Color.green(),
            ),
            discord.Embed(
                description="**TIP - Do you want more song aliases? You can suggest them in our support server!**",
                color=discord.Color.green(),
            ),
        ]

        self.bot = bot
        if not hasattr(self.bot, "downloading_jackets"):
            self.bot.downloading_jackets = False
        if not hasattr(self.bot, "downloading_charts"):
            self.bot.downloading_charts = False
        if not hasattr(self.bot, "downloading_cards"):
            self.bot.downloading_cards = False

        if not hasattr(self.bot, "download_jackets"):
            self.bot.download_jackets = self.download_jackets
        if not hasattr(self.bot, "download_cards"):
            self.bot.download_cards = self.download_cards
        # since we have deprecated the above methods, no future methods related will be added. Includes: charts

        self.max_guess_time = 60  # 60 seconds to guess. Divided by 2 for character guessing, and divided by 3 for chart append.

        self.check_guess_task.start()

    async def cog_load(self):
        # if self.bot.guess_channels == {}:
        #     await self.download_jackets()
        #     # await self.download_cards()
        return await super().cog_load()

    def cog_unload(self):
        # Prevent orphaned task, where the task still runs while cog is unloaded or destroyed.
        self.check_guess_task.cancel()
        return super().cog_unload()

    """
    
    FUNCTIONS
    
    """
    # region FUNCTIONS AND STATICMETHODS

    async def random_crop_rectangle(
        self, path, size=250, bw: bool = False
    ) -> io.BytesIO:
        def _make():
            img = Image.open(path)
            img_array = np.array(img.convert("L" if bw else "RGB"))
            height, width = img_array.shape[:2]

            ran1 = random.randint(0, width - size)
            ran2 = random.randint(0, height - size)
            cropped = img_array[ran2 : ran2 + size, ran1 : ran1 + size]

            output = Image.fromarray(cropped)
            f = io.BytesIO()
            output.save(f, "PNG")
            f.seek(0)
            return f

        return await to_process_with_timeout(_make)

    async def random_crop(self, path, size=140, bw=False) -> io.BytesIO:
        def _make():
            img = Image.open(path)
            img_array = np.array(img.convert("L" if bw else "RGB"))
            height, width = img_array.shape[:2]

            ran1 = random.randint(0, width - size)
            ran2 = random.randint(0, height - size)
            cropped = img_array[ran2 : ran2 + size, ran1 : ran1 + size]

            output = Image.fromarray(cropped)
            f = io.BytesIO()
            output.save(f, "PNG")
            f.seek(0)
            return f

        return await to_process_with_timeout(_make)

    def random_event(self, en_only: bool = False) -> dict:
        choices = self.bot.pjsk.events
        if en_only:
            choices = [
                choice
                for choice, value in choices.items()
                if not methods.pjsk_game_api.isleak_event(value["id"])
            ]
        else:
            choices = choices.keys()
        choice = secrets.choice(choices)
        r = methods.Tools.isleak_event(choice)
        if r == None:
            r = True
        while r:
            choice = secrets.choice(choices)
            r = methods.Tools.isleak_event(choice)
            if r == None:
                r = True
        return self.bot.pjsk.events[choice]

    def random_song(self, has_append: bool = False) -> Song:
        choices = list(self.bot.pjsk.songs.keys())

        if has_append:
            choices = [
                choice
                for choice in choices
                if self.bot.pjsk.difficulties[choice].get("append")
            ]

        choice = secrets.choice(choices)
        r = methods.Tools.isleak(choice)
        if r == None:
            r = True
        while r:
            choice = secrets.choice(choices)
            r = methods.Tools.isleak(choice)
            if r == None:
                r = True

        song = Song(self.bot.pjsk.songs[choice], self.bot.pjsk.difficulties[choice])

        return song

    def random_card(self) -> tuple:
        """
        Character ID (`1`), assetBundleName (`res001_no001`), card id, rarityType (`rarity_2`)
        """
        api = methods.pjsk_game_api_jp
        cards = api.get_master_data("cards.json")
        rannum = random.randint(0, len(cards) - 1)
        while (
            cards[rannum]["releaseAt"] > int(time.time() * 1000)  # leak check
            or cards[rannum]["cardRarityType"] == "rarity_1"  # oh it's a 1*...
            or cards[rannum]["cardRarityType"] == "rarity_2"  # oh it's a 2*...
        ):
            rannum = random.randint(0, len(cards) - 1)
        return (
            cards[rannum]["characterId"],
            cards[rannum]["assetbundleName"],
            cards[rannum]["id"],
            cards[rannum]["cardRarityType"],
        )

    async def random_crop_chart(self, png_path: str | io.BytesIO) -> io.BytesIO:
        def _make():
            img = Image.open(png_path)
            img_array = np.array(img)
            height, width, _ = img_array.shape

            row = round((width - 80) / 272)
            rannum = random.randint(2, row - 1)
            start_x = 80 + 272 * (rannum - 1)
            end_x = start_x + 192
            start_y, end_y = 32, height - 287

            cropped = img_array[start_y:end_y, start_x:end_x]

            mid_y = cropped.shape[0] // 2
            img1 = cropped[: mid_y + 20]
            img2 = cropped[mid_y - 20 :]

            final_height = mid_y - 10
            final = np.full((final_height, 410, 3), 255, dtype=np.uint8)

            final[-7 : -7 + img2.shape[0], 10 : 10 + img2.shape[1]] = img2
            final[-20 : -20 + img1.shape[0], 210 : 210 + img1.shape[1]] = img1

            output = Image.fromarray(final)

            result = io.BytesIO()
            output.save(result, format="png")
            result.seek(0)
            return result

        return await to_process_with_timeout(_make)

    async def channel_checks(
        self, interaction: discord.Interaction, already_guessing_check=True
    ) -> bool:
        try:
            save_user_name(interaction.user.id, interaction.user.name)
            if not interaction.channel:
                embed = embeds.error_embed(
                    f"I could not get the current channel.",
                )
                await interaction.followup.send(embed=embed)
                return False
            if already_guessing_check and (
                (interaction.channel.id in self.bot.guess_channels)
            ):
                embed = embeds.error_embed(
                    f"A guessing game is already happening in this channel!",
                )
                await interaction.followup.send(embed=embed)
                return False
            if isinstance(interaction.channel, discord.channel.DMChannel):
                if await self.bot.subscribed(interaction.user) < 1:
                    embed = embeds.error_embed(
                        f"To guess in the bot's DMs, you must join the support server. See </help:1326325488939040808> for links.",
                    )
                    await interaction.followup.send(embed=embed)
                    return False
            elif isinstance(interaction.channel, discord.channel.GroupChannel):
                embed = embeds.error_embed(
                    f"Group DMs don't work! Please use a server for guessing with multiple people. Either ask a server to add the bot, or make one.",
                )
                await interaction.followup.send(embed=embed)
                return False
            elif not (
                await self.bot.user_data.discord.guessing_enabled(interaction.guild_id)
            ):
                embed = embeds.error_embed(
                    f"You cannot use guessing in this server as it has been disabled.",
                )
                await interaction.followup.send(embed=embed)
                return False
            elif not (
                interaction.guild
                and interaction.channel.permissions_for(
                    interaction.guild.me
                ).send_messages
                and interaction.channel.permissions_for(
                    interaction.guild.me
                ).embed_links
                and interaction.channel.permissions_for(
                    interaction.guild.me
                ).attach_files
            ):
                embed = embeds.error_embed(
                    f"I don't have access to this channel. Check my permissions and try again.\n\n**Permissions Required**\n- `Send Messages`\n- `Embed Links`\n- `Attach Files`",
                )
                await interaction.followup.send(embed=embed)
                return False
            if interaction.guild:
                try:
                    await interaction.guild.fetch_member(self.bot.user.id)
                except discord.NotFound:
                    embed = embeds.error_embed(
                        f"I'm not in this server! Please ask the owner to add the bot, or run the command in another server.",
                    )
                    await interaction.followup.send(embed=embed)
                    return False
            return True
        except Exception as e:
            raise e

    async def download_jackets(self):
        self.bot.downloading_jackets = True
        while self.bot.guess_channels != {}:
            await asyncio.sleep(1)  # Wait for all guesses to finish.
        methods.pjsk_game_api.download_music_jackets()
        methods.pjsk_game_api_jp.download_music_jackets()
        self.bot.downloading_jackets = False

    async def download_cards(self):
        self.bot.downloading_cards = True
        while self.bot.guess_channels != {}:
            await asyncio.sleep(1)  # Wait for all guesses to finish.
        # methods.pjsk_game_api.download_character_cards()
        methods.pjsk_game_api_jp.download_character_cards()
        self.bot.downloading_cards = False

    """
    
    STATIC METHODS
    
    """

    @staticmethod
    def remove_guess(bot: DiscordBot, channel_id: str):
        guess = bot.guess_channels.pop(channel_id, {})
        if guess.get("id"):
            try:
                bot.existing_ids.remove(guess.get("id"))
            except:
                pass

    @staticmethod
    def guess_ended(bot: DiscordBot, data: dict) -> bool:
        if bot.guess_channels.get(data["channel"].id, {}).get("id", "") != data["id"]:
            return True
        return False

    @staticmethod
    def generate_guess_end(
        bot: DiscordBot, data: dict, paid: int = None, new: int = None
    ) -> tuple:
        embed = embeds.embed(
            title="Guess Ended",
            description=f"You failed to guess the {data['guessType']}.",
            color=discord.Color.red(),
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
        files = []
        if data["data"].get("thumbnail"):
            file = discord.File(data["data"]["thumbnail"], "thumb.png")
            files.append(file)
            embed.set_thumbnail(url="attachment://thumb.png")
        if data["answer_file_path"]:
            if isinstance(data["answer_file_path"], io.BytesIO):
                data["answer_file_path"].seek(0)
            file = discord.File(data["answer_file_path"], "image.png")
            files.append(file)
            embed.set_image(url="attachment://image.png")

        view = get_view(bot, data)

        if paid:
            embed.add_field(
                name=f"{emojis.sbugacoin} Paid",
                value=f"You paid **{paid:,}** {emojis.sbugacoin} to end this guess. You now have **{new:,}** {emojis.sbugacoin}.",
                inline=False,
            )

        return embed, files, view

    @staticmethod
    async def create_leaderboard_embed(
        page: int,
        total_pages: int,
        guess_type_name: str,
        data: dict,
        user_specific: list,
        bot: DiscordBot,
    ):
        """
        page=page,
        total_pages=total_pages,
        guess_type_name=guess_type,
        data=leaderboard,
        user_specific=[user_position, user_page],
        bot=self.bot
        """
        embed = embeds.embed(
            title=f"Guessing {guess_type_name} Leaderboard",
            color=discord.Color.purple(),
        )
        desc = f"-# Page {page}/{total_pages}\n\n"
        for rank, user in enumerate(data, start=(page - 1) * 25 + 1):
            duser = (
                await getch_user_name(bot, user["discord_id"], return_old_data=True)
            ) or "Unknown"
            score = user["score"]
            neg = ""
            if user["score"] < 0:
                score *= -1
                neg = "NEGATIVE "
            desc += f"**#{rank} - {tools.escape_md(duser)}** - `{neg}{score:,} POINT{'S' if user['score'] != 1 else ''}`\n"
        embed.description = desc.strip()
        rank = (
            f"You are rank #{user_specific[0]} on page {user_specific[1]}"
            if user_specific[0] != 0
            else "You are not ranked (no guesses)"
        )
        embed.set_footer(text=f"Guessing Leaderboard - {rank}")
        return embed

    # endregion
    """

    CHECK FOR ENDED GUESSES
    
    """

    @tasks.loop(seconds=0.5)
    async def check_guess_task(self):
        def max_guess_time():
            if data["guessing"] == "chart_append":
                return self.max_guess_time // 3
            return (
                self.max_guess_time
                if data["guessType"] == "song"
                else self.max_guess_time // 2
            )

        for channel_id, data in self.bot.guess_channels.copy().items():
            if data["startTime"] and data["startTime"] + max_guess_time() < time.time():
                try:
                    embed = embeds.embed(
                        title="Failed",
                        description=f"You failed to guess the {data['guessType']}.",
                        color=discord.Color.red(),
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
                    if data["guessType"] == "character" and data.get("data"):
                        embed.description += f"\n**Card:** {data['data']['card_name']}"
                    if self.guess_ended(self.bot, data):
                        return
                    view = get_view(self.bot, data)
                    files = []
                    if data["data"].get("thumbnail"):
                        file = discord.File(data["data"]["thumbnail"], "thumb.png")
                        files.append(file)
                        embed.set_thumbnail(url="attachment://thumb.png")
                    if data["answer_file_path"]:
                        if isinstance(data["answer_file_path"], io.BytesIO):
                            data["answer_file_path"].seek(0)
                        file = discord.File(data["answer_file_path"], "image.png")
                        files.append(file)
                        embed.set_image(url="attachment://image.png")
                    da_embeds = [embed]
                    tip = random.randint(1, 10) == 7
                    if tip:
                        da_embeds.append(random.choice(self.tip_embeds))
                    msg = await data["channel"].send(
                        embeds=da_embeds, view=view, files=files
                    )
                    if view:
                        view.message = msg
                except:
                    pass
                self.remove_guess(self.bot, channel_id)

    """
    
    CHECK FOR GUESSES
    
    """
    # region ON MESSAGE AND ACHIEVEMENTS

    async def handle_guess_achievement(
        self, message: discord.Message, guess_data: dict
    ):
        achievements = await self.bot.user_data.discord.get_achievements(
            message.author.id
        )
        achievement_fail = achievements.get("guess_fail")
        achievement_success = achievements.get("guess_success")
        achievement_general = achievements.get("guess_general")

        """
        {
            "fail": 0,
            "success": 0,
            "ragequit": 0,
            "hint": 0,
        }
        """

        if not achievement_fail and guess_data["fail"] >= 50:
            await self.bot.add_achievement(message, "guess_fail")
            return

        if achievement_success:
            achievement_success_rank = max(
                int(rank) for rank in achievement_success["granted"].keys()
            )
        else:
            achievement_success_rank = 0
        success_ranks = [5, 39, 100, 390, 666, 1000, 3939, 5000, 7500, 15000, 39039]

        if achievement_general:
            achievement_general_rank = max(
                int(rank) for rank in achievement_general["granted"].keys()
            )
        else:
            achievement_general_rank = 0
        general_ranks = [1, 39, 250, 1000, 3939, 5000, 10000, 20000, 50000]

        for i, req in enumerate(general_ranks):
            rank = i + 1
            if achievement_general_rank >= rank:
                continue
            if guess_data["fail"] + guess_data["success"] >= req:
                await self.bot.add_achievement(message, "guess_general", rank=rank)
                return

        for i, req in enumerate(success_ranks):
            rank = i + 1
            if achievement_success_rank >= rank:
                continue
            if guess_data["success"] >= req:
                await self.bot.add_achievement(message, "guess_success", rank=rank)
                return

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if (
            "sbuga" in message.content.lower()
            or "ohshitohfuck" in message.content.lower()
        ) and (
            (
                message.guild.me.guild_permissions.add_reactions
                and message.channel.permissions_for(message.guild.me).add_reactions
            )
            if message.guild
            else True
        ):
            if (
                hasattr(self.bot, "FORCE_TROLL_REACT") and self.bot.FORCE_TROLL_REACT
            ) or random.randint(1, 700) == 3:
                self.bot.FORCE_TROLL_REACT = False
                reaction = (
                    "<:sbuga:1293557990397448285>"
                    if "sbuga" in message.content.lower()
                    else "<:KanadeJiiOhShitOhFuck:1160317226772086926>"
                )
                for _ in range(random.randint(3, 11)):
                    await message.add_reaction(reaction)
                    await asyncio.sleep(random.randint(1, 75) / 100)
                    try:
                        await message.remove_reaction(reaction, self.bot.user)
                    except:
                        pass
                    await asyncio.sleep(random.randint(1, 50) / 100)
                achievement = await self.bot.user_data.discord.has_achievement(
                    message.author.id, "trolled"
                )
                if not achievement:
                    await self.bot.add_achievement(message, "trolled")
        try:
            # flags to ease transition into prefix-based guessing, use the ones in __init__
            deprecate_old = False
            no_old = False
            use_prefix = False
            if self.bot.intents.message_content:
                deprecate_old = self.deprecate_ping
                no_old = self.no_ping
                use_prefix = self.use_prefix
            if message.content.startswith(self.bot.user.mention):
                guess_method = "ping"
                if no_old:
                    return
            elif message.content.startswith(self.guess_prefix):
                if not use_prefix:
                    return
                guess_method = "prefix"
            else:
                return
            if message.author.bot:
                return
            if guess_method == "ping":
                content = message.content.removeprefix(self.bot.user.mention).strip()
            else:
                content = message.content.removeprefix(self.guess_prefix).strip()
            if not content:
                return
            if guess_method == "ping" and (
                content.lower().startswith(
                    tuple([cmd.name for cmd in self.bot.commands])
                )
                and message.author.id in self.bot.owner_ids
            ):
                return
            if (
                self.bot.guess_channels.get(message.channel.id, {}).get(
                    "startTime", None
                )
                != None
            ):
                if message.author.id in self.bot.ban_cache:
                    banned = self.bot.ban_cache.get(message.author.id)
                else:
                    banned = await self.bot.user_data.discord.get_banned(
                        message.author.id
                    )
                    self.bot.ban_cache[message.author.id] = banned
                if banned:
                    await message.reply(
                        embed=embeds.error_embed(
                            "You're banned from the bot. Run </help:1326325488939040808> for links to the support server to appeal."
                        )
                    )
                    return
                try:
                    data = self.bot.guess_channels[message.channel.id]
                except KeyError:
                    return
                data["guessed"].append(message.author.id)
                if data["guessType"] == "song":
                    song = converters.SongFromPJSK(self.bot.pjsk, content)
                    if GuessCog.guess_ended(self.bot, data):
                        return
                    leak = (methods.Tools.isleak(song.id)) if song else False
                    if not song or leak:
                        embed = embeds.error_embed(
                            title="Incorrect",
                            description=await translations.other_context_translate(
                                locale_str(
                                    "errors.unknown_song",
                                    replacements={"{song}": content},
                                ),
                                message,
                                "en-US",
                                self.bot,
                            ),
                        )
                        if leak:
                            embed = embeds.leak_embed()
                        reply_embeds = [embed]
                        if guess_method == "ping" and deprecate_old:
                            reply_embeds.append(
                                embeds.warn_embed(
                                    f"Please stop pinging the bot to guess! We are transitioning to prefix-based guessing.\n\nUse `{self.guess_prefix}your guess here` to guess."
                                )
                            )
                        await message.reply(embeds=reply_embeds)
                        return
                    if (
                        song.id == data["answer"]
                        or (data["answer"] == 388 and song.id == 131)
                        or (data["answer"] == 131 and song.id == 388)
                    ):  # Gekishou append
                        self.remove_guess(self.bot, message.channel.id)
                        embed = embeds.success_embed(
                            title="Correct",
                            description=f"Successfully guessed **`{data['answerName']}`**!",
                        )
                        if data["data"].get("notes"):
                            embed.description += f"\n\n### This song has `{data['data']['notes']}` notes on Master."
                        view = get_view(self.bot, data)
                        reply_embeds = [embed]
                        if guess_method == "ping" and deprecate_old:
                            reply_embeds.append(
                                embeds.warn_embed(
                                    f"Please stop pinging the bot to guess! We are transitioning to prefix-based guessing.\n\nUse `{self.guess_prefix}your guess here` to guess."
                                )
                            )
                        files = []
                        if data["data"].get("thumbnail"):
                            file = discord.File(data["data"]["thumbnail"], "thumb.png")
                            files.append(file)
                            embed.set_thumbnail(url="attachment://thumb.png")
                        if data["answer_file_path"]:
                            if isinstance(data["answer_file_path"], io.BytesIO):
                                data["answer_file_path"].seek(0)
                            file = discord.File(data["answer_file_path"], "image.png")
                            files.append(file)
                            embed.set_image(url="attachment://image.png")
                        am_currency = int(
                            random.randint(3, 8)
                            * data["data"].get("success_modifier", 1)
                        )
                        am_experience = int(
                            random.randint(50, 200)
                            * data["data"].get("success_modifier", 1)
                        )
                        embed.add_field(
                            name="Rewards",
                            value=f"- Earned {am_currency:,} {emojis.sbugacoin} and {am_experience:,} XP!",
                            inline=False,
                        )
                        msg = await message.reply(embed=embed, view=view, files=files)
                        if data["guessing"]:
                            g_data = await self.bot.user_data.discord.add_guesses(
                                message.author.id,
                                data["guessing"],
                                "success",
                                return_all=True,
                            )
                            await self.handle_guess_achievement(message, g_data)
                        if view:
                            view.message = msg
                        await self.bot.add_currency(message, am_currency)
                        # await self.bot.add_experience(
                        #     message, am_experience, prog_bar=False
                        # )
                        await self.bot.grant_reward(message.author, "xp", am_experience)
                        return
                    else:
                        embed = embeds.error_embed(
                            title="Incorrect",
                            description=f"Incorrectly guessed **`{song.title}`**."
                            + (
                                f"\n-# Did you mean to guess **88☆彡**? `88` is the ID for **{song.title}**, so use `88s or 224` to guess **88☆彡**."
                                if content.strip() == "88" and song.id == 88
                                else (
                                    f"\n-# Did you mean to guess **「１」**? `1` is the ID for **{song.title}**, so use `[1] or 132` to guess **「１」**."
                                    if content.strip() == "1" and song.id == 1
                                    else ""
                                )
                            ),
                        )
                        if data["data"].get("notes"):
                            embed.description += f"\n\n### This song has `{song.difficulties.get('master', {}).get('totalNoteCount', 0)}` notes on Master."
                        files = []
                        jacket = methods.Tools.get_music_jacket(song.id)
                        if jacket:
                            file = discord.File(jacket, "image.png")
                            files.append(file)
                            embed.set_thumbnail(url="attachment://image.png")
                        reply_embeds = [embed]
                        if guess_method == "ping" and deprecate_old:
                            reply_embeds.append(
                                embeds.warn_embed(
                                    f"Please stop pinging the bot to guess! We are transitioning to prefix-based guessing.\n\nUse `{self.guess_prefix}your guess here` to guess."
                                )
                            )
                        songaliasview = views.SongAliasesButton(song.id)
                        songaliasview.timeout = 10
                        am_experience = random.randint(5, 10)
                        embed.set_footer(text=f"✨ +{am_experience} XP")
                        tip = random.randint(1, 20) == 7
                        if tip:
                            reply_embeds.append(random.choice(self.tip_embeds))
                        msg = await message.reply(
                            embeds=reply_embeds, files=files, view=songaliasview
                        )
                        songaliasview.message = msg
                        if data["guessing"]:
                            g_data = await self.bot.user_data.discord.add_guesses(
                                message.author.id,
                                data["guessing"],
                                "fail",
                                return_all=True,
                            )
                            await self.handle_guess_achievement(message, g_data)
                        # await self.bot.add_experience(
                        #     message, am_experience, prog_bar=False
                        # )
                        await self.bot.grant_reward(message.author, "xp", am_experience)
                        return
                if data["guessType"] == "character":
                    char = converters.CharFromPJSK(self.bot.pjsk, content)
                    if GuessCog.guess_ended(self.bot, data):
                        return
                    if not char:
                        embed = embeds.error_embed(
                            title="Incorrect",
                            description=await translations.other_context_translate(
                                locale_str(
                                    "errors.unknown_character",
                                    replacements={"{character}": content},
                                ),
                                message,
                                "en-US",
                                self.bot,
                            ),
                        )
                        reply_embeds = [embed]
                        if guess_method == "ping" and deprecate_old:
                            reply_embeds.append(
                                embeds.warn_embed(
                                    f"Please stop pinging the bot to guess! We are transitioning to prefix-based guessing.\n\nUse `{self.guess_prefix}your guess here` to guess."
                                )
                            )
                        await message.reply(embeds=reply_embeds)
                        return
                    if char["id"] == data["answer"]:
                        self.remove_guess(self.bot, message.channel.id)
                        embed = embeds.success_embed(
                            title="Correct",
                            description=f"Successfully guessed **`{data['answerName']}`**!\n**Card:** {data['data']['card_name']}",
                        )
                        view = get_view(self.bot, data)
                        reply_embeds = [embed]
                        if guess_method == "ping" and deprecate_old:
                            reply_embeds.append(
                                embeds.warn_embed(
                                    f"Please stop pinging the bot to guess! We are transitioning to prefix-based guessing.\n\nUse `{self.guess_prefix}your guess here` to guess."
                                )
                            )
                        files = []
                        if data["data"].get("thumbnail"):
                            file = discord.File(data["data"]["thumbnail"], "thumb.png")
                            files.append(file)
                            embed.set_thumbnail(url="attachment://thumb.png")
                        if data["answer_file_path"]:
                            if isinstance(data["answer_file_path"], io.BytesIO):
                                data["answer_file_path"].seek(0)
                            file = discord.File(data["answer_file_path"], "image.png")
                            files.append(file)
                            embed.set_image(url="attachment://image.png")
                        am_currency = int(
                            random.randint(3, 8)
                            * data["data"].get("success_modifier", 1)
                        )
                        am_experience = int(
                            random.randint(50, 200)
                            * data["data"].get("success_modifier", 1)
                        )
                        embed.add_field(
                            name="Rewards",
                            value=f"- Earned {am_currency:,} {emojis.sbugacoin} and {am_experience:,} XP!",
                            inline=False,
                        )
                        msg = await message.reply(embed=embed, view=view, files=files)
                        if data["guessing"]:
                            g_data = await self.bot.user_data.discord.add_guesses(
                                message.author.id,
                                data["guessing"],
                                "success",
                                return_all=True,
                            )
                            await self.handle_guess_achievement(message, g_data)
                        if view:
                            view.message = msg
                        await self.bot.add_currency(message, am_currency)
                        # await self.bot.add_experience(
                        #     message, am_experience, prog_bar=False
                        # )
                        await self.bot.grant_reward(message.author, "xp", am_experience)
                        return
                    else:
                        char_name = (
                            str(char["givenName"]) + " " + str(char["firstName"])
                            if char.get("firstName") and char.get("unit") != "piapro"
                            else (
                                str(char["firstName"]) + " " + str(char["givenName"])
                                if char.get("firstName")
                                else char["givenName"]
                            )
                        )
                        embed = embeds.error_embed(
                            title="Incorrect",
                            description=f"Incorrectly guessed **`{char_name}`**.",
                        )
                        files = []
                        card_path, card_id, trained = (
                            methods.pjsk_game_api_jp.random_character_card(
                                char["id"],
                                rarity=["rarity_1", "rarity_2", "rarity_birthday"],
                            )
                        )
                        file = discord.File(card_path, "image.png")
                        files.append(file)
                        embed.set_thumbnail(url="attachment://image.png")
                        reply_embeds = [embed]
                        if guess_method == "ping" and deprecate_old:
                            reply_embeds.append(
                                embeds.warn_embed(
                                    f"Please stop pinging the bot to guess! We are transitioning to prefix-based guessing.\n\nUse `{self.guess_prefix}your guess here` to guess."
                                )
                            )
                        am_experience = random.randint(5, 10)
                        embed.set_footer(text=f"✨ +{am_experience} XP")
                        tip = random.randint(1, 20) == 7
                        if tip:
                            reply_embeds.append(random.choice(self.tip_embeds))
                        await message.reply(embeds=reply_embeds, files=files)
                        if data["guessing"]:
                            g_data = await self.bot.user_data.discord.add_guesses(
                                message.author.id,
                                data["guessing"],
                                "fail",
                                return_all=True,
                            )
                            await self.handle_guess_achievement(message, g_data)
                        # await self.bot.add_experience(
                        #     message, am_experience, prog_bar=False
                        # )
                        await self.bot.grant_reward(message.author, "xp", am_experience)
                        return
                if data["guessType"] == "event":
                    event = converters.EventFromPJSK(self.bot.pjsk, content)
                    if GuessCog.guess_ended(self.bot, data):
                        return
                    if not event:
                        embed = embeds.error_embed(
                            title="Incorrect",
                            description=await translations.other_context_translate(
                                locale_str(
                                    "errors.unknown_event",
                                    replacements={"{event}": content},
                                ),
                                message,
                                "en-US",
                                self.bot,
                            ),
                        )
                        reply_embeds = [embed]
                        if guess_method == "ping" and deprecate_old:
                            reply_embeds.append(
                                embeds.warn_embed(
                                    f"Please stop pinging the bot to guess! We are transitioning to prefix-based guessing.\n\nUse `{self.guess_prefix}your guess here` to guess."
                                )
                            )
                        await message.reply(embeds=reply_embeds)
                        return
                    if event["id"] == data["answer"]:
                        self.remove_guess(self.bot, message.channel.id)
                        embed = embeds.success_embed(
                            title="Correct",
                            description=f"Successfully guessed **`{data['answerName']}`** (`{data['data']['short']}`)!",
                        )
                        view = get_view(self.bot, data)
                        reply_embeds = [embed]
                        if guess_method == "ping" and deprecate_old:
                            reply_embeds.append(
                                embeds.warn_embed(
                                    f"Please stop pinging the bot to guess! We are transitioning to prefix-based guessing.\n\nUse `{self.guess_prefix}your guess here` to guess."
                                )
                            )
                        files = []
                        if data["data"].get("thumbnail"):
                            file = discord.File(data["data"]["thumbnail"], "thumb.png")
                            files.append(file)
                            embed.set_thumbnail(url="attachment://thumb.png")
                        if data["answer_file_path"]:
                            if isinstance(data["answer_file_path"], io.BytesIO):
                                data["answer_file_path"].seek(0)
                            file = discord.File(data["answer_file_path"], "image.png")
                            files.append(file)
                            embed.set_image(url="attachment://image.png")
                        am_currency = int(
                            random.randint(3, 8)
                            * data["data"].get("success_modifier", 1)
                        )
                        am_experience = int(
                            random.randint(50, 200)
                            * data["data"].get("success_modifier", 1)
                        )
                        embed.add_field(
                            name="Rewards",
                            value=f"- Earned {am_currency:,} {emojis.sbugacoin} and {am_experience:,} XP!",
                            inline=False,
                        )
                        msg = await message.reply(embed=embed, view=view, files=files)
                        if data["guessing"]:
                            g_data = await self.bot.user_data.discord.add_guesses(
                                message.author.id,
                                data["guessing"],
                                "success",
                                return_all=True,
                            )
                            await self.handle_guess_achievement(message, g_data)
                        if view:
                            view.message = msg
                        await self.bot.add_currency(message, am_currency)
                        # await self.bot.add_experience(
                        #     message, am_experience, prog_bar=False
                        # )
                        await self.bot.grant_reward(message.author, "xp", am_experience)
                        return
                    else:
                        embed = embeds.error_embed(
                            title="Incorrect",
                            description=f"Incorrectly guessed **`{event['name']}`** (`{event['assetbundleName'].split('_')[1]}`).",
                        )
                        files = []
                        logo, _, _ = methods.Tools.get_event_images(
                            event["id"], methods.Tools.get_event_region(event["id"])
                        )
                        file = discord.File(logo, "image.png")
                        files.append(file)
                        embed.set_thumbnail(url="attachment://image.png")
                        reply_embeds = [embed]
                        tip = random.randint(1, 20) == 7
                        if guess_method == "ping" and deprecate_old:
                            reply_embeds.append(
                                embeds.warn_embed(
                                    f"Please stop pinging the bot to guess! We are transitioning to prefix-based guessing.\n\nUse `{self.guess_prefix}your guess here` to guess."
                                )
                            )
                        am_experience = random.randint(5, 10)
                        embed.set_footer(text=f"✨ +{am_experience} XP")
                        if tip:
                            reply_embeds.append(random.choice(self.tip_embeds))
                        await message.reply(embeds=reply_embeds, files=files)
                        if data["guessing"]:
                            g_data = await self.bot.user_data.discord.add_guesses(
                                message.author.id,
                                data["guessing"],
                                "fail",
                                return_all=True,
                            )
                            await self.handle_guess_achievement(message, g_data)
                        # await self.bot.add_experience(
                        #     message, am_experience, prog_bar=False
                        # )
                        await self.bot.grant_reward(message.author, "xp", am_experience)
                        return
        except Exception as e:
            self.bot.traceback(e)

    # endregion
    """
    
    ALL VIEWS

    """
    # region VIEWS

    class GuessEndWarning(views.SbotgaView):
        def __init__(
            self,
            bot: DiscordBot,
            data: dict,
            amount: int,
            first_time: bool = False,
            disabled: bool = False,
        ):
            super().__init__()
            self.first_time = first_time
            self.data = data
            self.bot = bot

            self.amount = amount

            if disabled:
                self.end.disabled = True
                self.cancel.disabled = True

        @discord.ui.button(
            label="labels.cancel",
            style=discord.ButtonStyle.primary,
        )
        async def cancel(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            if interaction.user.id != interaction.message.interaction_metadata.user.id:
                embed = embeds.error_embed(
                    await interaction.translate("errors.cannot_click")
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if not GuessCog.guess_ended(self.bot, self.data):
                embed = embeds.embed(
                    title="Guess Continued",
                    description="Continuing guess.",
                    color=discord.Color.blue(),
                )
            else:
                embed = embeds.error_embed(
                    title="Guess Already Ended",
                    description=f"The guess was already ended; no {emojis.sbugacoin} were paid.",
                )
                await interaction.response.edit_message(embed=embed, view=None)
                return
            await interaction.response.edit_message(embed=embed, view=None)
            if self.first_time:
                await self.bot.user_data.discord.change_settings(
                    interaction.user.id, "first_time_guess_end", False
                )

        @discord.ui.button(
            label="labels.end_guess",
            style=discord.ButtonStyle.danger,
        )
        async def end(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            if interaction.user.id != interaction.message.interaction_metadata.user.id:
                embed = embeds.error_embed(
                    await interaction.translate("errors.cannot_click")
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            await interaction.response.defer()
            wallet = await self.bot.user_data.discord.get_currency(interaction.user.id)
            if wallet >= self.amount:
                pass
            else:
                return await interaction.followup.edit_message(
                    interaction.message.id,
                    embed=embeds.error_embed(
                        f"You only have **{wallet:,}** {emojis.sbugacoin} and need **{self.amount}** {emojis.sbugacoin} to end the guess."
                    ),
                )

            embed, files, view = GuessCog.generate_guess_end(
                self.bot, self.data, paid=self.amount, new=wallet - self.amount
            )
            await interaction.followup.edit_message(
                interaction.message.id,
                embed=embed,
                attachments=files,
                view=view,
            )
            if view:
                view.message = interaction.message
            if not GuessCog.guess_ended(self.bot, self.data):
                GuessCog.remove_guess(self.bot, interaction.channel.id)
            if self.first_time:
                await self.bot.user_data.discord.change_settings(
                    interaction.user.id, "first_time_guess_end", False
                )
            if self.data["guessing"]:
                await self.bot.user_data.discord.add_guesses(
                    interaction.user.id, self.data["guessing"], "ragequit"
                )
                await self.bot.user_data.discord.add_currency(
                    interaction.user.id, int(self.amount * -1)
                )

    class LeaderboardView(views.SbotgaView):
        def __init__(
            self,
            current_page: int,
            total_pages: int,
            guess_type: str,
            bot: DiscordBot,
        ):
            super().__init__()
            self.current_page = current_page
            self.total_pages = total_pages
            self.guess_type = guess_type
            self.bot = bot
            self.update_buttons()

        def update_buttons(self):
            self.previous_page.disabled = self.current_page == 1
            self.next_page.disabled = self.current_page == self.total_pages

        async def update_message(self, interaction: discord.Interaction):
            leaderboard, user_position, user_page, total_pages = (
                await self.bot.user_data.discord.get_guesses_leaderboard(
                    self.guess_type, self.current_page, interaction.user.id
                )
            )
            self.total_pages = total_pages
            embed = await GuessCog.create_leaderboard_embed(
                page=self.current_page,
                total_pages=total_pages,
                guess_type_name=TYPE_TO_NAME[self.guess_type],
                data=leaderboard,
                user_specific=[user_position, user_page],
                bot=self.bot,
            )
            self.update_buttons()
            try:
                await interaction.followup.edit_message(
                    interaction.message.id, embed=embed, view=self
                )
            except Exception as e:
                print(e)

        @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.primary)
        async def previous_page(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            if interaction.user.id != interaction.message.interaction_metadata.user.id:
                embed = embeds.error_embed(
                    await interaction.translate("errors.cannot_click")
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            await interaction.response.defer()
            if self.current_page > 1:
                self.current_page -= 1
                await self.update_message(interaction)

        @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.primary)
        async def next_page(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            if interaction.user.id != interaction.message.interaction_metadata.user.id:
                embed = embeds.error_embed(
                    await interaction.translate("errors.cannot_click")
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            await interaction.response.defer()
            if self.current_page < self.total_pages:
                self.current_page += 1
                await self.update_message(interaction)

    # endregion
    """
    
    GUESS COMMANDS
    
    """

    guess = app_commands.Group(
        name=locale_str("guess", key="guess.name", file="commands"),
        description=locale_str("guess.desc", file="commands"),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
    )

    """
    MISC (stats, leaderboard, end, hint)
    """
    # region GUESSING MISC

    @guess.command(
        auto_locale_strings=False,
        name=locale_str("stats", key="guess.cmds.stats.name", file="commands"),
        description=locale_str("guess.cmds.stats.desc", file="commands"),
    )
    @app_commands.describe(
        guess_type=locale_str("guess.cmds.stats.describes.guess_type", file="commands"),
        user=locale_str("guess.cmds.stats.describes.user", file="commands"),
        lb_rank=locale_str("guess.cmds.stats.describes.lb_rank", file="commands"),
    )
    @app_commands.autocomplete(
        guess_type=autocompletes.autocompletes.pjsk_guessing_types,
        lb_rank=autocompletes.autocompletes.range(1, "inf"),
    )
    async def guess_stats(
        self,
        interaction: discord.Interaction,
        guess_type: str,
        lb_rank: int = None,
        user: discord.User = None,
    ):
        save_user_name(interaction.user.id, interaction.user.name)
        if user and lb_rank:
            return await interaction.response.send_message(
                embed=embeds.error_embed("Cannot use both user and lb_rank options."),
                ephemeral=True,
            )
        if not user and not lb_rank:
            user = interaction.user
        guess_type = guess_type.lower().strip()

        # Validate the guess_type
        if guess_type not in TYPE_TO_NAME.keys():
            return await interaction.response.send_message(
                embed=embeds.error_embed(
                    "Unsupported guess type.\n-# Not all guessing saves stats!"
                ),
                ephemeral=True,
            )

        await interaction.response.defer(thinking=True)

        if lb_rank:
            user = await self.bot.user_data.discord.get_guesses_at_rank(
                guess_type, lb_rank
            )
            if not user:
                return await interaction.response.send_message(
                    embed=embeds.error_embed(f"No user at rank **#{lb_rank:,}**!"),
                    ephemeral=True,
                )
            else:
                user = self.bot.get_user(user["discord_id"]) or (
                    await self.bot.fetch_user(user["discord_id"])
                )

        data = await self.bot.user_data.discord.get_guesses(user.id, guess_type)
        pos, page = await self.bot.user_data.discord.get_guesses_position(
            guess_type, user.id
        )
        """
        {"fail": 0, "success": 0, "ragequit": 0, "hint": 0}
        """

        embed = embeds.embed(
            title=f"{tools.escape_md(user.name)}'s {TYPE_TO_NAME[guess_type]} Guess Stats",
            color=discord.Color.purple(),
        )
        score = data["success"]
        neg = ""
        rank = (
            f"Rank #{pos} (`{neg}{data['success']}` Point{'s' if data['success'] != 1 else ''})"
            if pos != 0
            else "Not Ranked"
        )
        guess_rate = (
            f"`{(data['success']/(data['fail'] + data['success']))*100:.2f}`%"
            if (data["success"] + data["fail"]) != 0
            else "Never Guessed Before"
        )
        embed.description = f"## {rank}\n\n**Total Guesses:** `{data['fail'] + data['success']:,}`\n**Guess Rate:** {guess_rate}\n\n**Rage Quits:** {data['ragequit']:,}\n**Hints Used:** {data['hint']:,}\n\n**Successful Guesses:** {data['success']}\n**Failed Guesses:** {data['fail']}\n\n-# Points is your successes."
        embed.set_thumbnail(url=user.display_avatar.url)

        return await interaction.followup.send(embed=embed)

    @guess.command(
        auto_locale_strings=False,
        name=locale_str(
            "leaderboard", key="guess.cmds.leaderboard.name", file="commands"
        ),
        description=locale_str("guess.cmds.leaderboard.desc", file="commands"),
    )
    @app_commands.describe(
        guess_type=locale_str(
            "guess.cmds.leaderboard.describes.guess_type", file="commands"
        ),
        page=locale_str("general.page"),
    )
    @app_commands.autocomplete(
        guess_type=autocompletes.autocompletes.pjsk_guessing_types,
        page=autocompletes.autocompletes.range(1, "inf"),
    )
    async def guess_leaderboard(
        self, interaction: discord.Interaction, guess_type: str, page: int = 1
    ):
        guess_type = guess_type.lower().strip()

        # Validate the guess_type
        if guess_type not in TYPE_TO_NAME.keys():
            return await interaction.response.send_message(
                embed=embeds.error_embed(
                    "Unsupported guess type.\n-# Not all guessing has a leaderboard!"
                ),
                ephemeral=True,
            )

        if page < 1:
            return await interaction.response.send_message(
                embed=embeds.error_embed("Page number must be at least 1."),
                ephemeral=True,
            )

        await interaction.response.defer(thinking=True)

        leaderboard, user_position, user_page, total_pages = (
            await self.bot.user_data.discord.get_guesses_leaderboard(
                guess_type, page, interaction.user.id
            )
        )
        if page > total_pages > 0:
            return await interaction.followup.send(
                embed=embeds.error_embed(
                    f"Invalid page number. There are only {total_pages} pages available."
                )
            )

        embed = await self.create_leaderboard_embed(
            page=page,
            total_pages=total_pages,
            guess_type_name=TYPE_TO_NAME[guess_type],
            data=leaderboard,
            user_specific=[user_position, user_page],
            bot=self.bot,
        )
        view = self.LeaderboardView(
            current_page=page,
            total_pages=total_pages,
            guess_type=guess_type,
            bot=self.bot,
        )
        await view.translate(interaction)
        await interaction.followup.send(embed=embed, view=view)
        view.message = await interaction.original_response()

    @guess.command(
        auto_locale_strings=False,
        name="end",
        description="Rage-quit your current guess.",
    )
    @app_commands.guild_only()
    async def end_guess(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        if not (await self.channel_checks(interaction, already_guessing_check=False)):
            return
        data = self.bot.guess_channels.get(interaction.channel.id)
        if not data:
            embed = embeds.error_embed("No ongoing guess.")
            await interaction.followup.send(embed=embed)
            return
        if interaction.user.id not in data["guessed"]:
            return await interaction.followup.send(
                embed=embeds.error_embed(
                    "You can't end this guess! You haven't even tried to guess."
                )
            )
        amount = 15  # sbugacoin pay amount
        settings = await self.bot.user_data.discord.get_settings(interaction.user.id)
        if data["guessing"]:
            embed = embeds.warn_embed("", title="Ending Guess")
            if settings.get("first_time_guess_end"):
                embed.description = f"**Are you sure you want to end this guess?**\nThis will cost you 20 {emojis.sbugacoin}.\n-# This is your first time seeing this warning, so you cannot skip this for 10 seconds."
                view = self.GuessEndWarning(
                    self.bot, data, amount, first_time=True, disabled=True
                )
                await view.translate(interaction)
                await interaction.followup.send(
                    embed=embed,
                    view=view,
                )
                msg = await interaction.original_response()
                view.message = msg
                embed.description = f"**Are you sure you want to end this guess?**\nThis will cost you {amount:,} {emojis.sbugacoin}.\n-# This is your first time seeing this warning."
                await asyncio.sleep(10)
                view = self.GuessEndWarning(self.bot, data, amount, first_time=True)
                await view.translate(interaction)
                view.message = msg
                return await msg.edit(
                    embed=embed,
                    view=view,
                )
            else:
                embed.description = f"**Are you sure you want to end this guess?**\nThis will cost you {amount:,} {emojis.sbugacoin}."
                view = self.GuessEndWarning(self.bot, data, amount, first_time=False)
                await view.translate(interaction)
                await interaction.followup.send(
                    embed=embed,
                    view=view,
                )
                view.message = await interaction.original_response()
                return
        embed, files, view = self.generate_guess_end(self.bot, data)
        await interaction.followup.send(embed=embed, files=files, view=view)
        if view:
            view.message = await interaction.original_response()
        if data["guessing"]:
            await self.bot.user_data.discord.add_guesses(
                interaction.user.id, data["guessing"], "ragequit"
            )
        self.remove_guess(self.bot, interaction.channel.id)

    @guess.command(
        auto_locale_strings=False,
        name=locale_str("hint", key="guess.cmds.hint.name", file="commands"),
        description=locale_str("guess.cmds.hint.desc", file="commands"),
    )
    @app_commands.guild_only()
    async def guess_hint(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        if not (await self.channel_checks(interaction, already_guessing_check=False)):
            return
        data = self.bot.guess_channels.get(interaction.channel.id)
        if not data:
            embed = embeds.error_embed(
                f"No ongoing guess.",
            )
            await interaction.followup.send(embed=embed)
            return
        try:
            if data["guessType"] == "song":
                song_id = data["answer"]
                if song_id == 388:  # Gekishou append
                    song_id = 131
                diff = self.bot.pjsk.difficulties[song_id]["master"]["playLevel"]
                if type(diff) == list:
                    diff = diff[1]
                embed = embeds.embed(
                    title="Guess Hint",
                    description=f"The song is level **`{diff}`** (after any rerates) on {emojis.difficulty_colors['master']} **Master**.",
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=embed)
                if data["guessing"]:
                    await self.bot.user_data.discord.add_guesses(
                        interaction.user.id, data["guessing"], "hint"
                    )
            elif data["guessType"] == "character":
                trained = data["data"]["trained"]
                embed = embeds.embed(
                    title="Guess Hint",
                    description=f"The character card is **`{'trained' if trained else 'not trained'}`**.",
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=embed)
                if data["guessing"]:
                    await self.bot.user_data.discord.add_guesses(
                        interaction.user.id, data["guessing"], "hint"
                    )
            elif data["guessType"] == "event":
                embed = embeds.embed(
                    title="Guess Hint",
                    description=f"Here is a character featured in this event.",
                    color=discord.Color.red(),
                )
                files = []
                _, _, char = methods.Tools.get_event_images(
                    data["answer"], methods.Tools.get_event_region(data["answer"])
                )
                file = discord.File(char, "image.png")
                files.append(file)
                embed.set_image(url="attachment://image.png")
                await interaction.followup.send(embed=embed, files=files)
                if data["guessing"]:
                    await self.bot.user_data.discord.add_guesses(
                        interaction.user.id, data["guessing"], "hint"
                    )
            else:
                embed = embeds.embed(
                    title="Unsupported Hint",
                    description=f"Ongoing guess does not support hints.",
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=embed)
                return
        except:
            pass

    # endregion
    """
    CODE FOR GUESSING
    """

    # region GUESS INTERACTION CODE
    async def handle_guess(
        self, interaction: discord.Interaction, guessing: str
    ) -> None:
        not_counted_warning = "\n\n-# This guessing mode is not counted for leaderboard. You cannot earn standard guessing achievements from this guessing mode."
        try:
            await interaction.response.defer(thinking=True)
        except discord.InteractionResponded:
            pass
        if not (await self.channel_checks(interaction)):
            return
        new_guess = {
            "func": self.handle_guess,
            "guessed": [],
            "channel": interaction.channel,
            "id": None,
            "guessType": None,
            "guessing": guessing,
            "answer_file_path": None,
            "answer": None,
            "answerName": None,
            "startTime": None,
            "data": {"success_modifier": 1},
        }
        new_id = generate_secure_string(25)
        while new_id in self.bot.existing_guess_ids:
            new_id = generate_secure_string(25)
        self.bot.existing_guess_ids.append(new_id)
        new_guess["id"] = new_id
        self.bot.guess_channels[interaction.channel.id] = new_guess
        user_settings = await interaction.client.user_data.discord.get_settings(
            interaction.user.id
        )

        async def random_chart(diff: str = "master") -> Tuple[Song, str, str]:
            for _ in range(10):  # maximum 10 retries
                try:
                    if diff == "master":
                        song = self.random_song()
                    else:
                        song = self.random_song(has_append=True)
                    region = methods.Tools.get_music_region(song.id, "en")
                    png = await methods.Tools.get_chart(
                        diff,
                        song.id,
                        server=region,
                    )
                    break
                except IndexError:
                    pass
            return song, png, region

        def random_jacket(has_master: bool = False) -> Tuple[Song, str]:
            song = self.random_song()
            jacket_path = methods.Tools.get_music_jacket(song.id)
            for _ in range(10):  # maximum 10 retries
                if (
                    (not jacket_path)
                    or (not os.path.exists(jacket_path))
                    or (has_master and not song.difficulties.get("master"))
                ):
                    song = self.random_song()
                    jacket_path = methods.Tools.get_music_jacket(song.id)
                else:
                    break
            return song, jacket_path

        def random_card_rare() -> Tuple[dict, str, int, bool, int]:
            """char, card_path, char_id, trained, card_id"""
            api = methods.pjsk_game_api_jp

            def da_works():
                char_id, asset_name, card_id, rarity = self.random_card()
                if rarity == "rarity_birthday":
                    path2 = "normal"
                    trained = False
                else:
                    trained = not random.randint(0, 1)
                    if trained:
                        path2 = "after_training"
                    else:
                        path2 = "normal"
                card_path = os.path.join(
                    api.game_files_path,
                    api.app_region,
                    "character",
                    "member",
                    f"{asset_name}_ex",
                    f"card_{path2}.png",
                )
                return card_path, char_id, asset_name, card_id, rarity, trained

            card_path, char_id, asset_name, card_id, rarity, trained = da_works()
            for _ in range(10):
                if (not card_path) or (not os.path.exists(card_path)):
                    card_path, char_id, asset_name, card_id, rarity, trained = (
                        da_works()
                    )
                else:
                    break
            char = self.bot.pjsk.characters_game[char_id - 1]
            return char, card_path, char_id, trained, card_id

        try:
            match guessing:
                case "jacket":
                    new_guess["guessType"] = "song"

                    song, jacket_path = random_jacket()

                    new_guess["answer_file_path"] = jacket_path
                    new_guess["answer"] = song.id
                    new_guess["answerName"] = song.title

                    edited_image = await self.random_crop(jacket_path)

                    embed = embeds.embed(
                        title="Guess The Song", color=discord.Color.dark_gold()
                    )
                    edited_image.seek(0)
                    file = discord.File(edited_image, "image.png")
                    embed.set_image(url="attachment://image.png")
                    embed.description = f"Guess song name based on a cropped jacket.\nUse {('**'+self.bot.user.mention+'` ') if ((not self.bot.intents.message_content) and self.use_prefix) else ('**`' + self.guess_prefix)}your guess`** to guess. You have 60 seconds."
                    # debugging, comment this for prod
                    # embed.description += f"\ndebug - answer `{song.title}` (`{song.id}`)"

                case "jacket_30px":
                    new_guess["guessType"] = "song"
                    new_guess["data"]["success_modifier"] = 1.2

                    song, jacket_path = random_jacket()

                    new_guess["answer_file_path"] = jacket_path
                    new_guess["answer"] = song.id
                    new_guess["answerName"] = song.title

                    edited_image = await self.random_crop(jacket_path, size=30)

                    embed = embeds.embed(
                        title="Guess The Song", color=discord.Color.dark_gold()
                    )
                    edited_image.seek(0)
                    file = discord.File(edited_image, "image.png")
                    embed.set_image(url="attachment://image.png")
                    embed.description = f"**30px Jacket Guess!** Guess song name based on cropped jacket.\nUse {('**'+self.bot.user.mention+'` ') if ((not self.bot.intents.message_content) and self.use_prefix) else ('**`' + self.guess_prefix)}your guess`** to guess. You have 60 seconds."
                    # debugging, comment this for prod
                    # embed.description += f"\ndebug - answer `{song.title}` (`{song.id}`)"
                case "jacket_bw":
                    new_guess["guessType"] = "song"
                    new_guess["data"]["success_modifier"] = 1.1

                    song, jacket_path = random_jacket()

                    new_guess["answer_file_path"] = jacket_path
                    new_guess["answer"] = song.id
                    new_guess["answerName"] = song.title

                    edited_image = await self.random_crop(jacket_path, bw=True)
                    embed = embeds.embed(
                        title="Guess The Song", color=discord.Color.dark_gold()
                    )
                    edited_image.seek(0)
                    file = discord.File(edited_image, "image.png")
                    embed.set_image(url="attachment://image.png")
                    embed.description = f"**Grayscale Jacket Guess!** Guess song name based on cropped jacket.\nUse {('**'+self.bot.user.mention+'` ') if ((not self.bot.intents.message_content) and self.use_prefix) else ('**`' + self.guess_prefix)}your guess`** to guess. You have 60 seconds."
                    # debugging, comment this for prod
                    # embed.description += f"\ndebug - answer `{song.title}` (`{song.id}`)"
                case "jacket_challenge":
                    new_guess["guessType"] = "song"
                    new_guess["data"]["success_modifier"] = 5

                    song, jacket_path = random_jacket()

                    new_guess["answer_file_path"] = jacket_path
                    new_guess["answer"] = song.id
                    new_guess["answerName"] = song.title

                    edited_image = await self.random_crop(jacket_path, size=30, bw=True)
                    embed = embeds.embed(
                        title="Guess The Song", color=discord.Color.dark_gold()
                    )
                    edited_image.seek(0)
                    file = discord.File(edited_image, "image.png")
                    embed.set_image(url="attachment://image.png")
                    embed.description = f"**CHALLENGE JACKET GUESS!** Guess song name based on cropped *grayscale 30px* jacket.\nUse {('**'+self.bot.user.mention+'` ') if ((not self.bot.intents.message_content) and self.use_prefix) else ('**`' + self.guess_prefix)}your guess`** to guess. You have 60 seconds."  # {not_counted_warning}"
                    # debugging, comment this for prod
                    # embed.description += f"\ndebug - answer `{song.title}` (`{song.id}`)"
                case "character":
                    new_guess["guessType"] = "character"

                    char, card_path, char_id, trained, card_id = random_card_rare()

                    new_guess["answer_file_path"] = card_path
                    new_guess["answer"] = char_id
                    new_guess["answerName"] = (
                        str(char["givenName"]) + " " + str(char["firstName"])
                        if char.get("firstName") and char.get("unit") != "piapro"
                        else (
                            str(char["firstName"]) + " " + str(char["givenName"])
                            if char.get("firstName")
                            else char["givenName"]
                        )
                    )
                    new_guess["data"]["card_id"] = card_id
                    new_guess["data"]["trained"] = trained
                    new_guess["data"]["card_name"] = methods.Tools.get_card_name(
                        card_id, trained, include_character=True, use_emojis=True
                    )

                    edited_image = await self.random_crop_rectangle(card_path)
                    embed = embeds.embed(
                        title="Guess The Character", color=discord.Color.dark_gold()
                    )
                    edited_image.seek(0)
                    file = discord.File(edited_image, "image.png")
                    embed.set_image(url="attachment://image.png")
                    embed.description = f"Guess character name based on cropped card.\nUse {('**'+self.bot.user.mention+'` ') if ((not self.bot.intents.message_content) and self.use_prefix) else ('**`' + self.guess_prefix)}your guess`** to guess. You have 30 seconds."
                    # debugging, comment this for prod
                    # embed.description += f"\ndebug - answer `{song.title}` (`{song.id}`)"
                case "character_bw":
                    new_guess["guessType"] = "character"
                    new_guess["data"]["success_modifier"] = 1.25

                    char, card_path, char_id, trained, card_id = random_card_rare()

                    new_guess["answer_file_path"] = card_path
                    new_guess["answer"] = char_id
                    new_guess["answerName"] = (
                        str(char["givenName"]) + " " + str(char["firstName"])
                        if char.get("firstName") and char.get("unit") != "piapro"
                        else (
                            str(char["firstName"]) + " " + str(char["givenName"])
                            if char.get("firstName")
                            else char["givenName"]
                        )
                    )
                    new_guess["data"]["card_id"] = card_id
                    new_guess["data"]["trained"] = trained
                    new_guess["data"]["card_name"] = methods.Tools.get_card_name(
                        card_id, trained, include_character=True, use_emojis=True
                    )

                    edited_image = await self.random_crop_rectangle(card_path, bw=True)
                    embed = embeds.embed(
                        title="Guess The Character", color=discord.Color.dark_gold()
                    )
                    edited_image.seek(0)
                    file = discord.File(edited_image, "image.png")
                    embed.set_image(url="attachment://image.png")
                    embed.description = f"**Grayscale Character Guess!** Guess character name based on cropped card.\nUse {('**'+self.bot.user.mention+'` ') if ((not self.bot.intents.message_content) and self.use_prefix) else ('**`' + self.guess_prefix)}your guess`** to guess. You have 30 seconds."
                    # debugging, comment this for prod
                    # embed.description += f"\ndebug - answer `{song.title}` (`{song.id}`)"
                case "chart":
                    new_guess["guessType"] = "song"
                    new_guess["data"]["success_modifier"] = 2

                    song, png, region = await random_chart()
                    if user_settings["mirror_charts_by_default"]:
                        png = await to_process_with_timeout(pjsk_chart.mirror, png)

                    new_guess["answer_file_path"] = png
                    new_guess["answer"] = song.id
                    new_guess["answerName"] = song.title
                    new_guess["data"]["diff"] = "master"
                    new_guess["data"]["region"] = region
                    new_guess["data"]["is_chart"] = True

                    edited_image = await self.random_crop_chart(png)
                    embed = embeds.embed(
                        title="Guess The Chart", color=discord.Color.dark_gold()
                    )
                    edited_image.seek(0)
                    file = discord.File(edited_image, "image.png")
                    embed.set_image(url="attachment://image.png")

                    embed.description = (
                        f"Guess song name based on cropped master chart.\nUse {('**'+self.bot.user.mention+'` ') if ((not self.bot.intents.message_content) and self.use_prefix) else ('**`' + self.guess_prefix)}your guess`** to guess. You have 60 seconds."
                        + (
                            "\n\n**Chart is mirrored! (user settings)**"
                            if user_settings["mirror_charts_by_default"]
                            else ""
                        )
                    )
                    # debugging, comment this for prod
                    # embed.description += f"\ndebug - answer `{song.title}` (`{song.id}`)"
                case "chart_append":
                    new_guess["guessType"] = "song"

                    song, png, region = await random_chart("append")
                    if user_settings["mirror_charts_by_default"]:
                        png = await to_process_with_timeout(pjsk_chart.mirror, png)

                    new_guess["answer_file_path"] = png
                    new_guess["answer"] = song.id
                    new_guess["answerName"] = song.title
                    new_guess["data"]["diff"] = "append"
                    new_guess["data"]["region"] = region
                    new_guess["data"]["is_chart"] = True

                    edited_image = await self.random_crop_chart(png)
                    embed = embeds.embed(
                        title="Guess The Chart", color=discord.Color.dark_gold()
                    )
                    edited_image.seek(0)
                    file = discord.File(edited_image, "image.png")
                    embed.set_image(url="attachment://image.png")

                    embed.description = (
                        f"Guess song name based on cropped append chart.\nUse {('**'+self.bot.user.mention+'` ') if ((not self.bot.intents.message_content) and self.use_prefix) else ('**`' + self.guess_prefix)}your guess`** to guess. You have 20 seconds."
                        + (
                            "\n\n**Chart is mirrored! (user settings)**"
                            if user_settings["mirror_charts_by_default"]
                            else ""
                        )
                    )
                    # debugging, comment this for prod
                    # embed.description += f"\ndebug - answer `{song.title}` (`{song.id}`)"
                case "event":
                    new_guess["guessType"] = "event"
                    new_guess["data"]["success_modifier"] = 1.1

                    for _ in range(10):  # maximum 10 retries
                        try:
                            event = self.random_event(en_only=True)
                            thumbnail, png, _ = methods.Tools.get_event_images(
                                event["id"], methods.Tools.get_event_region(event["id"])
                            )
                            break
                        except IndexError as e:
                            print(e)
                            pass

                    new_guess["answer_file_path"] = png
                    new_guess["data"]["thumbnail"] = thumbnail
                    new_guess["answer"] = event["id"]
                    new_guess["answerName"] = event["name"]
                    new_guess["data"]["short"] = event["assetbundleName"].split("_")[1]

                    edited_image = await self.random_crop_rectangle(png)
                    embed = embeds.embed(
                        title="Guess The Event", color=discord.Color.dark_gold()
                    )
                    edited_image.seek(0)
                    file = discord.File(edited_image, "image.png")
                    embed.set_image(url="attachment://image.png")

                    embed.description = f"Guess event name based on cropped event background.\nUse {('**'+self.bot.user.mention+'` ') if ((not self.bot.intents.message_content) and self.use_prefix) else ('**`' + self.guess_prefix)}your guess`** to guess. You have 60 seconds.\n\n-# Note: EN only events will show up. No specific aliases."
                    # debugging, comment this for prod
                    # embed.description += f"\ndebug - answer `{event['name']}` (`{event['id']}`, `{event['assetbundleName']}`)"
                case "notes":
                    new_guess["guessType"] = "song"
                    new_guess["data"]["success_modifier"] = 2

                    song, jacket_path = random_jacket(has_master=True)

                    new_guess["answer_file_path"] = None
                    new_guess["answer"] = song.id
                    new_guess["answerName"] = song.title
                    new_guess["data"]["notes"] = song.difficulties["master"][
                        "totalNoteCount"
                    ]
                    new_guess["data"]["thumbnail"] = jacket_path

                    embed = embeds.embed(
                        title="Guess The Song", color=discord.Color.dark_gold()
                    )
                    file = discord.utils.MISSING
                    embed.description = f"Guess song name based on Master note count.\nUse {('**'+self.bot.user.mention+'` ') if ((not self.bot.intents.message_content) and self.use_prefix) else ('**`' + self.guess_prefix)}your guess`** to guess. You have 60 seconds.\n\n# This song has `{new_guess['data']['notes']}` notes on Master."
                    # debugging, comment this for prod
                    # embed.description += f"\ndebug - answer `{song.title}` (`{song.id}`)"

            await interaction.followup.send(embed=embed, file=file)
            new_guess["startTime"] = time.time()
        except (
            Exception
        ) as e:  # it errored and we don't want to permanently block this channel
            self.remove_guess(self.bot, interaction.channel.id)
            raise e

    # endregion
    """
    TOGGLE GUESSING
    """
    # region TOGGLING

    @guess.command(
        auto_locale_strings=False,
        name=locale_str("toggle", key="guess.cmds.toggle.name", file="commands"),
        description=locale_str("guess.cmds.toggle.desc", file="commands"),
    )
    @app_commands.describe(
        on=locale_str("guess.cmds.toggle.describes.on", file="commands")
    )
    @app_commands.guild_only()
    async def toggle_guessing(self, interaction: discord.Interaction, on: bool):
        await interaction.response.defer()
        if interaction.user.guild_permissions.manage_guild:
            state = await self.bot.user_data.discord.toggle_guessing(
                interaction.guild_id, on
            )
            return await interaction.followup.send(
                embed=embeds.success_embed(
                    f"Guessing is now **{'ON' if state else 'OFF'}**!"
                )
            )
        else:
            return await interaction.followup.send(
                embed=embeds.error_embed(
                    "You need the `Manage Server` permission to do this!"
                )
            )

    # endregion
    """
    GUESSING
    """
    # region GUESSING

    @guess.command(
        auto_locale_strings=False,
        name=locale_str("jacket", key="guess.cmds.jacket.name", file="commands"),
        description=locale_str("guess.cmds.jacket.desc", file="commands"),
    )
    @app_commands.guild_only()
    async def jacket_guess(self, interaction: discord.Interaction):
        if self.bot.downloading_jackets:
            embed = embeds.error_embed(
                f"I'm currently refreshing all my jackets. Please be patient and try again in a minute.",
            )
            await interaction.response.send_message(embed=embed)
            return
        await self.handle_guess(interaction, "jacket")

    @guess.command(
        auto_locale_strings=False,
        name=locale_str(
            "jacket_smol", key="guess.cmds.jacket_smol.name", file="commands"
        ),
        description=locale_str("guess.cmds.jacket_smol.desc", file="commands"),
    )
    @app_commands.guild_only()
    async def guess_30px(self, interaction: discord.Interaction):
        if self.bot.downloading_jackets:
            embed = embeds.error_embed(
                f"I'm currently refreshing all my jackets. Please be patient and try again in a minute.",
            )
            await interaction.response.send_message(embed=embed)
            return
        await self.handle_guess(interaction, "jacket_30px")

    @guess.command(
        auto_locale_strings=False,
        name=locale_str("jacket_bw", key="guess.cmds.jacket_bw.name", file="commands"),
        description=locale_str("guess.cmds.jacket_bw.desc", file="commands"),
    )
    @app_commands.guild_only()
    async def guess_bw(self, interaction: discord.Interaction):
        if self.bot.downloading_jackets:
            embed = embeds.error_embed(
                f"I'm currently refreshing all my jackets. Please be patient and try again in a minute.",
            )
            await interaction.response.send_message(embed=embed)
            return
        await self.handle_guess(interaction, "jacket_bw")

    @guess.command(
        auto_locale_strings=False,
        name=locale_str(
            "jacket_challenge", key="guess.cmds.jacket_challenge.name", file="commands"
        ),
        description=locale_str("guess.cmds.jacket_challenge.desc", file="commands"),
    )
    @app_commands.guild_only()
    async def guess_bw_30px(self, interaction: discord.Interaction):
        if self.bot.downloading_jackets:
            embed = embeds.error_embed(
                f"I'm currently refreshing all my jackets. Please be patient and try again in a minute.",
            )
            await interaction.response.send_message(embed=embed)
            return
        await self.handle_guess(interaction, "jacket_challenge")

    @guess.command(
        auto_locale_strings=False,
        name=locale_str("character", key="guess.cmds.character.name", file="commands"),
        description=locale_str("guess.cmds.character.desc", file="commands"),
    )
    @app_commands.guild_only()
    async def guess_character(self, interaction: discord.Interaction):
        if self.bot.downloading_cards:
            embed = embeds.error_embed(
                f"I'm currently refreshing all my character cards. Please be patient and try again in a minute.",
            )
            await interaction.response.send_message(embed=embed)
            return
        await self.handle_guess(interaction, "character")

    @guess.command(
        auto_locale_strings=False,
        name=locale_str(
            "character_bw", key="guess.cmds.character_bw.name", file="commands"
        ),
        description=locale_str("guess.cmds.character_bw.desc", file="commands"),
    )
    @app_commands.guild_only()
    async def guess_character_bw(self, interaction: discord.Interaction):
        if self.bot.downloading_cards:
            embed = embeds.error_embed(
                f"I'm currently refreshing all my character cards. Please be patient and try again in a minute.",
            )
            await interaction.response.send_message(embed=embed)
            return
        await self.handle_guess(interaction, "character_bw")

    @guess.command(
        auto_locale_strings=False,
        name=locale_str("chart", key="guess.cmds.chart.name", file="commands"),
        description=locale_str("guess.cmds.chart.desc", file="commands"),
    )
    @app_commands.guild_only()
    async def guess_chart(self, interaction: discord.Interaction):
        if self.bot.downloading_charts:
            embed = embeds.error_embed(
                f"I'm currently refreshing all my charts. Please be patient and try again in a minute.",
            )
            await interaction.response.send_message(embed=embed)
            return
        await self.handle_guess(interaction, "chart")

    @guess.command(
        auto_locale_strings=False,
        name=locale_str(
            "chart_append", key="guess.cmds.chart_append.name", file="commands"
        ),
        description=locale_str("guess.cmds.chart_append.desc", file="commands"),
    )
    @app_commands.guild_only()
    async def guess_chart_append(self, interaction: discord.Interaction):
        if self.bot.downloading_charts:
            embed = embeds.error_embed(
                f"I'm currently refreshing all my charts. Please be patient and try again in a minute.",
            )
            await interaction.response.send_message(embed=embed)
            return
        await self.handle_guess(interaction, "chart_append")

    @guess.command(
        auto_locale_strings=False,
        name=locale_str("event", key="guess.cmds.event.name", file="commands"),
        description=locale_str("guess.cmds.event.desc", file="commands"),
    )
    @app_commands.guild_only()
    async def guess_event(self, interaction: discord.Interaction):
        await self.handle_guess(interaction, "event")

    @guess.command(
        auto_locale_strings=False,
        name=locale_str("notes", key="guess.cmds.notes.name", file="commands"),
        description=locale_str("guess.cmds.notes.desc", file="commands"),
    )
    @app_commands.guild_only()
    async def guess_notes(self, interaction: discord.Interaction):
        await self.handle_guess(interaction, "notes")

    # endregion


async def setup(bot: DiscordBot):
    await bot.add_cog(GuessCog(bot))
