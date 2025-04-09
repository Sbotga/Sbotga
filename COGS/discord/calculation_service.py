import discord
from discord.ext import commands
from discord import app_commands
import discord
from discord.ext import commands
from discord import app_commands

from discord.app_commands import locale_str
from COGS.discord_translations import translations

from main import DiscordBot

import time, csv, math, asyncio, random
from datetime import datetime, timezone
from io import BytesIO, StringIO

import aiohttp

from DATA.helpers import discord_autocompletes as autocompletes
from DATA.helpers import converters
from DATA.data.pjsk import Song
from DATA.helpers import embeds

from DATA.game_api import methods


class CalculationService(commands.Cog):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    def calculate_score(self, constant: float, score: str, note_count: int):
        score_data = score.split("/")

        if len(score_data) > 5 or len(score_data) < 1:
            return None

        score_values = self.convert_to_score_values(score_data, note_count)
        if score_values is None:
            return None

        accuracy = self.calculate_accuracy(score_values)
        constant_modifier = self.get_modifier_from_accuracy(accuracy)
        if constant_modifier is None:
            return None

        result = constant + constant_modifier
        diff = f"{'+' if constant_modifier > 0 else ''}{constant_modifier:.2f}"

        return {
            "result": result,
            "diff": diff,
            "accuracy": accuracy,
            "score_values": score_values,
        }

    def convert_to_score_values(self, score: list[str], note_count: int):
        if len(score) == 5:
            return [int(s) for s in score]

        if len(score) > 0:
            arr = [int(s) for s in score]
            great = arr[0]
            good = arr[1] if len(arr) > 1 else 0
            bad = arr[2] if len(arr) > 2 else 0
            miss = arr[3] if len(arr) > 3 else 0

            return [note_count - great - good - bad - miss, great, good, bad, miss]

        return None

    def calculate_accuracy(self, score: list[int]):
        total_note_amount = sum(score)

        perf = score[0]
        great = score[1]
        good = score[2]
        bad = score[3]
        miss = score[4]

        negative = great + good * 2 + bad * 3 + miss * 3
        accuracy = (total_note_amount * 3 - negative) / (total_note_amount * 3)

        return accuracy

    def get_modifier_from_accuracy(self, accuracy: float):
        if accuracy > 1.00:
            return None

        if accuracy >= 0.99:
            diff = accuracy - 0.99
            return diff * 200 + 2
        elif 0.97 <= accuracy < 0.99:
            diff = accuracy - 0.97
            return diff * 100
        else:
            diff = accuracy - 0.97
            return diff * 200 / 3

    @app_commands.command(
        auto_locale_strings=False,
        name=locale_str("calculate", key="calculate.name", file="commands"),
        description=locale_str("calculate.desc", file="commands"),
    )
    @app_commands.describe(
        song=locale_str("general.song_name"),
        difficulty=locale_str("general.difficulty"),
        score=locale_str("calculate.describes.score", file="commands"),
    )
    @app_commands.autocomplete(
        song=autocompletes.autocompletes.pjsk_song,
        difficulty=autocompletes.autocompletes.pjsk_difficulties,
    )
    @app_commands.guilds(discord.Object(id=986099686005960796))
    async def calculate(
        self, interaction: discord.Interaction, song: str, difficulty: str, score: str
    ):
        """
        Calculate the score based on provided parameters.
        Usage: !calculate_score <constant> <score> <note_count>
        Example: !calculate_score 12.5 "300/50/20/10/5" 400
        """
        osong = song
        song: Song = converters.SongFromPJSK(self.bot.pjsk, song)
        if song is None:
            embed = embeds.error_embed(
                await interaction.translate(
                    locale_str("errors.unknown_song", replacements={"{song}": osong})
                )
            )
            await interaction.followup.send(embed=embed)
            return
        leak = methods.Tools.isleak(song.id)
        if leak:
            await interaction.followup.send(embed=embeds.leak_embed())
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
                )
            )
            await interaction.followup.send(embed=embed)
            return
        constant = await self.bot.get_constant(
            song.id, difficulty, ap=True, force_39s=True
        )
        result = self.calculate_score(
            constant,
            score,
            song.difficulties.get(difficulty, {}).get("totalNoteCount", 0),
        )

        if result is None:
            await interaction.response.send_message(
                embed=embeds.error_embed(
                    await interaction.translate(locale_str("errors.invalid_input"))
                )
            )
        else:
            """
            36.00~ - Space Gorilla
            34.00~35.99 - Gorilla
            32.00~33.99 - Diamond
            30.00~31.99 - Platinum
            26.00~29.99 - Gold
            21.00~25.99 - Silver
            17.50~20.99 - Bronze
            0.0~17.49 - Novice
            """
            diff = float(result["diff"])
            rank = (
                "Troll"
                if diff < -4
                else (
                    "Novice"
                    if diff < -2
                    else (
                        "Bronze"
                        if diff < 0
                        else (
                            "Silver"
                            if diff < 1
                            else (
                                "Gold"
                                if diff < 2
                                else (
                                    "Platinum"
                                    if diff < 3
                                    else (
                                        "Diamond"
                                        if diff < 3.5
                                        else "Gorilla" if diff < 4 else "Space Gorilla"
                                    )
                                )
                            )
                        )
                    )
                )
            )
            await interaction.response.send_message(
                embed=embeds.embed(
                    description=f"**{song.title}** [{difficulty.upper()}]\n\n"
                    + f"**Result:** {result['result']:.2f} (`{constant} {result['diff']}`) (*{rank}*)\n-# Always uses 39s constants.\n"
                    + f"**Accuracy:** {result['accuracy']:.2%}\n"
                    + f"**Score:** {'/'.join([str(res) for res in result['score_values']])}",
                    color=(
                        discord.Color.green()
                        if diff > 2
                        else (
                            discord.Color.yellow() if diff > -2 else discord.Color.red()
                        )
                    ),
                )
            )


# Add the cog to the bot
async def setup(bot):
    await bot.add_cog(CalculationService(bot))
