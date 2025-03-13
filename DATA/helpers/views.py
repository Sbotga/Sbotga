import discord
from discord import app_commands
from discord.ext import commands

import time, os, datetime
from io import BytesIO

from DATA.game_api import methods
from DATA.helpers.discord_emojis import emojis
from DATA.helpers import embeds

from DATA.data.pjsk import Song, pjsk


class SbotgaView(discord.ui.View):
    def __init__(self, *, timeout=180):
        super().__init__(timeout=timeout)

        self.message: discord.Message = None

    async def on_timeout(self):
        if not self.message:
            return
        for child in self.children:
            if isinstance(child, discord.ui.Button) or isinstance(
                child, discord.ui.Select
            ):
                child.disabled = True
        try:
            await self.message.edit(view=self)
        except discord.NotFound:
            pass

    async def interaction_check(self, interaction: discord.Interaction):
        return await interaction.client.tree.interaction_check(interaction)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        await interaction.client.tree.on_error(interaction, error, item)


def merge_views(*args, timeout: int = 180):
    new = SbotgaView(timeout=timeout)
    for view in args:
        view: SbotgaView | discord.ui.View
        for children in view.children:
            new.add_item(children)
        if hasattr(view, "message") and view.message:
            new.message = view.message
    return new


class ReportBrokenChartButton(SbotgaView):
    def __init__(self, region: str, music_id: int, diff: str):
        super().__init__()

        self.region = region
        self.music_id = music_id
        self.diff = diff

        self.allowed = [1131568595369996379]

    @discord.ui.button(label="Report Broken Chart", style=discord.ButtonStyle.danger)
    async def _ReportBrokenChartButtonCallback(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        button.disabled = True
        await interaction.response.edit_message(view=button._view)
        channel = interaction.client.get_channel(1332839802323603477)
        if not channel:
            channel = interaction.client.fetch_channel(1332839802323603477)
        embed = embeds.warn_embed(title="Broken Chart?", description="")
        chart = await methods.Tools.get_chart(self.diff, self.music_id, self.region)
        file = discord.File(chart, "image.png")
        embed.set_image(url="attachment://image.png")
        embed.description = f"**Difficulty:** {emojis.difficulty_colors[self.diff]} {self.diff.title()}\n**Region:** `{self.region.upper()}`"

        class FixView(SbotgaView):
            def __init__(self, allowed: list, region: str, music_id: int, diff: str):
                super().__init__(timeout=None)

                self.region = region
                self.music_id = music_id
                self.diff = diff

                self.allowed = allowed

            @discord.ui.button(style=discord.ButtonStyle.green, label="Yes")
            async def yup(
                self, interaction: discord.Interaction, button: discord.Button
            ):
                if not (interaction.user.id in self.allowed):
                    return
                await self.message.delete()
                await methods.Tools.get_chart(
                    self.diff, self.music_id, self.region, fix=True
                )

            @discord.ui.button(style=discord.ButtonStyle.danger, label="No")
            async def nope(
                self, interaction: discord.Interaction, button: discord.Button
            ):
                if not (interaction.user.id in self.allowed):
                    return
                await self.message.delete()

        view = FixView(self.allowed, self.region, self.music_id, self.diff)
        msg = await channel.send(embed=embed, view=view, file=file)
        view.message = msg


class ToggleCardTrained(SbotgaView):
    def __init__(
        self,
        card_id: int,
        card_image_path: str,
        trained: bool,
        restricted_user_id: int = None,
    ):
        super().__init__()

        self.card_id = card_id

        self.path = card_image_path
        self.trained = trained

        self.restricted = restricted_user_id

        if self.trained:
            self.toggle_trained.label = "View Untrained"
        else:
            self.toggle_trained.label = "View Trained"

    @discord.ui.button(label="...", style=discord.ButtonStyle.primary, emoji="🔃")
    async def toggle_trained(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        if self.restricted:
            if interaction.user.id != self.restricted:
                embed = embeds.error_embed("You cannot click this button!")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        name = (
            "("
            + str(self.card_id)
            + ") "
            + methods.Tools.get_card_name(
                self.card_id,
                not self.trained,
                include_character=True,
                include_attribute=True,
                include_rarity=True,
                use_emojis=True,
            )
        )
        embed = embeds.embed(
            color=discord.Color.blurple(),
            description=(
                f"### {name}" + ("\n**Trained Version**" if not self.trained else "")
            ),
        )
        embed.set_image(url=f"attachment://card.png")
        embed.set_footer(text=f"Character Cards")

        file = discord.File(
            os.path.join(
                self.path,
                "card_after_training.png" if not self.trained else "card_normal.png",
            ),
            filename="card.png",
        )
        await interaction.followup.edit_message(
            (await interaction.original_response()).id,
            embed=embed,
            attachments=[file],
            view=ToggleCardTrained(self.card_id, self.path, not self.trained),
        )


class ViewCardButton(SbotgaView):
    def __init__(self, card_id: int, trained: bool = False):
        super().__init__()
        self.card_id = card_id
        self.trained = trained

    @discord.ui.button(
        label="Card Info",
        style=discord.ButtonStyle.gray,
    )
    async def card_info(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer(thinking=True)
        if interaction.message:
            button.disabled = True
            await interaction.message.edit(view=button._view)
        api = methods.pjsk_game_api_jp
        card: dict = api.get_card(int(self.card_id))

        card_image_path = os.path.join(
            api.game_files_path,
            api.app_region,
            "character",
            "member",
            f"{card['assetbundleName']}_ex",
        )

        name = (
            "("
            + str(self.card_id)
            + ") "
            + methods.Tools.get_card_name(
                self.card_id,
                self.trained,
                include_character=True,
                include_attribute=True,
                include_rarity=True,
                use_emojis=True,
            )
        )
        embed = embeds.embed(
            color=discord.Color.blurple(),
            description=(
                f"### {name}" + ("\n**Trained Version**" if self.trained else "")
            ),
        )
        embed.set_image(url=f"attachment://card.png")
        embed.set_footer(text=f"Character Cards")

        toggleable = None
        if card["cardRarityType"] in ["rarity_3", "rarity_4"]:
            toggleable = ToggleCardTrained(card["id"], card_image_path, self.trained)

        file = discord.File(
            os.path.join(
                card_image_path,
                "card_after_training.png" if self.trained else "card_normal.png",
            ),
            filename="card.png",
        )
        await interaction.followup.send(
            embed=embed, files=[file], view=toggleable or discord.utils.MISSING
        )
        if toggleable:
            toggleable.message = await interaction.original_response()


class CharacterInfoButton(SbotgaView):
    def __init__(self, character_id: int):
        super().__init__()
        self.character_id = character_id

    @discord.ui.button(
        label="Character Info",
        style=discord.ButtonStyle.gray,
    )
    async def character_info(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer(thinking=True)

        if interaction.message:
            button.disabled = True
            await interaction.message.edit(view=button._view)

        character: dict = pjsk.characters_game[self.character_id - 1]

        embed, file = CharacterInfo.generate_character_embed(character)
        file_data = file.fp.read()
        file.fp.seek(0)
        view = CharacterInfo(
            character["id"],
            file=file,
            file_data=file_data,
            footer=embed.footer.text,
        )
        await interaction.followup.send(
            embed=embed,
            file=file,
            view=view,
        )
        view.message = await interaction.original_response()


class CharacterInfo(SbotgaView):
    def __init__(
        self,
        character: int,
        file: discord.File = None,
        file_data: bytes = None,
        footer: str = None,
        profile: bool = False,
        restricted_user_id: int = None,
        _message: discord.Message = None,
    ):
        super().__init__()
        self.char_id = character

        self.restricted = restricted_user_id

        self.profile = profile
        self.file = file
        self.file_data = file_data
        self.footer = footer

        self.toggle_button.label = "View Profile" if not profile else "Back"

        self.message: discord.Message | None = _message

    @staticmethod
    def generate_character_embed(
        data: dict,
        file: discord.File = None,
        file_data: bytes = None,
        footer: str = None,
    ):
        data2 = pjsk.characters[data["id"] - 1]
        name = (
            str(data["givenName"]) + " " + str(data["firstName"])
            if data.get("firstName") and data.get("unit") != "piapro"
            else (
                str(data["firstName"]) + " " + str(data["givenName"])
                if data.get("firstName")
                else data["givenName"]
            )
        )
        embed = embeds.embed(title=name, color=discord.Color.teal())
        nl = "\n"
        embed.description = f"**{pjsk.unit_map[data['unit']]}**\n\n{'**Voice Actor:** ' + data2['characterVoice'] + nl if data2.get('characterVoice') else ''}**Birthday:** `{data2['birthday'].replace('.', ' ')}`\n\n**Gender:** {data['gender'].capitalize()}\n**Height:** {data2['height']}\n-# Height as of third anniversary."
        if data.get("school"):
            school = f"{data['school'].replace('HS', 'High School')} (Year {data['schoolYear'] if data['schoolYear'] != '-' else 'N/A'})"
        else:
            school = None
        if school:
            embed.description += f"\n\n**School:** {school}"
        if not file:
            card_path, card_id, trained = (
                methods.pjsk_game_api_jp.random_character_card(
                    data["id"], rarity=["rarity_3", "rarity_4", "rarity_birthday"]
                )
            )
            file = discord.File(card_path, "image.png")
            embed.set_footer(
                text=methods.Tools.get_card_name(
                    card_id, trained, include_character=True
                )
            )
        else:
            file = discord.File(BytesIO(file_data), file.filename)
            embed.set_footer(text=footer)
        embed.set_image(url="attachment://" + file.filename)
        return embed, file

    @staticmethod
    def generate_character_profile_embed(
        data: dict,
        file: discord.File = None,
        file_data: bytes = None,
        footer: str = None,
    ):
        data2 = pjsk.characters[data["id"] - 1]
        name = (
            str(data["givenName"]) + " " + str(data["firstName"])
            if data.get("firstName") and data.get("unit") != "piapro"
            else (
                str(data["firstName"]) + " " + str(data["givenName"])
                if data.get("firstName")
                else data["givenName"]
            )
        )
        embed = embeds.embed(title=name + " Profile", color=discord.Color.teal())
        embed.description = f"**{pjsk.unit_map[data['unit']]}**\n\n**Hobbies:** {data2.get('hobby')}\n**Special Skills:** {data2.get('specialSkill')}\n**Dislikes:** {data2.get('weak')}\n**Hated Food:** {data2.get('hatedFood')}\n**Favorite Food:** {data2.get('favoriteFood')}\n\n**Introduction**\n```\n{data2.get('introduction')}\n```"

        if not file:
            card_path, card_id, trained = (
                methods.pjsk_game_api_jp.random_character_card(
                    data["id"], rarity=["rarity_3", "rarity_4", "rarity_birthday"]
                )
            )
            file = discord.File(card_path, "image.png")
            embed.set_footer(
                text=methods.Tools.get_card_name(
                    card_id, trained, include_character=True
                )
            )
        else:
            file = discord.File(BytesIO(file_data), file.filename)
            embed.set_footer(text=footer)
        embed.set_image(url="attachment://" + file.filename)
        return embed, file

    @discord.ui.button(
        label="...",
        style=discord.ButtonStyle.primary,
    )
    async def toggle_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.restricted:
            if interaction.user.id != self.restricted:
                embed = embeds.error_embed("You cannot click this button!")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        data = pjsk.characters_game[self.char_id - 1]
        if self.profile:
            embed, file = self.generate_character_embed(
                data, self.file, self.file_data, self.footer
            )
        else:
            embed, file = self.generate_character_profile_embed(
                data, self.file, self.file_data, self.footer
            )
        self.footer = embed.footer.text
        await interaction.response.edit_message(
            embed=embed,
            attachments=[file],
            view=CharacterInfo(
                self.char_id,
                file,
                self.file_data,
                self.footer,
                not self.profile,
                _message=self.message,
            ),
        )

    @discord.ui.button(label="Change Card", style=discord.ButtonStyle.gray, emoji="🔃")
    async def change_card(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.restricted:
            if interaction.user.id != self.restricted:
                embed = embeds.error_embed("You cannot click this button!")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        data = pjsk.characters_game[self.char_id - 1]
        if self.profile:
            embed, file = self.generate_character_profile_embed(data, None, None, None)
        else:
            embed, file = self.generate_character_embed(data, None, None, None)
        self.file = file
        self.file_data = file.fp.read()
        file.fp.seek(0)
        self.footer = embed.footer.text
        await interaction.response.edit_message(
            embed=embed,
            attachments=[file],
            view=CharacterInfo(
                self.char_id,
                file,
                self.file_data,
                self.footer,
                self.profile,
                _message=self.message,
            ),
        )


class SongAliasesButton(SbotgaView):
    def __init__(self, music_id: int):
        super().__init__()
        self.music_id = music_id

    @discord.ui.button(
        label="Song Aliases",
        style=discord.ButtonStyle.gray,
    )
    async def song_info_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=False, thinking=True)

        if interaction.message:
            button.disabled = True
            await interaction.message.edit(view=button._view)

        song = pjsk.songs[self.music_id]
        difficulties = pjsk.difficulties[self.music_id]
        song = Song(song, difficulties)
        embed = embeds.embed(
            title="Aliases",
            description=f"Aliases for song: `{song.title}` (ID `{song.id}`)\nAliases: `{', '.join(song.aliases) or 'None'}`",
        )
        await interaction.followup.send(embed=embed)


class SongInfoButton(SbotgaView):
    def __init__(self, music_id: int):
        super().__init__()
        self.music_id = music_id

    @discord.ui.button(
        label="Song Info",
        style=discord.ButtonStyle.gray,
    )
    async def song_info_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer(thinking=True)

        if interaction.message:
            button.disabled = True
            await interaction.message.edit(view=button._view)

        song = pjsk.songs[self.music_id]
        difficulties = pjsk.difficulties[self.music_id]
        song = Song(song, difficulties)
        embed = embeds.embed(title=song.title)
        data = song.data
        difficulties = song.difficulties
        if difficulties.get("append"):
            apd_avail = f"\n**Append Server Availability:** `{', '.join([r.upper() for r in methods.Tools.get_music_append_regions(song.id)] or ['None'])}`"
        else:
            apd_avail = ""
        original = methods.Tools.get_original(song.id)
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


class ProfileButton(SbotgaView):
    def __init__(self, region: str, user_id: int):
        super().__init__()
        self.region = region
        self.user_id = user_id

    @discord.ui.button(
        label="Profile",
        style=discord.ButtonStyle.gray,
    )
    async def profile_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.message:
            button.disabled = True
            await interaction.message.edit(view=button._view)
        try:
            region = self.region
            user_id = self.user_id
            region = region.lower().strip()
            await interaction.response.defer(ephemeral=False, thinking=True)
            try:
                # min and max         10000000                    402827003243343876 is my id
                assert int(user_id) > 10000000 and int(user_id) < 10000000000000000000
                api = methods.Tools.get_api(region)
                data = api.get_profile(int(user_id))
                last_updated = api.profile_cache[int(user_id)]["last_updated"]
            except Exception as e:
                interaction.client.traceback(e)
                return await interaction.followup.send(
                    embed=embeds.error_embed(
                        f"Couldn't get this user's profile; are they in the {region.upper()} server? Is the user id valid?"
                    )
                )
            is_self = False
            pjsk_id = await interaction.client.user_data.discord.get_pjsk_id(
                interaction.user.id, region
            )
            if pjsk_id == user_id:
                is_self = True
            joined = (
                f"**Joined:** <t:{(int(format(data['user']['userId'], '064b')[:42], 2) + 1600218000000) // 1000}:R>\n"
                if region in ["en", "jp"]
                else ""
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
                text=f"Last Updated {round(time.time()-last_updated)}s ago"
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            raise e
