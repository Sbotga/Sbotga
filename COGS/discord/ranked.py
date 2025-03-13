import discord
from discord import app_commands
from discord.ext import commands

from discord.app_commands import locale_str
from COGS.discord_translations import translations

from main import DiscordBot

import math, time, json, os

from DATA.game_api import methods
from DATA.helpers import discord_autocompletes as autocompletes
from DATA.helpers import views
from DATA.helpers import embeds
from DATA.helpers import tools

# English Grade Names
RANKMATCH_GRADES_EN = {
    1: "Beginner",
    2: "Bronze",
    3: "Silver",
    4: "Gold",
    5: "Platinum",
    6: "Diamond",
    7: "Master",
}

# Japanese Grade Names
RANKMATCH_GRADES_JP = {
    1: "ビギナー",
    2: "ブロンズ",
    3: "シルバー",
    4: "ゴールド",
    5: "プラチナ",
    6: "ダイヤモンド",
    7: "マスター",
}

# TODO, move ^ rank match names to translations files.

RANKMATCH_IMAGES = {
    0: "DATA/data/ASSETS/ranked/unknown.png",
    1: "DATA/data/ASSETS/ranked/beginner.png",
    2: "DATA/data/ASSETS/ranked/bronze.png",
    3: "DATA/data/ASSETS/ranked/silver.png",
    4: "DATA/data/ASSETS/ranked/gold.png",
    5: "DATA/data/ASSETS/ranked/platinum.png",
    6: "DATA/data/ASSETS/ranked/diamond.png",
    7: "DATA/data/ASSETS/ranked/master.png",
}


