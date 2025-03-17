import discord
from discord.ext import commands
from discord import app_commands

from discord.app_commands import locale_str
from COGS.discord_translations import translations

from main import DiscordBot

import datetime

from DATA.game_api import methods

from DATA.helpers import discord_autocompletes as autocompletes
from DATA.helpers import views
from DATA.helpers import discord_emojis
from DATA.helpers import embeds
from DATA.helpers import progress_bar
from DATA.helpers import tools


class Achievements(commands.Cog):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

        self.bot.add_achievement = self.add_achievement
        self.bot.grant_reward = self.grant_reward
        self.bot.add_experience = self.add_experience
        self.bot.add_currency = self.add_currency

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if self.bot.user.name.lower() in message.content.lower():
            has = await self.bot.user_data.discord.has_achievement(
                message.author.id, "namer"
            )
            if not has:
                await self.bot.add_achievement(message, "namer")

    async def grant_reward(self, user: discord.User, type: str, amount: int) -> int:
        if type == "currency":
            return await self.bot.user_data.discord.add_currency(user.id, amount)
        elif type == "xp":
            return await self.bot.user_data.discord.add_experience(user.id, amount)

    async def add_currency(
        self,
        intage: discord.Interaction | discord.Message,
        currency: int,
        user: discord.User = None,
    ):
        user = user or (intage.user if hasattr(intage, "user") else intage.author)
        await self.bot.grant_reward(user, "currency", currency)

    async def add_experience(
        self,
        intage: discord.Interaction | discord.Message,
        xp: int,
        user: discord.User = None,
        ephemeral: bool = False,
        prog_bar: bool = True,
    ) -> None:
        user = user or (intage.user if hasattr(intage, "user") else intage.author)

        new_xp = await self.bot.grant_reward(user, "xp", xp)
        new_level = self.bot.user_data.discord.calculate_level(new_xp)
        level = self.bot.user_data.discord.calculate_level(new_xp - xp)

        # tuple: level, exp to next level, xp needed
        if level == new_level:
            pass
        else:
            if level[0] == new_level[0]:
                pass  # xp added but no new level
            else:
                if prog_bar:
                    bar = (
                        progress_bar.generate_progress_bar(
                            0, new_level[1], new_level[2]
                        )
                        + " "
                    )
                else:
                    bar = ""
                level_up = f"Leveled up {new_level[0]-level[0]:,} time{'s' if new_level[0]-level[0]  != 1 else ''}!\n"
                embed = embeds.embed(
                    title="Level Up!",
                    description=f"{user.mention} {level_up}Level {new_level[0]:,} - {bar}({new_level[1]:,}/{new_level[2]:,} XP)",
                    color=discord.Color.green(),
                )

                if intage.guild:
                    perms = intage.channel.permissions_for(intage.guild.me)
                    correct_perms = (
                        perms.send_messages
                        and (
                            not isinstance(intage.channel, discord.Thread)
                            or perms.send_messages_in_threads
                        )
                        and perms.embed_links
                    )
                else:
                    correct_perms = True
                if hasattr(intage, "reply") and correct_perms:
                    await intage.reply(embed=embed)
                elif hasattr(intage, "followup"):
                    await intage.followup.send(embed=embed, ephemeral=ephemeral)
                elif hasattr(intage, "channel") and correct_perms:
                    await intage.channel.send(embed=embed)

    async def add_achievement(
        self,
        intage: discord.Interaction | discord.Message,
        achievement: str,
        rank: int = 1,
        user: discord.User = None,
        ephemeral: bool = False,
    ) -> None:
        user = user or (intage.user if hasattr(intage, "user") else intage.author)
        achievement_data = self.bot.CONFIGS.achievements[achievement]

        if intage.guild:
            perms = intage.channel.permissions_for(intage.guild.me)
            correct_perms = (
                perms.send_messages
                and (
                    not isinstance(intage.channel, discord.Thread)
                    or perms.send_messages_in_threads
                )
                and perms.embed_links
            )
        else:
            correct_perms = True

        if not intage.guild:
            if achievement_data.get("guild_only"):
                return

        if achievement_data.get("dm_only"):
            if not isinstance(intage.channel, discord.DMChannel):
                return

        if not correct_perms and achievement_data.get("must_send"):
            return

        achievement_rank_data = achievement_data["ranks"][str(rank)]
        rewards = achievement_rank_data["rewards"]

        await self.bot.user_data.discord.add_achievement(
            user.id, achievement, rank, rewards
        )

        embed = embeds.embed(
            title=f"Achievement Unlocked! 🏆",
            color=(
                discord.Color.green()
                if not achievement_data["bad"]
                else discord.Color.red()
            ),
        )

        achievement_title = achievement_data["name"]
        if achievement_rank_data["name"]:
            achievement_title += f"{' - ' if achievement_data.get('join_name', True) else ' '}{achievement_rank_data['name']}"
        achievement_description = (
            "*"
            + (
                achievement_data["description"]
                if not achievement_rank_data["description"]
                else achievement_rank_data["description"]
            )
            + "*"
        )

        embed.description = f"{user.mention}\n{'-'*30}\n**{achievement_title}**\n{achievement_description}\n{'-'*30}"

        reward_field = []

        new_xp = None
        old_xp = None
        for reward in rewards:
            amount = reward["amount"]
            reward_type = reward["type"]
            if reward["type"] == "currency":
                reward_field.append(
                    f"- Earned {amount:,} {discord_emojis.emojis.sbugacoin}!"
                )
                await self.bot.grant_reward(user, reward_type, amount)
            elif reward["type"] == "xp":
                reward_field.append(f"- Earned {amount:,} XP!")
                new_xp = await self.bot.grant_reward(user, reward_type, amount)
                old_xp = new_xp - amount
            elif reward["type"] == "money":
                reward_field.append(
                    f"- Earned ${amount:,}! Congratulations, you earned real money as a prize. Please join our support server to claim.\n-# Prizes are subject to our TOS, and may be revoked at our discretion."
                )

        if reward_field:
            reward_field = "\n".join(reward_field)
            embed.description += f"\n{reward_field}"

        if new_xp is not None:
            level = self.bot.user_data.discord.calculate_level(old_xp)
            new_level = self.bot.user_data.discord.calculate_level(new_xp)

            # tuple: level, exp to next level, xp needed
            if level == new_level:
                pass
            else:
                if level[0] == new_level[0]:
                    bar = progress_bar.generate_progress_bar(
                        level[1], new_level[1], new_level[2]
                    )
                    level_up = ""
                else:
                    bar = progress_bar.generate_progress_bar(
                        0, new_level[1], new_level[2]
                    )
                    level_up = f"Leveled up {new_level[0]-level[0]:,} time{'s' if new_level[0]-level[0]  != 1 else ''}!\n"
                embed.add_field(
                    name="Level",
                    value=f"{level_up}Level {new_level[0]:,} - {bar} ({new_level[1]:,}/{new_level[2]:,} XP)",
                    inline=False,
                )

        if hasattr(intage, "reply") and correct_perms:
            await intage.reply(embed=embed)
        elif hasattr(intage, "followup"):
            await intage.followup.send(embed=embed, ephemeral=ephemeral)
        elif hasattr(intage, "channel") and correct_perms:
            await intage.channel.send(embed=embed)

    def get_achievement_info(self, achievement: str, rank: int):
        """Retrieve the achievement title and description based on rank."""
        achievement_data = self.bot.CONFIGS.achievements[achievement]
        achievement_rank_data = achievement_data["ranks"].get(str(rank))

        # Default to no rank if the rank does not exist
        if not achievement_rank_data:
            return None, None

        possiblerank = f" (Rank {rank})" if rank > 1 else ""

        # Form the achievement title with rank info
        achievement_title = achievement_data["name"]
        if achievement_rank_data["name"]:
            achievement_title += f"{' - ' if achievement_data.get('join_name', True) else ' '}{achievement_rank_data['name']}{possiblerank}"

        # Description of the achievement, rank-specific if it exists
        achievement_description = (
            achievement_data["description"]
            if not achievement_rank_data["description"]
            else achievement_rank_data["description"]
        )

        return achievement_title, achievement_description

    @app_commands.command(
        auto_locale_strings=False,
        name=locale_str("achievements", key="achievements.name", file="commands"),
        description=locale_str("achievements.desc", file="commands"),
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.describe(user=locale_str("general.discord_user"))
    async def achievements(
        self, interaction: discord.Interaction, user: discord.User = None
    ):
        if user == None:
            user = interaction.user
        await interaction.response.defer(thinking=True)

        user_achievements = await self.bot.user_data.discord.get_achievements(user.id)

        items_per_page = 10
        total_pages = (len(user_achievements) + items_per_page - 1) // items_per_page

        current_page = 1

        async def get_page_content(page: int, total_pages: int):
            """Retrieve content for the current page."""
            start_idx = (page - 1) * items_per_page
            end_idx = min(page * items_per_page, len(user_achievements))

            # Slice the achievements list to get only the current page's achievements
            page_achievements = list(user_achievements.keys())[start_idx:end_idx]
            embed = embeds.embed(
                title=f"{tools.escape_md(user.name)}'s Achievements",
                color=discord.Color.blurple(),
            )

            desc = []

            for achievement in page_achievements:
                d = user_achievements[achievement]
                unlocked_at = None
                last_upgraded = None

                for rank, data in d["granted"].items():
                    achievement_title, achievement_description = (
                        self.get_achievement_info(achievement, int(rank))
                    )
                    if not achievement_title or not achievement_description:
                        continue

                    if rank == "1":
                        unlocked_at = data["date"]
                    last_upgraded = data["date"]
                if last_upgraded == unlocked_at:
                    unlocked_at_dt = datetime.datetime.fromisoformat(unlocked_at)
                    unlock_msg = f"Unlocked At: {discord.utils.format_dt(unlocked_at_dt, style='f')}"
                else:
                    unlocked_at_dt = datetime.datetime.fromisoformat(unlocked_at)
                    last_upgraded_dt = datetime.datetime.fromisoformat(last_upgraded)
                    unlock_msg = (
                        f"First Unlocked: {discord.utils.format_dt(unlocked_at_dt, style='f')}\n"
                        f"Rank {rank} Unlocked: {discord.utils.format_dt(last_upgraded_dt, style='f')}"
                    )
                desc.append(
                    f"**🏆 {achievement_title}**\n*{achievement_description}*\n{unlock_msg}"
                )
            embed.description = (
                f"\n{'-'*30}\n".join(desc) + f"\n\n-# Page {current_page}/{total_pages}"
            )
            return embed

        # Create pagination buttons
        class PaginatorView(views.SbotgaView):
            def __init__(self):
                super().__init__(timeout=60)
                self.current_page = 1
                self.total_pages = total_pages

                self.update_buttons()

            def update_buttons(self):
                self.previous_page.disabled = self.current_page == 1
                self.next_page.disabled = self.current_page == self.total_pages

            @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.primary)
            async def previous_page(
                self, interaction: discord.Interaction, button: discord.ui.Button
            ):
                if self.current_page > 1:
                    self.current_page -= 1
                    self.update_buttons()
                    embed = await get_page_content(self.current_page, self.total_pages)
                    self.timeout += 30
                    await interaction.response.edit_message(embed=embed, view=self)

            @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.primary)
            async def next_page(
                self, interaction: discord.Interaction, button: discord.ui.Button
            ):
                if self.current_page < self.total_pages:
                    self.current_page += 1
                    self.update_buttons()
                    embed = await get_page_content(self.current_page, self.total_pages)
                    self.timeout += 30
                    await interaction.response.edit_message(embed=embed, view=self)

        # Send the initial embed
        embed = await get_page_content(current_page, total_pages)
        paginator_view = PaginatorView()

        await interaction.followup.send(embed=embed, view=paginator_view)
        paginator_view.message = await interaction.original_response()


async def setup(bot: DiscordBot):
    await bot.add_cog(Achievements(bot))
