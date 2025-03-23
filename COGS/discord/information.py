import discord
from discord.ext import commands
from discord import app_commands

from discord.app_commands import locale_str
from COGS.discord_translations import translations

from main import DiscordBot

import time, re
from collections import Counter

from DATA.helpers.discord_emojis import emojis
from DATA.helpers import converters
from DATA.helpers import discord_autocompletes as autocompletes
from DATA.helpers import embeds
from DATA.helpers import progress_bar
from DATA.helpers import tools

from DATA.game_api import methods

from main import DiscordBot


class InfoCog(commands.Cog):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    def _update_cmd_deque(self):
        current_time = time.time()
        while (
            self.bot.cache.executed_commands
            and self.bot.cache.executed_commands[0][1] < current_time - 60
        ):
            self.bot.cache.executed_commands.popleft()

    @commands.Cog.listener()
    async def on_app_command_completion(
        self, interaction: discord.Interaction, command: app_commands.Command
    ):
        # Append the command's qualified_name, timestamp, and user ID to the deque
        self.bot.cache.executed_commands.append(
            (command.qualified_name, time.time(), interaction.user.id)
        )

        self._update_cmd_deque()

    def check_text(self, text: str, block_words: list, allow_words: list):
        blocked_words = []
        is_blocked = False

        # Escape any triple backticks and existing backslashes
        escaped_text = re.sub(r"(```|\\)", r"\\\1", text)

        # Remove all allowed words at once
        allowed_patterns = [re.escape(allow["word"]) for allow in allow_words]
        combined_allowed_pattern = r"|".join(
            allowed_patterns
        )  # Join all allowed words into a single regex pattern
        text = re.sub(combined_allowed_pattern, "", text, flags=re.IGNORECASE)

        for block in block_words:
            block_word = block["word"].lower()
            if block_word in text.lower() and block_word not in blocked_words:
                matches = re.finditer(
                    re.escape(block["word"]), escaped_text, flags=re.IGNORECASE
                )
                for match in matches:
                    blocked_words.append(match.group(0))  # Append exact case match
                is_blocked = True

        blocked_section = "\n```diff"
        if blocked_words:
            for word in blocked_words:
                blocked_section += f"\n- {word}"
            blocked_section += "\n```"
        else:
            blocked_section += "\n+ None!\n```"

        return escaped_text, blocked_section, is_blocked

    pjsk = app_commands.Group(
        name=locale_str("pjsk", key="pjsk.name", file="commands"),
        description=locale_str("pjsk.desc", file="commands"),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
    )

    @pjsk.command(
        auto_locale_strings=False,
        name=locale_str(
            "why_inappropriate", key="pjsk.cmds.why_inappropriate.name", file="commands"
        ),
        description=locale_str("pjsk.cmds.why_inappropriate.desc", file="commands"),
    )
    @app_commands.describe(
        text=locale_str("pjsk.cmds.why_inappropriate.describes.text", file="commands"),
        region=locale_str("general.region"),
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.autocomplete(
        region=autocompletes.autocompletes.pjsk_region(["en", "jp", "tw", "kr", "cn"])
    )
    async def why_inappropriate(
        self, interaction: discord.Interaction, text: str, region: str = "default"
    ):
        region = region.lower().strip()
        if region not in ["en", "jp", "tw", "kr", "cn", "default"]:
            return await interaction.response.send_message(
                embed=embeds.error_embed(
                    await interaction.translate(
                        locale_str(
                            "errors.unsupported_region",
                            replacements={"{region}": region.upper()},
                        )
                    )
                ),
                ephemeral=True,
            )
        if len(text) > 512:
            await interaction.response.send_message(
                embeds.error_embed("Text is too long! Max length is 512 characters."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)
        if region == "default":
            region = await self.bot.user_data.discord.get_settings(
                interaction.user.id, "default_region"
            )
        api = methods.Tools.get_api(region)

        try:
            allow_words = api.get_master_data("allowWords.json")
        except FileNotFoundError:  # Some regions don't have this.
            allow_words = []
        block_words = api.get_master_data("ngWords.json")

        # Check the text
        escaped_text, blocked_section, verdict = self.check_text(
            text, block_words, allow_words
        )

        # Create the embed
        embed = embeds.embed(
            title=f"PJSK {region.upper()} Text Check",
            description=(
                f"Your text is **appropriate**, and is allowed on PJSK {region.upper()}!"
                if not verdict
                else f"Your text is **inappropriate**, and will be blocked on PJSK {region.upper()}!"
            ),
            color=discord.Color.green() if not verdict else discord.Color.red(),
        )
        embed.add_field(
            name="Your Text", value=f"```text\n{escaped_text}\n```", inline=False
        )
        embed.add_field(name="Blocked Words", value=blocked_section, inline=False)

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        auto_locale_strings=False,
        name=locale_str("ping", key="ping.name", file="commands"),
        description=locale_str("ping.desc", file="commands"),
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False, thinking=True)

        self._update_cmd_deque()

        cmds_ran = len(self.bot.cache.executed_commands) + 1
        current_time = time.time()

        user_ids = set()
        user_ids.add(interaction.user.id)
        command_counter = Counter()

        for cmd, timestamp, user_id in self.bot.cache.executed_commands:
            if timestamp >= current_time - 60:
                user_ids.add(user_id)
                command_counter[cmd] += 1

        command_counter["ping"] += 1

        most_popular_cmd = (
            f"`/{command_counter.most_common(1)[0][0]}` was the most popular command in the last minute."
            if command_counter
            else "No commands were ran."
        )

        # Create the embed
        embed = embeds.embed(
            title="Pong!",
            description=(
                f"**Latency:** `{round(self.bot.latency * 1000, 2)}`ms\n\n"
                f"**{cmds_ran:,}** command{'s' if cmds_ran != 1 else ''} {'were' if cmds_ran != 1 else 'was'} ran in the last minute.\n"
                f"**{len(user_ids)}** user{'s' if len(user_ids) != 1 else ''} ran commands in the last minute.\n"
                f"{most_popular_cmd}"
            ),
            color=discord.Color.green(),
        )

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        auto_locale_strings=False,
        name=locale_str("donate", key="donate.name", file="commands"),
        description=locale_str("donate.desc", file="commands"),
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    async def donate(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        cost = 25
        embed = embeds.embed(
            title="Donations",
            description=f"<:sbuga:1293557990397448285> sbugacoin??\n-# Donations are strictly OPTIONAL.\n\nWe need donations to pay the approximately **${cost:,} USD** hosting cost every month, and this number will grow as the bot expands.\n\n**LINK:** https://ko-fi.com/uselessyum\n\nTo claim benefits, join the Discord server via Ko-Fi (also located at </help:1326325488939040808>). You must login on Ko-Fi!",
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        auto_locale_strings=False,
        name=locale_str("help", key="help.name", file="commands"),
        description=locale_str("help.desc", file="commands"),
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    async def help(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False, thinking=True)
        embed = embeds.embed(
            title=f"{self.bot.user.name}",
            description=f"Sbuga <:sbuga:1293557990397448285>\n\n**Invite:** https://discord.com/oauth2/authorize?client_id=1322253224799109281\n**Support:** https://discord.gg/JKANSRGPNW\n\n**Commands:** https://github.com/Sbotga/info/blob/main/en/COMMANDS.md\n**TOS:** https://github.com/Sbotga/info/blob/main/legal/TOS.md\n**Privacy Policy:** https://github.com/Sbotga/info/blob/main/legal/PRIVACY.md\n\n-# {self.bot.user.mention} is in no way affiliated with SEGA, Colorful Palette, or Project Sekai.",
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        auto_locale_strings=False,
        name=locale_str("xp_for", key="xp_for.name", file="commands"),
        description=locale_str("xp_for.desc", file="commands"),
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.describe(
        level=locale_str("xp_for.describes.level", file="commands"),
    )
    async def xp_for_cmd(self, interaction: discord.Interaction, level: int):
        if level < 1 or level > 3939:
            return await interaction.response.send_message(
                embed=embeds.error_embed("Invalid level.")
            )

        await interaction.response.defer(thinking=True)
        xp_needed = self.bot.user_data.discord.xp_for_level(level)
        current_xp = await self.bot.user_data.discord.get_experience(
            interaction.user.id
        )

        if current_xp == 0:
            faked_xp = 1
        else:
            faked_xp = current_xp
        bar = progress_bar.generate_progress_bar(
            min(faked_xp, max(1, xp_needed)),
            min(faked_xp, max(1, xp_needed)),
            max(1, xp_needed),
            bar_length=20,
        )

        embed = embeds.embed(
            title=f"XP For Level {level:,}.",
            description=f"{xp_needed:,} XP is needed for level {level:,}. You have {current_xp:,} XP.",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name=f"Your Progress ({current_xp:,}/{xp_needed:,})",
            value=bar,
            inline=False,
        )

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        auto_locale_strings=False,
        name=locale_str("profile", key="profile.name", file="commands"),
        description=locale_str("profile.desc", file="commands"),
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.describe(user=locale_str("general.discord_user"))
    async def profile(
        self, interaction: discord.Interaction, user: discord.User = None
    ):
        if user == None:
            user = interaction.user
        await interaction.response.defer(thinking=True)

        level, current_xp, xp_needed = self.bot.user_data.discord.calculate_level(
            await self.bot.user_data.discord.get_experience(user.id)
        )
        currency = await self.bot.user_data.discord.get_currency(user.id)

        bar = progress_bar.generate_progress_bar(
            current_xp, current_xp, xp_needed, bar_length=20
        )

        guild = self.bot.get_guild(1238684904804319243)
        if not guild:
            guild = await self.bot.fetch_guild(1238684904804319243)
        try:
            member = await guild.fetch_member(user.id)
            developer = 1329628642036154494
            strat_mod = 1338521073448255508
            translator = 1330694049799082085
            staff_roles = [
                developer,  # developer
                strat_mod,  # strategy moderator
                translator,  # translator
            ]
            staff_roles.extend(self.bot.alias_adders)  # alias adders
            staff = any(role in member._roles for role in staff_roles)
            staff = staff or member.id in self.bot.owner_ids
        except discord.NotFound:
            staff = False

        if staff:
            is_staff = [""]
            if (member.id in self.bot.owner_ids) or (
                any(role in member._roles for role in [developer, strat_mod])
            ):
                is_staff.append("🛡️ **Sbotga Staff**")
            if any(role in member._roles for role in [translator]):
                is_staff.append("🌐 **Sbotga Translator**")
            if any(role in member._roles for role in self.bot.alias_adders):
                is_staff.append("🆕 **Song Alias Moderator**")
            is_staff = "\n".join(is_staff)
        else:
            is_staff = ""

        # Create the embed
        embed = embeds.embed(
            title=f"{tools.escape_md(user.name)}'s Profile",
            description=is_staff,
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=user.avatar.url)
        embed.add_field(
            name=f"Level {level}",
            value=f"{bar}\nXP: {current_xp:,}/{xp_needed:,}",
            inline=False,
        )
        embed.add_field(
            name="Sbugacoin", value=f"**{currency:,}** {emojis.sbugacoin}", inline=False
        )
        embed.set_footer(
            text=f"Requested by {tools.escape_md(interaction.user.name)}",
            icon_url=interaction.user.avatar.url,
        )

        await interaction.followup.send(embed=embed)

    @pjsk.command(
        auto_locale_strings=False,
        name=locale_str("profile", key="pjsk.cmds.profile.name", file="commands"),
        description=locale_str("pjsk.cmds.profile.desc", file="commands"),
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.autocomplete(
        region=autocompletes.autocompletes.pjsk_region(["en", "jp", "tw", "kr", "cn"])
    )
    @app_commands.describe(
        user_id=locale_str("general.pjsk_user_id"), region=locale_str("general.region")
    )
    async def pjsk_profile(
        self,
        interaction: discord.Interaction,
        user_id: str = None,
        region: str = "default",
    ):
        region = region.lower().strip()
        if region not in ["en", "jp", "tw", "kr", "cn", "default"]:
            return await interaction.response.send_message(
                embed=embeds.error_embed(
                    await interaction.translate(
                        locale_str(
                            "errors.unsupported_region",
                            replacements={"{region}": region.upper()},
                        )
                    )
                ),
                ephemeral=True,
            )
        await interaction.response.defer(ephemeral=False, thinking=True)
        if region == "default":
            region = await self.bot.user_data.discord.get_settings(
                interaction.user.id, "default_region"
            )
        try:
            # min and max         10000000                    402827003243343876 is my id
            if user_id:
                assert int(user_id) > 10000000 and int(user_id) < 10000000000000000000
            else:
                user_id = await self.bot.user_data.discord.get_pjsk_id(
                    interaction.user.id, region
                )
                if not user_id:
                    return await interaction.followup.send(
                        embed=embeds.error_embed(
                            f"Please link your {region.upper()} PJSK account to use this command without specifiying a user."
                        )
                    )
            api = methods.Tools.get_api(region)
            data = api.get_profile(int(user_id))
            last_updated = api.profile_cache[int(user_id)]["last_updated"]
        except Exception as e:
            if "404" in str(e):
                return await interaction.followup.send(
                    embed=embeds.error_embed(
                        f"Couldn't get this user's profile; are they in the {region.upper()} server (if not, change the region option)? Is the user id valid?"
                    )
                )
            raise e
        is_self = False
        pjsk_id = await self.bot.user_data.discord.get_pjsk_id(
            interaction.user.id, region
        )
        if pjsk_id == user_id:
            is_self = True
        # id: 7459900032591108917, joined 1736898921322
        joined = (
            f"**Joined:** <t:{(int(format(data['user']['userId'], '064b')[:42], 2) + 1600218000000) // 1000}:R>\n"
            if region in ["en", "jp"]
            else ""  #  f"**Joined:** <t:{(int(format(data['user']['userId'], '064b')[:42], 2) - 41679844688) // 1000}:R>\n" # THIS IS NOT ACCURATE.
        )
        embed = embeds.embed(
            title=data["user"]["name"],
            description=("✅ This is your PJSK account!\n\n" if is_self else "")
            + (
                f"**User ID:** `{data['user']['userId']}`\n"
                f"{joined}"
                f"**Rank:** **`🎵 {data['user']['rank']}`**\n\n"
                f"**Bio**\n```{data['userProfile'].get('word') or 'No Bio'}```\n"
                f"**X (formerly Twitter):** *`{data['userProfile'].get('twitterId') or 'None'}`*\n\n"
                f"**Clears:**  "  # `{data['userMusicDifficultyClearCount'][0]['liveClear']}` Easy {emojis.clear}, "
                # f"`{data['userMusicDifficultyClearCount'][1]['liveClear']}` Normal {emojis.clear}, "
                # f"`{data['userMusicDifficultyClearCount'][2]['liveClear']}` Hard {emojis.clear}, "
                f"`{data['userMusicDifficultyClearCount'][3]['liveClear']}` Expert {emojis.clear}, "
                f"`{data['userMusicDifficultyClearCount'][4]['liveClear']}` Master {emojis.clear}, "
                f"`{data['userMusicDifficultyClearCount'][5]['liveClear']}` Append {emojis.append_clear}\n"
                f"**FCs:**    "  # `{data['userMusicDifficultyClearCount'][0]['fullCombo']}` Easy {emojis.fc}, "
                # f"`{data['userMusicDifficultyClearCount'][1]['fullCombo']}` Normal {emojis.fc}, "
                # f"`{data['userMusicDifficultyClearCount'][2]['fullCombo']}` Hard {emojis.fc}, "
                f"`{data['userMusicDifficultyClearCount'][3]['fullCombo']}` Expert {emojis.fc}, "
                f"`{data['userMusicDifficultyClearCount'][4]['fullCombo']}` Master {emojis.fc}, "
                f"`{data['userMusicDifficultyClearCount'][5]['fullCombo']}` Append {emojis.append_fc}\n"
                f"**APs:**    "  # `{data['userMusicDifficultyClearCount'][0]['allPerfect']}` Easy {emojis.ap}, "
                # f"`{data['userMusicDifficultyClearCount'][1]['allPerfect']}` Normal {emojis.ap}, "
                # f"`{data['userMusicDifficultyClearCount'][2]['allPerfect']}` Hard {emojis.ap}, "
                f"`{data['userMusicDifficultyClearCount'][3]['allPerfect']}` Expert {emojis.ap}, "
                f"`{data['userMusicDifficultyClearCount'][4]['allPerfect']}` Master {emojis.ap}, "
                f"`{data['userMusicDifficultyClearCount'][5]['allPerfect']}` Append {emojis.append_ap}\n"
            ),
            color=discord.Color.dark_green(),
        )
        embed.set_footer(
            text=f"{region.upper()} - Last updated {round(time.time()-last_updated)}s ago"
        )
        await interaction.followup.send(embed=embed)

    alias = app_commands.Group(
        name="alias",
        description="Add or remove aliases for songs.",
        guild_ids=[1238684904804319243],
        allowed_installs=app_commands.AppInstallationType(guild=True, user=False),
    )

    @alias.command(
        auto_locale_strings=False,
        name="add",
        description="Authorized only; add a song alias.",
    )
    @app_commands.autocomplete(song=autocompletes.autocompletes.pjsk_song)
    @app_commands.describe(song=locale_str("general.song_name"))
    async def add_alias(self, interaction: discord.Interaction, song: str, alias: str):
        if (interaction.user.id not in self.bot.owner_ids) and not any(
            role_id in self.bot.alias_adders for role_id in interaction.user._roles
        ):
            return await interaction.response.send_message(
                embed=embeds.error_embed("Who do you think you are >:("), ephemeral=True
            )
        await interaction.response.defer(ephemeral=False, thinking=True)
        osong = song
        song = converters.SongFromPJSK(self.bot.pjsk, song)
        if song is None:
            embed = embeds.error_embed(
                await interaction.translate(
                    locale_str("errors.unknown_song", replacements={"{song}": osong})
                ),
            )
            await interaction.followup.send(embed=embed)
            return
        await self.bot.pjsk.add_song_alias(song.id, alias.lower())
        embed = embeds.success_embed(
            title="Added alias!",
            description=f"Added alias for song: `{song.title}` (ID `{song.id}`)\nAlias: `{alias.lower()}`",
        )
        await interaction.followup.send(embed=embed)

    @alias.command(
        auto_locale_strings=False,
        name="remove",
        description="Authorized only; remove a song alias.",
    )
    @app_commands.autocomplete(song=autocompletes.autocompletes.pjsk_song)
    @app_commands.describe(song=locale_str("general.song_name"))
    async def remove_alias(
        self, interaction: discord.Interaction, song: str, alias: str
    ):
        if (interaction.user.id not in self.bot.owner_ids) and not any(
            role_id in self.bot.alias_adders for role_id in interaction.user._roles
        ):
            return await interaction.response.send_message(
                embed=embeds.error_embed("Who do you think you are >:("), ephemeral=True
            )
        await interaction.response.defer(ephemeral=False, thinking=True)
        osong = song
        song = converters.SongFromPJSK(self.bot.pjsk, song)
        if song is None:
            embed = embeds.error_embed(
                await interaction.translate(
                    locale_str("errors.unknown_song", replacements={"{song}": osong})
                ),
            )
            await interaction.followup.send(embed=embed)
            return
        await self.bot.pjsk.remove_song_alias(song.id, alias.lower())
        embed = embeds.success_embed(
            title="Removed alias!",
            description=f"Removed alias (if existed) for song: `{song.title}` (ID `{song.id}`)\nAlias: `{alias.lower()}`",
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: DiscordBot):
    await bot.add_cog(InfoCog(bot))
