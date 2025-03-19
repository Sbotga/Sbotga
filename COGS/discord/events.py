import discord
from discord import app_commands
from discord.ext import commands

from discord.app_commands import locale_str
from COGS.discord_translations import translations

from main import DiscordBot

import math, time, json, os
from datetime import datetime, timedelta, timezone

import aiohttp

from DATA.game_api import methods

from DATA.helpers import converters
from DATA.helpers import discord_autocompletes as autocompletes
from DATA.helpers import views
from DATA.helpers import embeds
from DATA.helpers import views
from DATA.helpers import tools


class EventsCog(commands.Cog):
    def __init__(self, bot: DiscordBot):
        self.bot = bot
        self.ranking_data = {
            api.app_region: {"rankings": []} for api in methods.all_apis
        }
        self.ranking_data["border"] = {
            api.app_region: {"borderRankings": []} for api in methods.all_apis
        }
        self.last_updated = {api.app_region: 0 for api in methods.all_apis}

        self.update_cooldown = 00  # 1 minute

        if os.path.exists("DATA/data/ASSETS/events/top100.json"):
            with open("DATA/data/ASSETS/events/top100.json", "r") as f:
                data = json.load(f)
                for k, v in data["data"].items():
                    self.ranking_data[k] = v
                for k, v in data["last_updated"].items():
                    self.last_updated[k] = v

    def update_rank_data(self, region: str, force: bool = False) -> str:
        api = methods.Tools.get_api(region)
        if force or self.last_updated[region] + self.update_cooldown < time.time():
            try:
                self.ranking_data[region] = api.get_event_leaderboard()
                self.ranking_data["border"][region] = api.get_event_border()
                self.last_updated[region] = time.time()
                if not os.path.exists(f"DATA/data/ASSETS/events/"):
                    os.mkdir(f"DATA/data/ASSETS/events/")
                with open(f"DATA/data/ASSETS/events/top100.json", "w+") as f:
                    json.dump(
                        {
                            "last_updated": self.last_updated,
                            "data": self.ranking_data,
                        },
                        f,
                    )
            except Exception as e:
                self.bot.traceback(e)
                # pass
        data = api.get_master_data("events.json")
        for i in range(0, len(data)):
            startAt = data[i]["startAt"]
            endAt = data[i]["closedAt"]
            assetbundleName = data[i]["assetbundleName"]
            now = int(round(time.time() * 1000))
            remain = ""
            if not startAt < now < endAt:
                continue
            if data[i]["startAt"] < now < data[i]["aggregateAt"]:
                status = "going"
                # remain = timeremain(time=(data[i]['aggregateAt'] - now) / 1000, server=server)
            elif data[i]["aggregateAt"] < now < data[i]["aggregateAt"] + 600000:
                status = "counting"
            else:
                status = "end"
            return data[i]["name"]

    class LeaderboardView(views.SbotgaView):
        def __init__(
            self,
            current_page: int,
            total_pages: int,
            region: str,
            ranking_data: dict,
            last_updated: dict,
            event_name: str,
            character: dict,
            pjsk_id: int,
            border: bool = False,
        ):
            super().__init__()
            self.current_page = current_page
            self.total_pages = total_pages
            self.current_region = region
            self.ranking_data = ranking_data
            self.last_updated = last_updated
            self.event_name = event_name
            self.character = character
            self.pjsk_id = pjsk_id
            self.border = border
            self.update_buttons()

        def update_buttons(self):
            self.previous_page.disabled = self.current_page == 1
            self.next_page.disabled = self.current_page == self.total_pages

        async def update_message(self, interaction: discord.Interaction):
            embed, file = EventsCog.create_leaderboard_embed(
                self.ranking_data,
                self.last_updated,
                self.current_page,
                self.current_region,
                event_name=self.event_name,
                character=self.character,
                pjsk_id=self.pjsk_id,
                border=self.border,
            )
            self.update_buttons()
            try:
                await interaction.followup.edit_message(
                    interaction.message.id, embed=embed, view=self, attachments=[file]
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

    # Calculate Rank Class Details
    @staticmethod
    def calculate_rank_details(ranking, region: str, character: str = None):
        return f"`{ranking['score']:,} EP`"

    def create_rank_embed(
        self,
        rank: int,
        region: str,
        event_id: int,
        is_self: bool,
        character: dict = None,
    ):
        if character:
            name = (
                str(character["givenName"]) + " " + str(character["firstName"])
                if character.get("firstName") and character.get("unit") != "piapro"
                else (
                    str(character["firstName"]) + " " + str(character["givenName"])
                    if character.get("firstName")
                    else character["givenName"]
                )
            ) + " "
        else:
            name = ""
        if not character:
            ranking = self.ranking_data[region]["rankings"][rank - 1]
        else:
            f = False
            ranking = self.ranking_data[region]
            for chapter in ranking["userWorldBloomChapterRankings"]:
                if chapter["gameCharacterId"] == character["id"]:
                    f = True
                    ranking = chapter["rankings"][rank - 1]
                    break
            if not f:
                embed = embeds.error_embed(
                    f"Character not found for current event!\n-# Occurs if the current event is NOT a World Link, or the wrong character is given."
                )
                embed.set_footer(
                    text=f"Event Statistics - {region.upper()} - Last updated {round(time.time()-self.last_updated[region])}s ago"
                )
                return (
                    embed,
                    discord.utils.MISSING,  # file,
                    discord.utils.MISSING,  # view
                )

        score = ranking["score"]
        score = EventsCog.calculate_rank_details(ranking, region, character)

        embed = embeds.embed(
            title=f"{name}Rank #{ranking['rank']} - {tools.escape_md(ranking['name'] if len(ranking['name']) < 50 else (ranking['name'][:43] + '... ⚠️ (I will not display your very long name)'))}",
            color=discord.Color.yellow(),
        )
        desc_text = ""
        if is_self:
            desc_text = "✅ This is you!\n"
        desc_text += f"## {score}" + (
            f"\n{name.strip()}'s Chapter Only." if name != "" else ""
        )

        # calculate border
        borders = (
            list(range(1, 6))
            + list(range(10, 101, 10))
            + list(range(200, 501, 100))
            + list(range(1000, 3001, 500))
            + list(range(4000, 5001, 1000))
            + list(range(10_000, 50_001, 10_000))
            + list(range(100_000, 300_001, 100_000))
        )

        def find_next_border(rank):
            if rank == 1:
                return None
            return next((b for b in borders if b < rank), None)

        current_ep = ranking["score"]
        up_border = find_next_border(ranking["rank"])

        if up_border:
            if character:
                f = False
                if up_border < 100:
                    ranking = self.ranking_data[region]
                    for chapter in ranking["userWorldBloomChapterRankings"]:
                        if chapter["gameCharacterId"] == character["id"]:
                            f = True
                            darankings = chapter["rankings"]
                            break
                else:
                    ranking = self.ranking_data["border"][region]
                    for chapter in ranking["userWorldBloomChapterRankingBorders"]:
                        if chapter["gameCharacterId"] == character["id"]:
                            f = True
                            darankings = chapter["borderRankings"]
                            break
                if not f:
                    # ??? this should probably never happen.
                    pass
            else:
                if up_border < 100:
                    darankings = self.ranking_data[region]["rankings"]
                else:
                    darankings = self.ranking_data["border"][region]["borderRankings"]

            for rank in darankings:
                if rank["rank"] == int(up_border):
                    border_ep = rank["score"]
                    break
            desc_text += f"\n\nThe next border is **T{up_border}**, at `{border_ep:,} EP`, which is `+{border_ep-current_ep:,} EP` away."
        else:
            pass

        embed.description = desc_text
        logo, _, _ = methods.Tools.get_event_images(event_id, region)
        file = discord.File(
            logo,
            filename="image.png",
        )
        embed.set_thumbnail(url="attachment://image.png")

        embed.set_footer(
            text=f"Event Statistics{' - ' + name.strip() if name != '' else ''} - {region.upper()} - Last updated {round(time.time()-self.last_updated[region])}s ago"
        )
        return (
            embed,
            file,
            views.ProfileButton(region=region, user_id=ranking["userId"]),
        )

    # Create embed for leaderboard page
    @staticmethod
    def create_leaderboard_embed(
        ranking_data: dict,
        last_updated: dict,
        page: int,
        region: str,
        ranks_per_page: int = 25,
        event_name: str = "Unknown Event",
        character: dict = None,
        pjsk_id: int = None,
        border: bool = False,
    ):
        event_id = methods.Tools.get_api(region).get_current_event()
        if character:
            name = (
                str(character["givenName"]) + " " + str(character["firstName"])
                if character.get("firstName") and character.get("unit") != "piapro"
                else (
                    str(character["firstName"]) + " " + str(character["givenName"])
                    if character.get("firstName")
                    else character["givenName"]
                )
            ) + " "
        else:
            name = ""
        start = (page - 1) * ranks_per_page
        end = start + ranks_per_page
        if not character:
            rankings = ranking_data[region][
                "rankings" if not border else "borderRankings"
            ]
            if border:
                rankings = rankings[::-1]
        else:
            f = False
            rankings = ranking_data[region]
            for chapter in rankings[
                (
                    "userWorldBloomChapterRankings"
                    if not border
                    else "userWorldBloomChapterRankingBorders"
                )
            ]:
                if chapter["gameCharacterId"] == character["id"]:
                    f = True
                    rankings = chapter["rankings" if not border else "borderRankings"]
                    if border:
                        rankings = rankings[::-1]
                    break
            if not f:
                embed = embeds.error_embed(
                    f"Character not found for current event!\n-# Occurs if the current event is NOT a World Link, or the wrong character is given."
                )
                embed.set_footer(
                    text=f"Event Statistics - {region.upper()} - Last updated {round(time.time()-last_updated[region])}s ago"
                )
                return embed

        embed = embeds.embed(
            title=f"{event_name}{' - ' + name.strip() if name != '' else ''} {'Leaderboard' if not border else 'Borders'}{(' - Page ' + str(page)) if not border else ''}",
            color=discord.Color.purple(),
        )
        desc = ""
        newline = "\n"
        for ranking in rankings[start:end]:
            score = EventsCog.calculate_rank_details(ranking, region)
            desc += f"{'✅ ' if ranking['userId'] == pjsk_id else ''}**#{ranking['rank']:,} - {tools.escape_md(ranking['name'].replace(newline, ' '))}** - {score}\n"
        embed.description = desc.strip()
        f_rank = ""
        if pjsk_id:
            for ranking in rankings:
                if ranking["userId"] == pjsk_id:
                    f_rank = f" - You are #{ranking['rank']:,}"
                    break
        embed.set_footer(
            text=f"Event {'Leaderboard' if not border else 'Borders'}{' - ' + name.strip() if name != '' else ''} - {region.upper()} - Last updated {round(time.time()-last_updated[region])}s ago"
            + f_rank
        )
        logo, _, _ = methods.Tools.get_event_images(event_id, region)
        file = discord.File(
            logo,
            filename="image.png",
        )
        embed.set_thumbnail(url="attachment://image.png")
        return embed, file

    # Command Group
    event = app_commands.Group(
        name=locale_str("events", key="events.name", file="commands"),
        description=locale_str("events.desc", file="commands"),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
    )

    @event.command(
        auto_locale_strings=False,
        name=locale_str("view", key="events.cmds.view.name", file="commands"),
        description=locale_str("events.cmds.view.desc", file="commands"),
    )
    @app_commands.describe(
        rank=locale_str("general.rank"),
        region=locale_str("general.region"),
        character=locale_str("general.event_wl_character"),
    )
    @app_commands.autocomplete(
        rank=autocompletes.autocompletes.range(1, 100),
        region=autocompletes.autocompletes.pjsk_region(["en", "jp", "tw", "kr", "cn"]),
        character=autocompletes.autocompletes.pjsk_char,
    )
    async def view(
        self,
        interaction: discord.Interaction,
        rank: int = None,
        region: str = "default",
        character: str = None,
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
        if region == "default":
            region = await self.bot.user_data.discord.get_settings(
                interaction.user.id, "default_region"
            )

        await interaction.response.defer(thinking=True)
        self.update_rank_data(region=region)

        if character:
            character = converters.CharFromPJSK(self.bot.pjsk, character)
            if not character:
                return await interaction.followup.send(
                    embed=embeds.error_embed("Invalid character."),
                )
            f = False
            ranking = self.ranking_data[region]
            for chapter in ranking["userWorldBloomChapterRankings"]:
                if chapter["gameCharacterId"] == character["id"]:
                    f = True
                    darankings = chapter["rankings"]
                    break
            if not f:
                embed = embeds.error_embed(
                    f"Character not found for current event!\n-# Occurs if the current event is NOT a World Link, or the wrong character is given.",
                )
                return await interaction.followup.send(embed=embed)
        else:
            darankings = self.ranking_data[region]["rankings"]
        if rank is None:
            pass
        elif not (1 <= rank <= len(darankings)):
            return await interaction.followup.send(
                embed=embeds.error_embed(
                    "The specified rank couldn't be fetched.", title="Invalid Rank"
                )
            )
        is_self = False
        pjsk_id = await self.bot.user_data.discord.get_pjsk_id(
            interaction.user.id, region
        )
        f_rank = None
        if pjsk_id and (not rank):
            for ranking in darankings:
                if ranking["userId"] == pjsk_id:
                    f_rank = ranking["rank"]
                    break
        elif not rank:
            return await interaction.followup.send(
                embed=embeds.error_embed(
                    "You didn't specify a rank and you are not linked to a PJSK account.",
                    title="Invalid Rank",
                )
            )
        if f_rank:
            rank = f_rank
            is_self = True
        elif not rank:
            if character:
                name = (
                    str(character["givenName"]) + " " + str(character["firstName"])
                    if character.get("firstName") and character.get("unit") != "piapro"
                    else (
                        str(character["firstName"]) + " " + str(character["givenName"])
                        if character.get("firstName")
                        else character["givenName"]
                    )
                ) + " "
            else:
                name = ""
            return await interaction.followup.send(
                embed=embeds.error_embed(
                    title="Not Found",
                    description=f"I didn't find you on the {character}leaderboards, since you're not on them.\n**Leaderboards Last Updated:** `{round(time.time()-self.last_updated[region])}s ago`",
                )
            )
        if is_self or pjsk_id == darankings[rank - 1]["userId"]:
            is_self = True
        embed, file, view = self.create_rank_embed(
            rank,
            region=region,
            event_id=methods.Tools.get_api(region).get_current_event(),
            is_self=is_self,
            character=character,
        )
        await interaction.followup.send(embed=embed, file=file, view=view)

    @event.command(
        auto_locale_strings=False,
        name=locale_str(
            "leaderboard", key="events.cmds.leaderboard.name", file="commands"
        ),
        description=locale_str("events.cmds.leaderboard.desc", file="commands"),
    )
    @app_commands.describe(
        region=locale_str("general.region"),
        character=locale_str("general.event_wl_character"),
    )
    @app_commands.autocomplete(
        region=autocompletes.autocompletes.pjsk_region(["en", "jp", "tw", "kr", "cn"]),
        character=autocompletes.autocompletes.pjsk_char,
    )
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        region: str = "default",
        character: str = None,
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
        if region == "default":
            region = await self.bot.user_data.discord.get_settings(
                interaction.user.id, "default_region"
            )

        await interaction.response.defer(thinking=True)
        event_name = self.update_rank_data(region=region)

        if character:
            character = converters.CharFromPJSK(self.bot.pjsk, character)
            if not character:
                return await interaction.followup.send(
                    embed=embeds.error_embed("Invalid character."),
                )
            f = False
            ranking = self.ranking_data[region]
            for chapter in ranking["userWorldBloomChapterRankings"]:
                if chapter["gameCharacterId"] == character["id"]:
                    f = True
                    darankings = chapter["rankings"]
                    break
            if not f:
                embed = embeds.error_embed(
                    f"Character not found for current event!\n-# Occurs if the current event is NOT a World Link, or the wrong character is given.",
                )
                return await interaction.followup.send(embed=embed)
        else:
            darankings = self.ranking_data[region]["rankings"]

        total_pages = math.ceil(len(darankings) / 25)

        if total_pages == 0:
            embed = embeds.error_embed(
                f"Character chapter has not started.",
            )
            return await interaction.followup.send(embed=embed)

        pjsk_id = await self.bot.user_data.discord.get_pjsk_id(
            interaction.user.id, region
        )
        embed, file = self.create_leaderboard_embed(
            self.ranking_data,
            self.last_updated,
            page=1,
            region=region,
            event_name=event_name,
            character=character,
            pjsk_id=pjsk_id,
            border=False,
        )
        view = self.LeaderboardView(
            current_page=1,
            total_pages=total_pages,
            region=region,
            ranking_data=self.ranking_data,
            last_updated=self.last_updated,
            event_name=event_name,
            character=character,
            pjsk_id=pjsk_id,
        )
        await interaction.followup.send(embed=embed, view=view, file=file)
        view.message = await interaction.original_response()

    def get_next_reset(self):
        """
        Obtains the time of the next daily reset in game.
        """
        current_date = datetime.now(timezone("UTC"))
        pst = timezone("America/Los_Angeles")
        next_reset = current_date.astimezone(pst).replace(
            hour=4, minute=0, second=0, microsecond=0
        )

        if next_reset < current_date.astimezone(pst):
            next_reset += timedelta(days=1)

        return int(next_reset.timestamp())

    def create_schedule_embed(self, data: dict, region: str):
        """
        Creates an embed of the current schedule data provided.
        """
        current_date = datetime.now(timezone.utc)

        current_event_idx = -1
        next_event_idx = -1

        for i, event in enumerate(data):
            start_at = datetime.fromtimestamp(
                round(event["startAt"] / 1000), timezone.utc
            )
            closed_at = datetime.fromtimestamp(
                round(event["closedAt"] / 1000), timezone.utc
            )

            if closed_at > current_date > start_at:
                current_event_idx = i

            if start_at > current_date:
                if next_event_idx == -1 or start_at < datetime.fromtimestamp(
                    round(data[next_event_idx]["startAt"] / 1000), timezone.utc
                ):
                    next_event_idx = i

        embed = embeds.embed(
            color=discord.Color.dark_blue(),
            title=f"{region.upper()} Event Schedule",
            description="",
        )

        if current_event_idx != -1:
            current_event = data[current_event_idx]
            start_time = round(current_event["startAt"] / 1000)
            aggregate_time = round(current_event["aggregateAt"] / 1000)

            embed.add_field(
                name=f"**__Current Event__** ({current_event['id']})",
                value=f"{current_event['name']} - **{self.bot.pjsk.event_type_map[current_event['eventType']]}**",
                inline=False,
            )
            embed.add_field(
                name="Event Started", value=f"<t:{start_time}> - <t:{start_time}:R>"
            )
            embed.add_field(
                name="Ranking Closes",
                value=f"<t:{aggregate_time}> - <t:{aggregate_time}:R>",
            )

            embed.set_thumbnail(
                url=f"https://sekai-res.dnaroma.eu/file/sekai-en-assets/event/{current_event['assetbundleName']}/logo_rip/logo.webp"
            )

        if next_event_idx != -1:
            if current_event_idx != -1:
                embed.add_field(name="** **", value="** **", inline=False)

            next_event = data[next_event_idx]
            start_time = round(next_event["startAt"] / 1000)
            aggregate_time = round(next_event["aggregateAt"] / 1000)

            embed.add_field(
                name=f"**__Next Event__** ({next_event['id']})",
                value=f"{next_event['name']} - **{self.bot.pjsk.event_type_map[next_event['eventType']]}**",
                inline=False,
            )
            embed.add_field(
                name="Event Starts", value=f"<t:{start_time}> - <t:{start_time}:R>"
            )
            embed.add_field(
                name="Ranking Closes",
                value=f"<t:{aggregate_time}> - <t:{aggregate_time}:R>",
            )

        embed.timestamp = discord.utils.utcnow()
        return embed

    @event.command(
        auto_locale_strings=False,
        name=locale_str("schedule", key="events.cmds.schedule.name", file="commands"),
        description=locale_str("events.cmds.schedule.desc", file="commands"),
    )
    @app_commands.describe(
        region=locale_str("general.region"),
    )
    @app_commands.autocomplete(
        region=autocompletes.autocompletes.pjsk_region(["en", "jp", "tw", "kr", "cn"]),
    )
    async def schedule(
        self,
        interaction: discord.Interaction,
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
        await interaction.response.defer(thinking=True)
        if region == "default":
            region = await self.bot.user_data.discord.get_settings(
                interaction.user.id, "default_region"
            )
        api = methods.Tools.get_api(region)
        events = api.get_master_data("events.json")
        embed = self.create_schedule_embed(events, region)
        await interaction.followup.send(embed=embed)

    @event.command(
        auto_locale_strings=False,
        name=locale_str("border", key="events.cmds.border.name", file="commands"),
        description=locale_str("events.cmds.border.desc", file="commands"),
    )
    @app_commands.describe(
        region=locale_str("general.region"),
        character=locale_str("general.event_wl_character"),
    )
    @app_commands.autocomplete(
        region=autocompletes.autocompletes.pjsk_region(["en", "jp", "tw", "kr", "cn"]),
        character=autocompletes.autocompletes.pjsk_char,
    )
    async def border(
        self,
        interaction: discord.Interaction,
        region: str = "default",
        character: str = None,
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
        if region == "default":
            region = await self.bot.user_data.discord.get_settings(
                interaction.user.id, "default_region"
            )

        await interaction.response.defer(thinking=True)
        event_name = self.update_rank_data(region=region)

        if character:
            character = converters.CharFromPJSK(self.bot.pjsk, character)
            if not character:
                return await interaction.followup.send(
                    embed=embeds.error_embed("Invalid character."),
                )
            f = False
            ranking = self.ranking_data["border"][region]
            for chapter in ranking["userWorldBloomChapterRankingBorders"]:
                if chapter["gameCharacterId"] == character["id"]:
                    f = True
                    darankings = chapter["borderRankings"]
                    break
            if not f:
                embed = embeds.error_embed(
                    f"Character not found for current event!\n-# Occurs if the current event is NOT a World Link, or the wrong character is given.",
                )
                return await interaction.followup.send(embed=embed)
        else:
            darankings = self.ranking_data["border"][region]["borderRankings"]

        total_pages = math.ceil(len(darankings) / 25)

        if total_pages == 0:
            embed = embeds.error_embed(
                f"Character chapter has not started.",
            )
            return await interaction.followup.send(embed=embed)

        pjsk_id = await self.bot.user_data.discord.get_pjsk_id(
            interaction.user.id, region
        )
        embed, file = self.create_leaderboard_embed(
            self.ranking_data["border"],
            self.last_updated,
            page=1,
            region=region,
            event_name=event_name,
            character=character,
            pjsk_id=pjsk_id,
            border=True,
        )
        await interaction.followup.send(embed=embed, file=file)

    @event.command(
        auto_locale_strings=False,
        name=locale_str("predict", key="events.cmds.predict.name", file="commands"),
        description=locale_str("events.cmds.predict.desc", file="commands"),
    )
    @app_commands.describe(
        tier=locale_str("general.rank"),
        region=locale_str("general.region"),
        character=locale_str("general.event_wl_character"),
    )
    @app_commands.autocomplete(
        tier=autocompletes.autocompletes.custom_values(
            {
                "T1": "1",
                "T2": "2",
                "T3": "3",
                "T10": "10",
                "T20": "20",
                "T30": "30",
                "T40": "40",
                "T50": "50",
                "T100": "100",
                "T200": "200",
                "T300": "300",
                "T400": "400",
                "T500": "500",
                "T1000": "1000",
                "T1500": "1500",
                "T2000": "2000",
                "T2500": "2500",
                "T3000": "3000",
                "T4000": "4000",
                "T5000": "5000",
                "T10000": "10000",
            }
        ),
        region=autocompletes.autocompletes.pjsk_region(["en", "jp", "tw", "kr", "cn"]),
        character=autocompletes.autocompletes.pjsk_char,
    )
    async def predict(
        self,
        interaction: discord.Interaction,
        tier: str,
        region: str = "default",
        character: str = None,
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
        tier = tier.lower().strip().removeprefix("t")
        if tier not in [
            "1",
            "2",
            "3",
            "10",
            "20",
            "30",
            "40",
            "50",
            "100",
            "200",
            "300",
            "400",
            "500",
            "1000",
            "1500",
            "2000",
            "2500",
            "3000",
            "4000",
            "5000",
            "10000",
        ]:
            return await interaction.response.send_message(
                embed=embeds.error_embed("Unsupported tier."), ephemeral=True
            )
        if region == "default":
            region = await self.bot.user_data.discord.get_settings(
                interaction.user.id, "default_region"
            )

        await interaction.response.defer(thinking=True)
        event_name = self.update_rank_data(region=region)

        if character:
            character = converters.CharFromPJSK(self.bot.pjsk, character)
            if not character:
                return await interaction.followup.send(
                    embed=embeds.error_embed("Invalid character.")
                )
            f = False
            if int(tier) < 100:
                ranking = self.ranking_data[region]
                for chapter in ranking["userWorldBloomChapterRankings"]:
                    if chapter["gameCharacterId"] == character["id"]:
                        f = True
                        darankings = chapter["rankings"]
                        break
            else:
                ranking = self.ranking_data["border"][region]
                for chapter in ranking["userWorldBloomChapterRankingBorders"]:
                    if chapter["gameCharacterId"] == character["id"]:
                        f = True
                        darankings = chapter["borderRankings"]
                        break
            if not f:
                embed = embeds.error_embed(
                    f"Character not found for current event!\n-# Occurs if the current event is NOT a World Link, or the wrong character is given.",
                )
                return await interaction.followup.send(embed=embed)
        else:
            if int(tier) < 100:
                darankings = self.ranking_data[region]["rankings"]
            else:
                darankings = self.ranking_data["border"][region]["borderRankings"]

        api = methods.Tools.get_api(region)
        world_link = False
        if (
            len(
                self.ranking_data["border"][region][
                    "userWorldBloomChapterRankingBorders"
                ]
            )
            > 0
        ):
            if not character:
                embed = embeds.error_embed(
                    f"Predictions for the overall ranking in World Link are not supported, as they are too dependent on the character sequence.\n\nInstead, why don't you try predicting the current chapter?",
                )
                return await interaction.followup.send(embed=embed)

            world_link_data = api.get_master_data("worldBlooms.json")
            world_link = True

        url = f"https://raw.githubusercontent.com/Jiiku831/Jiiku831.github.io/refs/heads/main/{region + '/' if region != 'jp' else ''}data/sekarun_current.json"

        async with aiohttp.ClientSession() as cs:
            async with cs.get(url) as resp:
                data = await resp.json(content_type=None)

        for rank in darankings:
            if rank["rank"] == int(tier):
                current_ep = rank["score"]
                break

        total_pages = math.ceil(len(darankings) / 25)

        if total_pages == 0:
            embed = embeds.error_embed(
                f"Character chapter has not started.",
            )
            return await interaction.followup.send(embed=embed)

        current_event = api.get_current_event(return_data=True)
        current_sekarun = data["event_id"]

        if current_event["id"] != current_sekarun:
            embed = embeds.error_embed(
                f"No predictions found. Sorry about that!",
            )
            return await interaction.followup.send(embed=embed)

        if world_link:
            chapters = data["chapters"]
            for _, chapter_data in chapters.items():
                world_bloom_id = chapter_data["world_bloom_id"]
                wl_chap_data = next(
                    (
                        wl_data
                        for wl_data in world_link_data
                        if wl_data["id"] == world_bloom_id
                    ),
                    None,
                )
                if wl_chap_data["gameCharacterId"] == character["id"]:
                    entries = chapter_data["lines"][tier]["entries"]
                    aggregate = wl_chap_data["aggregateAt"]
                    start = wl_chap_data["chapterStartAt"]
                    break
        else:
            entries = data["lines"][tier]["entries"]
            aggregate = current_event["aggregateAt"]
            start = current_event["startAt"]

        for entry in entries:
            if (
                entry["entry_type"] == "p"
                and entry["border"] == int(tier)
                and entry["timestamp"] in [aggregate // 1000, (aggregate // 1000) + 1]
            ):
                pred = entry
                break

        progress = ((time.time() * 1000 - start) / (aggregate - start)) * 100
        percent = f"{min(max(progress, 0), 100):.2f}%"

        pred_eb = round(pred["ep"])
        pred_eb_lb = round(pred["ep_lb"])  # lower boundary
        pred_eb_ub = round(pred["ep_ub"])  # upper boundary

        pred_ub_diff = pred_eb_ub - pred_eb
        pred_lb_diff = pred_eb - pred_eb_lb
        if -1000 < (pred_ub_diff - pred_lb_diff) < 1000:
            pred_ub_diff = pred_lb_diff = (pred_ub_diff + pred_lb_diff) // 2

        pred_diff = (
            f"+{pred_ub_diff:,}, -{pred_lb_diff:,}"
            if pred_ub_diff != pred_lb_diff
            else f"±{pred_ub_diff:,}"
        )

        embed = embeds.embed(
            title=f"{event_name} - T{int(tier):,} Prediction",  # TODO: character name
            description=f"The event ends {discord.utils.format_dt(datetime.fromtimestamp(aggregate//1000), style='R')}, and started {discord.utils.format_dt(datetime.fromtimestamp(start//1000), style='R')}. This event is currently `{percent}` complete.\n\n**Current EP:** `{current_ep:,}`\n**Predicted EP:** `{pred_eb:,}` (`{pred_diff}`)",
        )

        logo, _, _ = methods.Tools.get_event_images(current_event["id"], region)
        file = discord.File(
            logo,
            filename="image.png",
        )
        embed.set_thumbnail(url="attachment://image.png")
        embed.set_footer(
            text=f"Event T{int(tier):,} Prediction - {region.upper()} - Current EP Last Updated {round(time.time()-self.last_updated[region])}s ago"
        )

        if region != "jp":  # TODO: remove warning after 2025/04
            embed.add_field(
                name="⚠️WARNING",
                value="Only JP predictions are completely accurate; this is due to EN/TW/KR not having any previous data.",
                inline=False,
            )
        await interaction.followup.send(embed=embed, file=file)


async def setup(bot: DiscordBot):
    await bot.add_cog(EventsCog(bot))
