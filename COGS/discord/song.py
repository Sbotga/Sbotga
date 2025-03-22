import discord
from discord.ext import commands
from discord import app_commands

from discord.app_commands import locale_str
from COGS.discord_translations import translations

from main import DiscordBot

import time, datetime, csv, math, asyncio
from io import BytesIO, StringIO

from PIL import Image, ImageFilter
import aiohttp

from DATA.game_api import methods

from DATA.helpers import discord_autocompletes as autocompletes
from DATA.helpers import converters
from DATA.helpers.discord_emojis import emojis
from DATA.helpers import views
from DATA.helpers import embeds
from DATA.helpers.unblock import to_process_with_timeout
from DATA.helpers import pjsk_chart

from DATA.data.pjsk import Song, pjsk as pjsk_data_obj


class SongInfo(commands.Cog):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    song = app_commands.Group(
        name="song", description="Commands related to PJSK songs."
    )

    @song.command(
        auto_locale_strings=False, name="jacket", description="View song jacket large."
    )
    @app_commands.autocomplete(song=autocompletes.autocompletes.pjsk_song)
    @app_commands.describe(song=locale_str("general.song_name"))
    async def song_jacket(self, interaction: discord.Interaction, song: str):
        await interaction.response.defer(ephemeral=False, thinking=True)
        osong = song
        song: Song = converters.SongFromPJSK(self.bot.pjsk, song)
        if song is None:
            embed = embeds.error_embed(
                await interaction.translate(
                    locale_str("errors.unknown_song", replacements={"{song}": osong})
                ),
            )
            await interaction.followup.send(embed=embed)
            return
        leak = methods.Tools.isleak(song.id)
        if leak:
            embed = embeds.leak_embed()
            await interaction.followup.send(embed=embed)
            return
        embed = embeds.embed(title=song.title)
        embed.set_image(url="attachment://jacket.png")
        file = discord.File(methods.Tools.get_music_jacket(song.id), "jacket.png")
        await interaction.followup.send(embed=embed, file=file)

    @song.command(
        auto_locale_strings=False,
        name="progress",
        description="View your own progress on a specific song.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.autocomplete(
        region=autocompletes.autocompletes.pjsk_region(
            ["en", "jp", "tw", "kr", "cn", "all"]
        ),
        song=autocompletes.autocompletes.pjsk_song,
    )
    @app_commands.describe(
        region=locale_str("general.region"),
        song=locale_str("general.song_name"),
    )
    async def song_progress(
        self,
        interaction: discord.Interaction,
        song: str,
        region: str = "default",
    ):
        region = region.lower().strip()
        if region not in ["en", "jp", "tw", "kr", "cn", "all", "default"]:
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
        if region != "all":
            pjsk_id = await self.bot.user_data.discord.get_pjsk_id(
                interaction.user.id, region
            )
            if not pjsk_id:
                return await interaction.followup.send(
                    embed=embeds.error_embed(
                        f"You are not linked to a PJSK {region.upper()} account."
                    ),
                )
            api = methods.Tools.get_api(region)
            data = api.attempt_get_user_data(pjsk_id)
            if not data:
                embed = embeds.error_embed(
                    f"I don't have access to your {region.upper()} account data.\n\nThis requires a temporary data transfer. </user pjsk update_data:1325347278805929994>",
                )
                return await interaction.followup.send(embed=embed)
            data = {region: data}
        else:
            data = {}
            for api, r in [(api, api.app_region) for api in methods.all_apis]:
                pjsk_id = await self.bot.user_data.discord.get_pjsk_id(
                    interaction.user.id, r
                )
                if not pjsk_id:
                    continue
                acc_data = api.attempt_get_user_data(pjsk_id)
                if not acc_data:
                    continue
                data[r] = acc_data
            if not data:
                embed = embeds.error_embed(
                    "I don't have access to your **any** of your account data.\n\nThis requires a temporary data transfer. </user pjsk update_data:1325347278805929994>",
                )
                return await interaction.followup.send(embed=embed)

        osong = song
        song: Song = converters.SongFromPJSK(self.bot.pjsk, song)
        if song is None:
            embed = embeds.error_embed(
                await interaction.translate(
                    locale_str("errors.unknown_song", replacements={"{song}": osong})
                ),
            )
            await interaction.followup.send(embed=embed)
            return
        if methods.Tools.isleak(song.id):
            embed = embeds.leak_embed()
            await interaction.followup.send(embed=embed)
            return
        if any(
            api.isleak(song.id)
            for api in [
                a for a in methods.all_apis if a.app_region in list(data.keys())
            ]
        ):
            embed = embeds.error_embed(
                "The song is not available on any of the regions specified."
            )
            await interaction.followup.send(embed=embed)
            return

        # Define playResult priorities
        RESULT_PRIORITY = {
            "full_perfect": 4,
            "full_combo": 3,
            "clear": 2,
            "not_clear": 1,
            None: 0,
        }

        append_indicators = {
            "ap": "DATA/data/ASSETS/append_ap.png",
            "fc": "DATA/data/ASSETS/append_fc.png",
            "clear": "DATA/data/ASSETS/append_clear.png",
            "none": "DATA/data/ASSETS/append_fail.png",
        }
        indicators = {
            "ap": "DATA/data/ASSETS/normal_ap.png",
            "fc": "DATA/data/ASSETS/normal_fc.png",
            "clear": "DATA/data/ASSETS/normal_clear.png",
            "none": "DATA/data/ASSETS/normal_fail.png",
        }

        def _make():
            has_append = False

            last_updated = []
            diffs = [None] * 6

            for r, d in data.items():
                # Add last_updated entry
                last_updated.append(
                    f"{r.upper()} - {int(time.time() - d['now'] / 1000)}s ago"
                )

                song_progress_info = {}
                for song_data in d["userMusics"]:
                    if song_data["musicId"] == song.id:
                        song_progress_info = song_data["userMusicDifficultyStatuses"]
                        break

                for i, difficulty in enumerate(song_progress_info):
                    c_d = diffs[i]

                    if i == 5:
                        has_append = True

                    for result in difficulty["userMusicResults"]:
                        res = result["playResult"]

                        # Compare current result with existing one based on priority
                        if c_d is None or RESULT_PRIORITY[res] > RESULT_PRIORITY[c_d]:
                            c_d = res

                    diffs[i] = c_d

            jacket = methods.Tools.get_music_jacket(song.id)
            img = Image.open(jacket)
            img_width, img_height = img.size

            # Indicator settings
            difficulty_labels = ["easy", "normal", "hard", "expert", "master", "append"]
            indicator_size = (75, 75)
            padding = 15

            start_x = padding
            start_y = img_height - indicator_size[1] - padding

            status_map = {
                None: "none",
                "clear": "clear",
                "full_combo": "fc",
                "full_perfect": "ap",
                "not_clear": "none",
            }

            for i, difficulty in enumerate(difficulty_labels):
                if i == 5 and not has_append:
                    continue  # skip append

                status = diffs[i] if i < len(diffs) else "none"
                indicator_path = (
                    append_indicators[status_map[status]]
                    if i == 5
                    else indicators[status_map[status]]
                )

                indicator = Image.open(indicator_path).resize(indicator_size)

                padding = 15  # transparent padding to fit stroke
                expanded_size = (
                    indicator_size[0] + padding * 2,
                    indicator_size[1] + padding * 2,
                )

                expanded_indicator = Image.new("RGBA", expanded_size, (0, 0, 0, 0))
                expanded_indicator.paste(
                    indicator,
                    (padding, padding),
                    indicator if indicator.mode == "RGBA" else None,
                )
                mask = expanded_indicator.split()[3]

                stroke_thickness = 9  # Adjust stroke thickness (odd numbers only)
                expanded_mask = mask.filter(ImageFilter.MaxFilter(stroke_thickness))

                stroke = Image.new(
                    "RGBA", expanded_size, (255, 255, 255, int(255 * 0.7))
                )  # white stroke with 70% opacity
                expanded_indicator.paste(stroke, (0, 0), expanded_mask)

                expanded_indicator.paste(
                    indicator,
                    (padding, padding),
                    indicator if indicator.mode == "RGBA" else None,
                )

                img.paste(
                    expanded_indicator,
                    (start_x - padding, start_y - padding),
                    expanded_indicator,
                )

                start_x += indicator_size[0] + padding

            edited_img = BytesIO()
            img.save(edited_img, "PNG")
            edited_img.seek(0)
            return edited_img, last_updated

        edited_img, last_updated = await to_process_with_timeout(_make)

        embed = embeds.embed(
            title=f"{song.title} Progress", color=discord.Color.dark_gold()
        )
        embed.set_footer(
            text=" + ".join([r.upper() for r in data.keys()])
            + " · Last Updated: "
            + " || ".join(last_updated)
        )
        file = discord.File(edited_img, "image.png")
        embed.set_image(url="attachment://image.png")
        await interaction.followup.send(embed=embed, file=file)

    @song.command(
        auto_locale_strings=False, name="constant", description="View song constant."
    )
    @app_commands.autocomplete(
        song=autocompletes.autocompletes.pjsk_song,
        difficulty=autocompletes.autocompletes.custom_values(
            {"Expert": "expert", "Master": "master", "Append": "append"}
        ),
    )
    @app_commands.describe(
        song=locale_str("general.song_name"),
        difficulty=locale_str("general.difficulty_default_master"),
    )
    async def song_constant(
        self, interaction: discord.Interaction, song: str, difficulty: str = "master"
    ):
        await interaction.response.defer(ephemeral=False, thinking=True)
        osong = song
        song: Song = converters.SongFromPJSK(self.bot.pjsk, song)
        if song is None:
            embed = embeds.error_embed(
                await interaction.translate(
                    locale_str("errors.unknown_song", replacements={"{song}": osong})
                ),
            )
            await interaction.followup.send(embed=embed)
            return
        odiff = difficulty
        difficulty = converters.DiffFromPJSK(difficulty)
        if difficulty not in ["expert", "master", "append"]:
            embed = embeds.error_embed(
                f"Unsupported difficulty: `{odiff}`\n-# Only Expert, Master, and Append charts have constants.",
            )
            await interaction.followup.send(embed=embed)
            return
        leak = methods.Tools.isleak(song.id)
        if leak:
            embed = embeds.leak_embed()
            await interaction.followup.send(embed=embed)
            return
        if difficulty == "append":
            region = methods.Tools.get_music_append_regions(song.id)
        else:
            region = [methods.Tools.get_music_region(song.id)]
        embed = embeds.embed(title=song.title)
        try:
            the_constant, source = await self.bot.get_constant(
                song.id, difficulty, True, error_on_not_found=True, include_source=True
            )
            region = region[0]
            embed.set_thumbnail(url="attachment://jacket.png")
            file = discord.File(methods.Tools.get_music_jacket(song.id), "jacket.png")
            constant = f"{math.ceil(the_constant * 10) / 10:.1f}"
            actual = f"{int(math.ceil(methods.Tools.get_music_diff(song.id, difficulty) * 10) / 10)}"
            embed.description = f"**Difficulty:** {emojis.difficulty_colors[difficulty]} {difficulty.title()}\n\n**Level:** `{actual}`\n**Constant:** `{constant}`\n**Source:** `{source}`\n\n-# Constants are opinionated. Do not take seriously. Constants WILL be different for different people, they are community rated with a 'general' agreement."
            await interaction.followup.send(embed=embed, file=file)
        except IndexError:
            embed.description = f"Difficulty **{emojis.difficulty_colors[difficulty]} {difficulty.title()}** does not exist, or does not have a community-rated constant."
            embed.color = discord.Color.red()
            await interaction.followup.send(embed=embed)

    @song.command(
        auto_locale_strings=False, name="chart", description="View song chart."
    )
    @app_commands.autocomplete(
        song=autocompletes.autocompletes.pjsk_song,
        difficulty=autocompletes.autocompletes.pjsk_difficulties,
    )
    @app_commands.describe(
        song=locale_str("general.song_name"),
        difficulty=locale_str("general.difficulty_default_master"),
        mirror="Whether to show a mirrored PJSK chart (False, or the value you set in settings).",
    )
    async def song_chart(
        self,
        interaction: discord.Interaction,
        song: str,
        difficulty: str = "master",
        mirror: bool = False,
    ):
        await interaction.response.defer(ephemeral=False, thinking=True)
        osong = song
        song: Song = converters.SongFromPJSK(self.bot.pjsk, song)
        if song is None:
            embed = embeds.error_embed(
                await interaction.translate(
                    locale_str("errors.unknown_song", replacements={"{song}": osong})
                ),
            )
            await interaction.followup.send(embed=embed)
            return
        odiff = difficulty
        difficulty = converters.DiffFromPJSK(difficulty)
        if not difficulty:
            embed = embeds.error_embed(
                await interaction.translate(
                    locale_str(
                        "errors.unsupported_difficulty",
                        replacements={"{difficulty}": odiff},
                    )
                ),
            )
            await interaction.followup.send(embed=embed)
            return
        leak = methods.Tools.isleak(song.id)
        if leak:
            embed = embeds.leak_embed()
            await interaction.followup.send(embed=embed)
            return
        if difficulty == "append":
            region = methods.Tools.get_music_append_regions(song.id)
        else:
            region = [methods.Tools.get_music_region(song.id)]
        embed = embeds.embed(title=song.title)
        try:
            region = region[0]
            chart = await methods.Tools.get_chart(difficulty, song.id, region)
            if mirror:
                chart = await to_process_with_timeout(pjsk_chart.mirror, chart)
            file = discord.File(chart, "image.png")
            embed.set_image(url="attachment://image.png")
            embed.description = f"**Difficulty:** {emojis.difficulty_colors[difficulty]} {difficulty.title()}"
            if mirror:
                embed.description += f"\n\n**MIRRORED CHART**"
            view = views.ReportBrokenChartButton(region, song.id, difficulty)
            view2 = views.SbotgaView(timeout=None)
            view2.add_item(
                discord.ui.Button(
                    label="File",
                    style=discord.ButtonStyle.url,
                    url=f"https://sbotga.sbuga.com/cdn/charts/?id={song.id}&difficulty={difficulty}&mirror={int(mirror)}",
                )
            )
            view = views.merge_views(view, view2)
            await interaction.followup.send(embed=embed, file=file, view=view)
            view.message = await interaction.original_response()
        except IndexError as e:
            embed.description = f"Difficulty **{emojis.difficulty_colors[difficulty]} {difficulty.title()}** does not exist for this song."
            embed.color = discord.Color.red()
            await interaction.followup.send(embed=embed)

    @song.command(auto_locale_strings=False, name="info", description="View song data.")
    @app_commands.autocomplete(song=autocompletes.autocompletes.pjsk_song)
    @app_commands.describe(song=locale_str("general.song_name"))
    async def song_info(self, interaction: discord.Interaction, song: str):
        await interaction.response.defer(ephemeral=False, thinking=True)
        osong = song
        song: Song = converters.SongFromPJSK(self.bot.pjsk, song)
        if song is None:
            embed = embeds.error_embed(
                await interaction.translate(
                    locale_str("errors.unknown_song", replacements={"{song}": osong})
                ),
            )
            await interaction.followup.send(embed=embed)
            return
        leak = methods.Tools.isleak(song.id)
        if leak:
            embed = embeds.leak_embed()
            await interaction.followup.send(embed=embed)
            return
        embed = embeds.embed(title=song.title)
        data = song.data
        difficulties = song.difficulties
        original = methods.Tools.get_original(song.id)
        if difficulties.get("append"):
            apd_avail = f"\n**Append Server Availability:** `{', '.join([r.upper() for r in methods.Tools.get_music_append_regions(song.id)] or ['None'])}`"
        else:
            apd_avail = ""
        published, added, reg = methods.Tools.get_music_time_added(song.id)
        _, bpm_events, _, duration = methods.Tools.parse_bpm(song.id)
        text = ""
        for bpms in bpm_events:
            text = text + " - " + str(bpms["bpm"]).replace(".0", "")
        text = text[3:]
        try:
            dur_bpm = (
                f"**Duration:** {int(duration // 60)}m {int(duration % 60)}s\n"
                + f"**BPM:**\n```\n{text}\n```\n\n"
            )
        except TypeError:
            dur_bpm = ""
        ts = (
            "On Game Release"
            if datetime.datetime.fromtimestamp(added / 1000, datetime.timezone.utc).year
            <= 2019
            else f"<t:{int(added / 1000)}:R> (<t:{int(added / 1000)}:D>)"
        )
        embed.description = (
            f"{', '.join(data.get('section', []))}\n\n**Server Availability:** `{', '.join([r.upper() for r in methods.Tools.get_music_regions(song.id)[1]] or ['None'])}`{apd_avail}\n\n**ID:** `{song.id}`\n"
            + f"**By:** {' and '.join(', '.join(sorted(set(name.strip() for name in [data.get('composer', ''), data.get('arranger', ''), data.get('lyricist', '')] if name != '-'))).rsplit(', ', 1))}\n"
            + f"**Added to PJSK ({reg.upper()}):** {ts}\n\n"
            + f"**Original Song:** {'<' + original + '>' if original else 'No Link Found'}\n"
            + f"**Original Song Published:** <t:{int(published/1000)}:R> (<t:{int(published/1000)}:D>)\n\n"
            + f"{dur_bpm}"
            + f"**{emojis.difficulty_colors['easy']} Easy:** Lvl {difficulties.get('easy', {}).get('playLevel') if not isinstance(difficulties.get('easy', {}).get('playLevel'), list) else str(difficulties.get('easy', {}).get('playLevel', [])[0]) + ' (JP RERATED ' + str(difficulties.get('easy', {}).get('playLevel', [])[1]) + ')'} `({difficulties.get('easy', {}).get('totalNoteCount', 0)} notes)`\n"
            + f"**{emojis.difficulty_colors['normal']} Normal:** Lvl {difficulties.get('normal', {}).get('playLevel') if not isinstance(difficulties.get('normal', {}).get('playLevel'), list) else str(difficulties.get('normal', {}).get('playLevel', [])[0]) + ' (JP RERATED ' + str(difficulties.get('normal', {}).get('playLevel', [])[1]) + ')'} `({difficulties.get('normal', {}).get('totalNoteCount', 0)} notes)`\n"
            + f"**{emojis.difficulty_colors['hard']} Hard:** Lvl {difficulties.get('hard', {}).get('playLevel') if not isinstance(difficulties.get('hard', {}).get('playLevel'), list) else str(difficulties.get('hard', {}).get('playLevel', [])[0]) + ' (JP RERATED ' + str(difficulties.get('hard', {}).get('playLevel', [])[1]) + ')'} `({difficulties.get('hard', {}).get('totalNoteCount', 0)} notes)`\n"
            + f"**{emojis.difficulty_colors['expert']} Expert:** Lvl {difficulties.get('expert', {}).get('playLevel') if not isinstance(difficulties.get('expert', {}).get('playLevel'), list) else str(difficulties.get('expert', {}).get('playLevel', [])[0]) + ' (JP RERATED ' + str(difficulties.get('expert', {}).get('playLevel', [])[1]) + ')'} `({difficulties.get('expert', {}).get('totalNoteCount', 0)} notes)`\n"
            + f"**{emojis.difficulty_colors['master']} Master:** Lvl {difficulties.get('master', {}).get('playLevel') if not isinstance(difficulties.get('master', {}).get('playLevel'), list) else str(difficulties.get('master', {}).get('playLevel', [])[0]) + ' (JP RERATED ' + str(difficulties.get('master', {}).get('playLevel', [])[1]) + ')'} `({difficulties.get('master', {}).get('totalNoteCount', 0)} notes)`\n"
            + (
                f"**{emojis.difficulty_colors['append']} Append:** Lvl {difficulties.get('append', {}).get('playLevel') if not isinstance(difficulties.get('append', {}).get('playLevel'), list) else str(difficulties.get('append', {}).get('playLevel', [])[0]) + ' (JP RERATED ' + str(difficulties.get('append', {}).get('playLevel', [])[1]) + ')'} `({difficulties.get('append', {}).get('totalNoteCount', 0)} notes)`"
                if difficulties.get("append")
                else ""
            )
        )
        embed.set_thumbnail(url="attachment://jacket.png")
        file = discord.File(methods.Tools.get_music_jacket(song.id), "jacket.png")
        await interaction.followup.send(embed=embed, file=file)

    @song.command(
        auto_locale_strings=False,
        name="aliases",
        description="View defined song aliases.",
    )
    @app_commands.autocomplete(song=autocompletes.autocompletes.pjsk_song)
    @app_commands.describe(song=locale_str("general.song_name"))
    async def aliases(self, interaction: discord.Interaction, song: str):
        await interaction.response.defer(ephemeral=False, thinking=True)
        osong = song
        song: Song = converters.SongFromPJSK(self.bot.pjsk, song)
        if song is None:
            embed = embeds.error_embed(
                await interaction.translate(
                    locale_str("errors.unknown_song", replacements={"{song}": osong})
                ),
            )
            await interaction.followup.send(embed=embed)
            return
        leak = methods.Tools.isleak(song.id)
        if leak:
            embed = embeds.leak_embed()
            await interaction.followup.send(embed=embed)
            return
        embed = embeds.embed(
            title="Aliases",
            description=f"Aliases for song: `{song.title}` (ID `{song.id}`)\nAliases: `{', '.join(song.aliases) or 'None'}`",
        )
        await interaction.followup.send(embed=embed)

    @song.command(
        auto_locale_strings=False,
        name="difficulty",
        description="Find all songs of a level.",
    )
    @app_commands.describe(level="Level to search.")
    async def difficulty(self, interaction: discord.Interaction, level: int):
        await interaction.response.defer(ephemeral=False, thinking=True)
        if level <= 0 or level >= 40:
            embed = embeds.error_embed(
                f"Level must be between 0-40.",
            )
            await interaction.followup.send(embed=embed)
            return
        found = []
        for music_id, data in self.bot.pjsk.difficulties.items():
            if methods.Tools.isleak(music_id):
                continue
            for difficulty, diff_data in data.items():
                song = converters.SongFromPJSK(self.bot.pjsk, music_id)
                playlevel = song.difficulties.get(difficulty, {}).get("playLevel", -1)
                if type(playlevel) == list:
                    playlevel = playlevel[1]
                if playlevel == level:
                    found.append([song, difficulty])

        '[Song, "difficulty"]'
        difficulty_order = ["append", "master", "expert", "hard", "normal", "easy"]

        def sort_songs(song_list):
            return sorted(
                song_list,
                key=lambda x: (difficulty_order.index(x[1]), x[0].title.lower()),
            )

        found = sort_songs(found)

        def paginate_list(lst, page, per_page=25) -> list:
            start = (page - 1) * per_page
            end = start + per_page
            return lst[start:end]

        def create_diff_page(data: list, page: int, total: int) -> discord.Embed:
            embed = embeds.embed(
                title=f"Level {level} Songs", color=discord.Color.blue()
            )
            desc = []
            for d in data:
                song: Song = d[0]
                diff = d[1]
                desc.append(
                    f"**{diff.capitalize()} {emojis.difficulty_colors[diff]}** - {song.title}"
                )

            embed.description = "\n".join(desc) + f"\n\n-# Page {page}/{total}"

            return embed

        class PaginatedView(views.SbotgaView):
            def __init__(self, current_page: int, total_pages: int, found_data: list):
                super().__init__()
                self.current_page = current_page
                self.total_pages = total_pages
                self.found_data = found_data
                self.update_buttons()

            def update_buttons(self):
                self.previous_page.disabled = self.current_page == 1
                self.next_page.disabled = self.current_page == self.total_pages

            async def update_message(self, interaction: discord.Interaction):
                embed = create_diff_page(
                    paginate_list(self.found_data, self.current_page),
                    self.current_page,
                    self.total_pages,
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
                if (
                    interaction.user.id
                    != interaction.message.interaction_metadata.user.id
                ):
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
                if (
                    interaction.user.id
                    != interaction.message.interaction_metadata.user.id
                ):
                    embed = embeds.error_embed(
                        await interaction.translate("errors.cannot_click")
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                await interaction.response.defer()
                if self.current_page < self.total_pages:
                    self.current_page += 1
                    await self.update_message(interaction)

        embed = create_diff_page(paginate_list(found, 1), 1, math.ceil(len(found) / 25))
        view = PaginatedView(1, math.ceil(len(found) / 25), found)
        await interaction.followup.send(embed=embed, view=view)

    @song.command(
        auto_locale_strings=False,
        name="strategy",
        description="View song play strategy, usable for FC/AP.",
    )
    @app_commands.autocomplete(
        song=autocompletes.autocompletes.pjsk_song,
        difficulty=autocompletes.autocompletes.pjsk_difficulties,
    )
    @app_commands.describe(
        song=locale_str("general.song_name"),
        difficulty=locale_str("general.difficulty_default_master"),
    )
    async def song_strat(
        self, interaction: discord.Interaction, song: str, difficulty: str = "master"
    ):
        await interaction.response.defer(ephemeral=False, thinking=True)
        osong = song
        song: Song = converters.SongFromPJSK(self.bot.pjsk, song)
        if song is None:
            embed = embeds.error_embed(
                await interaction.translate(
                    locale_str("errors.unknown_song", replacements={"{song}": osong})
                ),
            )
            await interaction.followup.send(embed=embed)
            return
        odiff = difficulty
        difficulty = converters.DiffFromPJSK(difficulty)
        if not difficulty:
            embed = embeds.error_embed(
                await interaction.translate(
                    locale_str(
                        "errors.unsupported_difficulty",
                        replacements={"{difficulty}": odiff},
                    )
                ),
            )
            await interaction.followup.send(embed=embed)
            return
        leak = methods.Tools.isleak(song.id)
        if leak:
            embed = embeds.leak_embed()
            await interaction.followup.send(embed=embed)
            return

        def from_path(root: str, song_id: int, path: str):
            return f"{root}{song_id}/{path}"

        meta_file = "https://raw.githubusercontent.com/Sbotga/strategies/refs/heads/main/meta.json"
        async with aiohttp.ClientSession() as cs:
            async with cs.get(meta_file) as resp:
                meta_data = await resp.json(content_type=None)
            if song.id in meta_data["exists"]:
                async with cs.get(
                    from_path(meta_data["root"], song.id, "meta.json")
                ) as resp:
                    song_meta_data = await resp.json(content_type=None)
                if difficulty in song_meta_data:
                    strats_meta_data = song_meta_data[difficulty]
                else:
                    strats_meta_data = None
            else:
                strats_meta_data = None
        embed = embeds.embed(title=song.title)
        if strats_meta_data:
            jacket = methods.Tools.get_music_jacket(song.id)

            async def generate_strat_embed(strat_index: int):
                strat_meta_data = strats_meta_data["strats"][strat_index]
                strat_url = from_path(
                    meta_data["root"], song.id, strat_meta_data["path"]
                )
                async with aiohttp.ClientSession() as cs:
                    async with cs.get(strat_url) as resp:
                        img = BytesIO(await resp.read())
                embed.set_image(url="attachment://strat.png")
                embed.set_thumbnail(url="attachment://image.png")
                files = [
                    discord.File(jacket, "image.png"),
                    discord.File(img, "strat.png"),
                ]
                embed.description = (
                    f"-# Red for right hand, blue for left hand. TIMRP/12345 for fingers if labeled (1/thumb, 2/index, 3/middle, 4/ring, 5/pinky).\n\n**Difficulty:** {emojis.difficulty_colors[difficulty]} {difficulty.title()}\n**Fingers Required:** `{strat_meta_data['fingers']}`\n"
                    + (
                        f"\n**{strat_meta_data['title']}**"
                        if strat_meta_data["title"]
                        else ""
                    )
                    + (
                        f"\n{strat_meta_data['description']}"
                        if strat_meta_data["description"]
                        else ""
                    )
                ).strip()
                embed.set_author(name=f"Strategy made by {strat_meta_data['author']}")
                return embed, files

            async def generate_strat_section_embed(section_key: str, strat_index: int):
                section_meta_data = strats_meta_data["sections"][section_key]
                strat_meta_data = section_meta_data["strategies"][strat_index]
                section_url = from_path(
                    meta_data["root"], song.id, strat_meta_data["path"]
                )
                async with aiohttp.ClientSession() as cs:
                    async with cs.get(section_url) as resp:
                        img = BytesIO(await resp.read())
                embed.set_image(url="attachment://strat.png")
                embed.set_thumbnail(url="attachment://image.png")
                files = [
                    discord.File(jacket, "image.png"),
                    discord.File(img, "strat.png"),
                ]
                if type(section_meta_data["start_combo"]) == int:
                    combo = f"{section_meta_data['start_combo']} - {section_meta_data['end_combo']}"
                else:
                    combos = []
                    for index in range(len(section_meta_data["start_combo"])):
                        combo = f"{section_meta_data['start_combo'][index]} - {section_meta_data['end_combo'][index]}"
                        combos.append(combo)
                    combo = ", ".join(combos)
                embed.description = (
                    f"**Section of chart! Located at {combo} combo{'s' if type(section_meta_data['start_combo']) == list else ''}.**\n-# Red for right hand, blue for left hand. TIMRP/12345 for fingers if labeled (1/thumb, 2/index, 3/middle, 4/ring, 5/pinky).\n\n**Difficulty:** {emojis.difficulty_colors[difficulty]} {difficulty.title()}\n**Fingers Required:** `{strat_meta_data['fingers']}`\n"
                    + (
                        f"\n**{strat_meta_data['title']}**"
                        if strat_meta_data["title"]
                        else ""
                    )
                    + (
                        f"\n{strat_meta_data['description']}"
                        if strat_meta_data["description"]
                        else ""
                    )
                ).strip()
                embed.set_author(name=f"Strategy made by {strat_meta_data['author']}")
                return embed, files

            all_views = []

            def gen_select_optional_title(data: dict) -> str:
                if data["title"]:
                    fingers = f" ({data['fingers']}k)"
                else:
                    fingers = f"{data['fingers']}k"
                return (data["title"] or "") + fingers

            alt_strat = False
            section_strat = False

            if len(strats_meta_data["strats"]) > 1:
                selections = [
                    (gen_select_optional_title(data), index)
                    for index, data in enumerate(strats_meta_data["strats"])
                ]

                alt_strat = True

                class StrategySelect(discord.ui.Select):
                    def __init__(self, selections):
                        options = [
                            discord.SelectOption(label=title, value=str(index))
                            for title, index in selections
                        ]
                        super().__init__(placeholder=options[0].label, options=options)

                    async def callback(self, interaction: discord.Interaction):
                        if (
                            interaction.user.id
                            != interaction.message.interaction_metadata.user.id
                        ):
                            embed = embeds.error_embed(
                                await interaction.translate("errors.cannot_select")
                            )
                            await interaction.response.send_message(
                                embed=embed, ephemeral=True
                            )
                            return
                        await interaction.response.defer()
                        selected_index = int(self.values[0])

                        self.placeholder = self.options[selected_index].label

                        embed, files = await generate_strat_embed(selected_index)
                        if alt_strat and section_strat:
                            embed.description += f"\n\n**Alternate full-chart strategies available.**\n**Section-specific strategies available.**"
                        elif alt_strat:
                            embed.description += (
                                f"\n\n**Alternate full-chart strategies available.**"
                            )
                        elif section_strat:
                            embed.description += (
                                f"\n\n**Section-specific strategies available.**"
                            )
                        await interaction.followup.edit_message(
                            interaction.message.id,
                            embed=embed,
                            attachments=files,
                            view=self._view,
                        )

                view = views.SbotgaView()
                view.add_item(StrategySelect(selections))

                all_views.append(view)
            if len(strats_meta_data["sections"]) > 0:

                section_strat = True

                def gen_section_title(key: str, data: dict):
                    if type(data["start_measure"]) == list:
                        measures = []
                        combos = []
                        for index in range(len(data["start_measure"])):
                            # if (
                            #     data["start_measure"][index]
                            #     == data["end_measure"][index]
                            # ):
                            #     measure = f"#{data['start_measure'][index]}"
                            # else:
                            measure = f"#{data['start_measure'][index]} - #{data['end_measure'][index]}"
                            combo = f"{data['start_combo'][index]} - {data['end_combo'][index]}"
                            measures.append(measure)
                            combos.append(combo)
                        return f"{key} ({', '.join(combos)}) [{', '.join(measures)}]"
                    else:
                        # if data["start_measure"] == data["end_measure"]:
                        measure = f"#{data['start_measure']}"
                        # else:
                        #     measure = (
                        #         f"#{data['start_measure']} - #{data['end_measure']}"
                        #     )
                        return f"{key} ({data['start_combo']} - {data['end_combo']}) [{measure}]"

                class SectionSelection(views.SbotgaView):
                    def __init__(self, section_data: dict):
                        super().__init__()
                        self.section_data = section_data
                        self.selected_section = None

                        self.unmodified_button = None

                        self.section_select = discord.ui.Select(
                            placeholder="Choose a section.",
                            options=[
                                discord.SelectOption(
                                    label=gen_section_title(key, data), value=key
                                )
                                for key, data in section_data.items()
                            ],
                        )
                        self.strategy_select = discord.ui.Select(
                            placeholder="Choose a strategy.",
                            options=[discord.SelectOption(label="none")],
                            disabled=True,
                        )

                        self.section_select.callback = self.section_callback
                        self.strategy_select.callback = self.strategy_callback

                        self.add_item(self.section_select)
                        self.add_item(self.strategy_select)

                    async def section_callback(self, interaction: discord.Interaction):
                        if (
                            interaction.user.id
                            != interaction.message.interaction_metadata.user.id
                        ):
                            embed = embeds.error_embed(
                                await interaction.translate("errors.cannot_select")
                            )
                            await interaction.response.send_message(
                                embed=embed, ephemeral=True
                            )
                            return
                        self.selected_section = self.section_select.values[0]
                        section = self.section_data[self.selected_section]

                        self.strategy_select.options = [
                            discord.SelectOption(
                                label=gen_select_optional_title(data), value=index
                            )
                            for index, data in enumerate(section["strategies"])
                        ]
                        self.strategy_select.placeholder = "Select a strategy."
                        self.strategy_select.disabled = False

                        self.section_select.placeholder = gen_section_title(
                            self.selected_section,
                            self.section_data[self.selected_section],
                        )

                        embed = embeds.embed(
                            title="Select a strategy to view.",
                            description='These are multiple strategies you can choose from for this section.\n\n-# "k" stands for "key", and it means how many fingers. For example, 3k means 3 fingers, 4k means 4 fingers.',
                            color=discord.Colour.blue(),
                        )
                        embed.set_thumbnail(url="attachment://image.png")
                        file = discord.File(jacket, "image.png")

                        if self.unmodified_button:
                            self.remove_item(self.unmodified_button)
                        self.unmodified_button = discord.ui.Button(
                            label="Unmodified Section",
                            style=discord.ButtonStyle.link,
                            url=from_path(
                                meta_data["root"],
                                song.id,
                                self.section_data[self.selected_section]["raw"],
                            ),
                        )
                        self.add_item(self.unmodified_button)

                        await interaction.response.edit_message(
                            embed=embed, attachments=[file], view=self
                        )

                    async def strategy_callback(self, interaction: discord.Interaction):
                        if (
                            interaction.user.id
                            != interaction.message.interaction_metadata.user.id
                        ):
                            embed = embeds.error_embed(
                                await interaction.translate("errors.cannot_select")
                            )
                            await interaction.response.send_message(
                                embed=embed, ephemeral=True
                            )
                            return
                        selected_strategy = int(self.strategy_select.values[0])

                        embed, files = await generate_strat_section_embed(
                            self.selected_section, selected_strategy
                        )

                        self.strategy_select.placeholder = gen_select_optional_title(
                            self.section_data[self.selected_section]["strategies"][
                                selected_strategy
                            ]
                        )

                        await interaction.response.edit_message(
                            embed=embed, attachments=files, view=self
                        )

                view = views.SbotgaView()
                button = discord.ui.Button(label="View Section Strategies")

                async def callback(interaction: discord.Interaction):
                    if (
                        interaction.user.id
                        != interaction.message.interaction_metadata.user.id
                    ):
                        embed = embeds.error_embed(
                            await interaction.translate("errors.cannot_click")
                        )
                        await interaction.response.send_message(
                            embed=embed, ephemeral=True
                        )
                        return
                    view = SectionSelection(strats_meta_data["sections"])

                    embed = embeds.embed(
                        title="Select a section to view.",
                        description='These are sections of the chart with multiple strategies you can choose from.\n\n-# The selections are formatted in `Section Name (Start Combos - End Combos) [Start Measures]`. For example, the section called "The Wall" starting on measure 45 and ending on measure 47, at 663-691 combo, will be called "The Wall (663 - 691) [#45]".',
                        color=discord.Colour.blue(),
                    )
                    embed.set_thumbnail(url="attachment://image.png")
                    file = discord.File(jacket, "image.png")

                    await interaction.response.edit_message(
                        embed=embed, attachments=[file], view=view
                    )
                    view.message = await interaction.original_response()

                button.callback = callback
                view.add_item(button)
                all_views.append(view)

            embed, files = await generate_strat_embed(strat_index=0)
            final_view = (
                views.merge_views(*tuple(all_views))
                if len(all_views) > 0
                else discord.utils.MISSING
            )
            if alt_strat and section_strat:
                embed.description += f"\n\n**Alternate full-chart strategies available.**\n**Section-specific strategies available.**"
            elif alt_strat:
                embed.description += (
                    f"\n\n**Alternate full-chart strategies available.**"
                )
            elif section_strat:
                embed.description += f"\n\n**Section-specific strategies available.**"
            await interaction.followup.send(embed=embed, files=files, view=final_view)
            if not isinstance(final_view, discord.utils._MissingSentinel):
                final_view.message = await interaction.original_response()
        else:
            embed.description = f"We do not have a strategy for **{emojis.difficulty_colors[difficulty]} {difficulty.title()}** on this song.\n\n-# Contribute? Join our support server using </help:1326325488939040808>. Must be usable for AP, and neat."
            embed.color = discord.Color.red()
            await interaction.followup.send(embed=embed)


async def setup(bot: DiscordBot):
    await bot.add_cog(SongInfo(bot))
