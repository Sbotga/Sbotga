import discord
from discord.ext import commands
from discord import app_commands

from discord.app_commands import locale_str
from COGS.discord_translations import translations

from main import DiscordBot

import os

from DATA.game_api import methods

from DATA.helpers import discord_autocompletes as autocompletes
from DATA.helpers import embeds

from DATA.helpers import views

from main import DiscordBot


class ComicsCog(commands.Cog):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    @app_commands.command(
        auto_locale_strings=False,
        name=locale_str("comics", key="comics.name", file="commands"),
        description=locale_str("comics.desc", file="commands"),
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.describe(region=locale_str("general.region"))
    @app_commands.autocomplete(
        region=autocompletes.autocompletes.pjsk_region(["en", "jp", "tw", "kr", "cn"])
    )
    async def comics(self, interaction: discord.Interaction, region: str = "default"):
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
        data = api.comics

        page_size = 23
        options = [
            discord.SelectOption(label=title, value=str(comic_id))
            for comic_id, (title, _) in data.items()
        ]
        pages = [options[i : i + page_size] for i in range(0, len(options), page_size)]

        view = ComicView(api, data, pages, interaction.user.id)
        embed = embeds.embed(
            title="Choose a Comic",
            description="Choose a comic to display!",
        )
        embed.set_footer(text=f"{region.upper()} Comics")
        await interaction.followup.send(embed=embed, view=view)
        view.message = await interaction.original_response()


class ComicView(views.SbotgaView):
    def __init__(
        self, api: methods.GAME_API, data: dict, pages: list, restriction_id: int
    ):
        super().__init__()
        self.data = data
        self.api = api
        self.pages = pages
        self.current_page = 0
        self.restrict = restriction_id

        self.update_menu()

    def update_menu(self):
        """Update the dropdown menu with the current page options."""
        options = self.pages[self.current_page]
        if self.current_page > 0:
            options.insert(
                0,
                discord.SelectOption(
                    label="⬅ Previous Selections Page", value="previous"
                ),
            )
        if self.current_page < len(self.pages) - 1:
            options.append(
                discord.SelectOption(label="➡ Next Selections Page", value="next")
            )

        self.clear_items()
        self.add_item(ComicSelect(self.api, self.data, options, self, self.restrict))

    async def update_view(self, interaction: discord.Interaction):
        """Update the view without changing the embed or content."""
        self.update_menu()
        await interaction.response.edit_message(view=self)


class ComicSelect(discord.ui.Select):
    def __init__(
        self,
        api: methods.GAME_API,
        data: dict,
        options: list,
        da_view: ComicView,
        restriction_id: int,
    ):
        super().__init__(placeholder="Select a comic.", options=options)
        self.data = data
        self.da_view = da_view
        self.api = api
        self.restriction = restriction_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.restriction:
            return await interaction.response.send_message(
                embed=embeds.error_embed(
                    await interaction.translate("errors.cannot_select")
                ),
                ephemeral=True,
            )
        if self.values[0] == "previous":
            self.da_view.current_page -= 1
            await self.da_view.update_view(interaction)
        elif self.values[0] == "next":
            self.da_view.current_page += 1
            await self.da_view.update_view(interaction)
        else:
            comic_id = int(self.values[0])
            comic_title, comic_image_path = self.data[comic_id]

            comic_image_path = os.path.join(
                self.api.game_files_path,
                self.api.app_region,
                "comic",
                "one_frame_ex",
                comic_image_path + ".png",
            )

            embed = embeds.embed(title=comic_title, color=discord.Color.blurple())
            embed.set_image(url=f"attachment://comic.png")
            embed.set_footer(text=f"{self.api.app_region.upper()} Comics")

            file = discord.File(comic_image_path, filename="comic.png")
            await interaction.response.edit_message(embed=embed, attachments=[file])


async def setup(bot: DiscordBot):
    await bot.add_cog(ComicsCog(bot))
