import discord
from discord.ext import commands
from discord import app_commands

from discord.app_commands import locale_str
from COGS.discord_translations import translations

from main import DiscordBot

import os

from DATA.game_api import methods

from DATA.helpers import views
from DATA.helpers import discord_autocompletes as autocompletes
from DATA.helpers import converters
from DATA.helpers import embeds


class CharactersCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    char = app_commands.Group(
        name=locale_str("char", key="char.cmds.info.name", file="commands"),
        description=locale_str("char.cmds.info.desc", file="commands"),
    )

    @char.command(
        auto_locale_strings=False,
        name=locale_str("info", key="char.cmds.info.name", file="commands"),
        description=locale_str("char.cmds.info.desc", file="commands"),
    )
    @app_commands.autocomplete(character=autocompletes.autocompletes.pjsk_char)
    @app_commands.describe(
        character=locale_str("char.cmds.info.describes.character", file="commands")
    )
    async def char_info(self, interaction: discord.Interaction, character: str):
        await interaction.response.defer(thinking=True)
        ochar = character
        character: dict = converters.CharFromPJSK(self.bot.pjsk, character)
        if character is None:
            embed = embeds.error_embed(
                await interaction.translate(
                    locale_str(
                        "errors.unknown_character", replacements={"{character}": ochar}
                    )
                )
            )
            await interaction.followup.send(embed=embed)
            return

        embed, file = views.CharacterInfo.generate_character_embed(character)
        file_data = file.fp.read()
        file.fp.seek(0)
        view = views.CharacterInfo(
            character["id"],
            file=file,
            file_data=file_data,
            footer=embed.footer.text,
            restricted_user_id=interaction.user.id,
        )
        await interaction.followup.send(
            embed=embed,
            file=file,
            view=view,
        )
        view.message = await interaction.original_response()

    @char.command(
        auto_locale_strings=False,
        name=locale_str("card", key="char.cmds.card.name", file="commands"),
        description=locale_str("char.cmds.card.desc", file="commands"),
    )
    @app_commands.autocomplete(card=autocompletes.autocompletes.pjsk_card)
    @app_commands.describe(
        card=locale_str(
            "char.cmds.card.describes.card",
            file="commands",
        )
    )
    async def card(self, interaction: discord.Interaction, card: str):
        await interaction.response.defer(thinking=True)
        api = methods.pjsk_game_api_jp
        ocard = card
        try:
            card: dict = api.get_card(int(card))
        except:
            card = None
        if card is None:
            embed = embeds.error_embed(
                await interaction.translate(
                    locale_str("errors.unknown_card", replacements={"{card}": ocard})
                )
            )
            await interaction.followup.send(embed=embed)
            return

        trained = False

        card_image_path = os.path.join(
            api.game_files_path,
            api.app_region,
            "character",
            "member",
            f"{card['assetbundleName']}_ex",
        )

        name = (
            "("
            + str(card["id"])
            + ") "
            + methods.Tools.get_card_name(
                card["id"],
                trained,
                include_character=True,
                include_attribute=True,
                include_rarity=True,
                use_emojis=True,
            )
        )
        embed = embeds.embed(color=discord.Color.blurple(), description=f"### {name}")
        embed.set_image(url=f"attachment://card.png")
        embed.set_footer(text=f"Character Cards")

        toggleable = discord.utils.MISSING
        if card["cardRarityType"] in ["rarity_3", "rarity_4"]:
            toggleable = views.ToggleCardTrained(
                card["id"], card_image_path, trained, interaction.user.id
            )

        file = discord.File(
            os.path.join(
                card_image_path,
                "card_after_training.png" if trained else "card_normal.png",
            ),
            filename="card.png",
        )
        await interaction.followup.send(embed=embed, files=[file], view=toggleable)
        if toggleable:
            toggleable.message = await interaction.original_response()


async def setup(bot: DiscordBot):
    await bot.add_cog(CharactersCog(bot))