class RankedCog(commands.Cog):
    def __init__(self, bot: DiscordBot):
        self.bot = bot
        self.ranked_data = {
            api.app_region: {"rankings": []} for api in methods.all_apis
        }
        self.last_updated = {api.app_region: 0 for api in methods.all_apis}

        self.update_cooldown = 600  # 10 minutes

        if os.path.exists("DATA/data/ASSETS/ranked/top100.json"):
            with open("DATA/data/ASSETS/ranked/top100.json", "r") as f:
                data = json.load(f)
                for k, v in data["data"].items():
                    self.ranked_data[k] = v
                for k, v in data["last_updated"].items():
                    self.last_updated[k] = v

    def update_rank_data(self, region: str, force: bool = False) -> str:
        api = methods.Tools.get_api(region)
        if force or self.last_updated[region] + self.update_cooldown < time.time():
            try:
                self.ranked_data[region] = api.get_ranked_leaderboard()
                self.last_updated[region] = time.time()
                with open(f"DATA/data/ASSETS/ranked/top100.json", "w+") as f:
                    json.dump(
                        {
                            "last_updated": self.last_updated,
                            "data": self.ranked_data,
                        },
                        f,
                    )
            except Exception as e:
                # pass
                self.bot.traceback(e)
        data = api.get_master_data("rankMatchSeasons.json")
        for i in range(0, len(data)):
            startAt = data[i]["startAt"]
            endAt = data[i]["closedAt"]
            now = int(round(time.time() * 1000))
            if startAt < now < endAt:
                return data[i]["name"]
        if (
            len(data) == 1
        ):  # 如果只有一个数据，有可能是开第一次排位之前，也有可能是第一次排位之后，排除第一个排位之前的
            if now < data[0]["startAt"]:
                return "Unknown Season"
            else:
                return data[len(data) - 1]["id"]
        else:
            return data[len(data) - 1]["id"]

    class LeaderboardView(views.SbotgaView):
        def __init__(
            self,
            current_page: int,
            total_pages: int,
            region: str,
            ranked_data: dict,
            last_updated: dict,
            season_name: str,
            pjsk_id: int,
        ):
            super().__init__()
            self.current_page = current_page
            self.total_pages = total_pages
            self.current_region = region
            self.ranked_data = ranked_data
            self.last_updated = last_updated
            self.season_name = season_name
            self.pjsk_id = pjsk_id
            self.update_buttons()

        def update_buttons(self):
            self.previous_page.disabled = self.current_page == 1
            self.next_page.disabled = self.current_page == self.total_pages

        async def update_message(self, interaction: discord.Interaction):
            embed = RankedCog.create_leaderboard_embed(
                self.ranked_data,
                self.last_updated,
                self.current_page,
                self.current_region,
                season_name=self.season_name,
                pjsk_id=self.pjsk_id,
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
                embed = embeds.error_embed("You cannot click this button!")
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
                embed = embeds.error_embed("You cannot click this button!")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            await interaction.response.defer()
            if self.current_page < self.total_pages:
                self.current_page += 1
                await self.update_message(interaction)

    # Calculate Rank Class Details
    @staticmethod
    def calculate_rank_details(ranking, region: str):
        tier_id = ranking["userRankMatchSeason"]["rankMatchTierId"]
        tier_point = ranking["userRankMatchSeason"]["tierPoint"]

        grade = min(int((tier_id - 1) / 4) + 1, 7)
        kurasu = tier_id - 4 * (grade - 1)
        if not kurasu:
            kurasu = 4

        if region == "en":
            grade_name = RANKMATCH_GRADES_EN[grade]
        elif region == "jp":
            grade_name = RANKMATCH_GRADES_JP[grade]
        else:
            grade_name = RANKMATCH_GRADES_EN[grade]
        if grade == 7:  # Master Rank
            return f"**{grade_name}**\n♪ × {tier_point}", grade
        else:
            return f"**{grade_name}** Class {kurasu}\n{tier_point}/5", [grade, kurasu]

    def create_rank_embed(self, rank: int, region: str, is_self: bool):
        ranking = self.ranked_data[region]["rankings"][rank - 1]
        season = ranking["userRankMatchSeason"]
        grade_details, grade = RankedCog.calculate_rank_details(ranking, region)

        embed = embeds.embed(
            title=f"Rank #{ranking['rank']} - {tools.escape_md(ranking['name'] if len(ranking['name']) < 50 else (ranking['name'][:43] + '... ⚠️ (I will not display your very long name)'))}",
            color=(
                discord.Color.purple()
                if (grade[0] if type(grade) == list else grade) == 7
                else discord.Color.dark_blue()
            ),
        )
        gd0 = grade_details.split("\n")[0]
        gd1 = grade_details.split("\n")[1]
        desc_text = ""
        if is_self:
            desc_text = "✅ This is you!\n"
        desc_text += f"## {gd0 + ' (`' + gd1 + '`)'}\n\n**Total Games:** `{season['playCount']}`\n**Win Rate:** `{(season['winCount']/(season['playCount']-season['drawCount']))*100:.2f}`%\n-# Win rate does not include draws.\n\n**Current Winstreak:** `{season['consecutiveWinCount']}`\n**Max Winstreak:** `{season['maxConsecutiveWinCount']}`\n\n-# Ranked losses are added for disconnects, but doesn't add to the total playcount. Win rate may be off."
        desc_text += (
            f"\n\n### Web View: <https://sbuga.com/{region}/ranked/{ranking['userId']}>"
        )
        embed.description = desc_text
        file = discord.File(
            RANKMATCH_IMAGES[grade[0] if type(grade) == list else grade],
            filename="image.png",
        )
        embed.set_thumbnail(url="attachment://image.png")

        # RankMatchSeason details
        embed.add_field(
            name="Wins",
            value=season["winCount"],
            inline=True,
        )
        embed.add_field(name="Losses", value=season["loseCount"], inline=True)
        embed.add_field(name="Draws", value=season["drawCount"], inline=True)

        embed.set_footer(
            text=f"Ranked Statistics - {region.upper()} - Last updated {round(time.time()-self.last_updated[region])}s ago"
        )
        return (
            embed,
            file,
            views.ProfileButton(region=region, user_id=ranking["userId"]),
        )

    # Create embed for leaderboard page
    @staticmethod
    def create_leaderboard_embed(
        ranked_data: dict,
        last_updated: dict,
        page: int,
        region: str,
        ranks_per_page: int = 25,
        season_name: str = "Unknown Season",
        pjsk_id: int = None,
    ):
        start = (page - 1) * ranks_per_page
        end = start + ranks_per_page
        rankings = ranked_data[region]["rankings"]

        embed = embeds.embed(
            title=f"Ranked {season_name} Leaderboard - Page {page}",
            color=discord.Color.purple(),
        )
        desc = ""
        newline = "\n"
        for ranking in rankings[start:end]:
            grade_details, grade = RankedCog.calculate_rank_details(ranking, region)
            gd0 = grade_details.split("\n")[0]
            gd1 = grade_details.split("\n")[1]
            desc += f"{'✅ ' if ranking['userId'] == pjsk_id else ''}**#{ranking['rank']} - {tools.escape_md(ranking['name'].replace(newline, ' '))}** - {gd0.replace('**', '') + ' (`' + gd1 + '`)'}\n"
        desc += f"\n\n### Web View: <https://sbuga.com/{region}/ranked>"
        embed.description = desc.strip()
        f_rank = ""
        if pjsk_id:
            for ranking in rankings:
                if ranking["userId"] == pjsk_id:
                    f_rank = f" - You are #{ranking['rank']}"
                    break
        embed.set_footer(
            text=f"Ranked Leaderboard - {region.upper()} - Last updated {round(time.time()-last_updated[region])}s ago"
            + f_rank
        )
        return embed

    # Command Group
    ranked = app_commands.Group(
        name=locale_str("cmds-ranked-name"),
        description=locale_str("cmds.ranked.desc"),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
    )

    @ranked.command(
        auto_locale_strings=False,
        name=locale_str("cmds-ranked-cmds-view-name"),
        description=locale_str("cmds.ranked.cmds.view.desc"),
    )
    @app_commands.describe(
        rank=locale_str("general.rank"),
        region=locale_str("general.region"),
    )
    @app_commands.autocomplete(
        rank=autocompletes.autocompletes.range(1, 100),
        region=autocompletes.autocompletes.pjsk_region(["en", "jp", "tw", "kr", "cn"]),
    )
    async def view(
        self,
        interaction: discord.Interaction,
        rank: int = None,
        region: str = "default",
    ):
        region = region.lower().strip()
        if region not in ["en", "jp", "tw", "kr", "cn", "default"]:
            return await interaction.response.send_message(
                embed=embeds.error_embed("Unsupported region."), ephemeral=True
            )
        if region == "default":
            region = await self.bot.user_data.discord.get_settings(
                interaction.user.id, "default_region"
            )
        await interaction.response.defer(ephemeral=False, thinking=True)
        self.update_rank_data(region=region)
        if rank is None:
            pass
        elif not 1 <= rank <= len(self.ranked_data[region]["rankings"]):
            return await interaction.followup.send(
                embed=embeds.error_embed(
                    title="Invalid Rank",
                    description="The specified rank couldn't be fetched.",
                )
            )
        is_self = False
        pjsk_id = await self.bot.user_data.discord.get_pjsk_id(
            interaction.user.id, region
        )
        f_rank = None
        if pjsk_id and (not rank):
            for ranking in self.ranked_data[region]["rankings"]:
                if ranking["userId"] == pjsk_id:
                    f_rank = ranking["rank"]
                    break
        elif not rank:
            return await interaction.followup.send(
                embed=embeds.error_embed(
                    title="Invalid Rank",
                    description="You didn't specify a rank and you are not linked to a PJSK account.",
                )
            )
        if f_rank:
            rank = f_rank
            is_self = True
        elif not rank:
            return await interaction.followup.send(
                embed=embeds.error_embed(
                    title="Not Found",
                    description=f"I didn't find you on the leaderboards, since you're not on them.\n**Leaderboards Last Updated:** `{round(time.time()-self.last_updated[region])}s ago`",
                )
            )
        if (
            is_self
            or pjsk_id == self.ranked_data[region]["rankings"][rank - 1]["userId"]
        ):
            is_self = True
        embed, file, view = self.create_rank_embed(rank, region=region, is_self=is_self)
        await interaction.followup.send(embed=embed, file=file, view=view)
        view.message = await interaction.original_response()

    @ranked.command(
        auto_locale_strings=False,
        name=locale_str("cmds-ranked-cmds-lb-name"),
        description=locale_str("cmds.ranked.cmds.lb.desc"),
    )
    @app_commands.describe(region=locale_str("general.region"))
    @app_commands.autocomplete(
        region=autocompletes.autocompletes.pjsk_region(["en", "jp", "tw", "kr", "cn"])
    )
    async def leaderboard(
        self, interaction: discord.Interaction, region: str = "default"
    ):
        region = region.lower().strip()
        if region not in ["en", "jp", "tw", "kr", "cn", "default"]:
            return await interaction.response.send_message(
                embed=embeds.error_embed("Unsupported region."), ephemeral=True
            )
        if region == "default":
            region = await self.bot.user_data.discord.get_settings(
                interaction.user.id, "default_region"
            )
        await interaction.response.defer(ephemeral=False, thinking=True)
        season_name = self.update_rank_data(region=region)
        total_pages = math.ceil(len(self.ranked_data[region]["rankings"]) / 25)
        pjsk_id = await self.bot.user_data.discord.get_pjsk_id(
            interaction.user.id, region
        )
        embed = self.create_leaderboard_embed(
            self.ranked_data,
            self.last_updated,
            page=1,
            region=region,
            season_name=season_name,
            pjsk_id=pjsk_id,
        )
        view = self.LeaderboardView(
            current_page=1,
            total_pages=total_pages,
            region=region,
            ranked_data=self.ranked_data,
            last_updated=self.last_updated,
            season_name=season_name,
            pjsk_id=pjsk_id,
        )
        await interaction.followup.send(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot: DiscordBot):
    await bot.add_cog(RankedCog(bot))
