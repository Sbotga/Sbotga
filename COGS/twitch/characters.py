import twitchio
from twitchio.ext import commands

import datetime

from main import TwitchBot

from typing import Annotated

from DATA.helpers import converters


class CharCog(commands.Cog):
    def __init__(self, bot: TwitchBot):
        self.bot = bot

    @commands.command(aliases=["birthday"])
    async def birthdays(
        self,
        ctx: commands.Context,
        char: Annotated[str, converters.CharacterConverter] = None,
    ):
        if not (await self.bot.run_checks(ctx, True, False)):
            return
        today = datetime.datetime.now()
        upcoming_birthdays = []
        next_30_days = today + datetime.timedelta(days=30)
        prev_day = today - datetime.timedelta(days=1)
        await self.bot.command_ran(ctx)
        if char:
            character = self.bot.pjsk.characters[char["id"] - 1]
            # Parse the birthday into a datetime object for the current year
            patterns = [
                "%b %d",
                "%b.%d",
                "%b. %d",
            ]  # Different patterns to handle variations

            for pattern in patterns:
                try:
                    birthday_date = datetime.datetime.strptime(
                        character["birthday"], pattern
                    )
                    break
                except ValueError:
                    continue
            char = self.bot.pjsk.characters_game[character["characterId"] - 1]
            name = (
                str(char["givenName"]) + " " + str(char["firstName"])
                if char.get("firstName") and char.get("unit") != "piapro"
                else (
                    str(char["firstName"]) + " " + str(char["givenName"])
                    if char.get("firstName")
                    else char["givenName"]
                )
            )
            await ctx.reply(
                f"{name} - {character['birthday'].replace('.', ' ')}"
                or "No upcoming birthdays in the next 30 days."
            )
        else:
            for character in self.bot.pjsk.characters:  # Sort by date TODO
                # Parse the birthday into a datetime object for the current year
                patterns = [
                    "%b %d",
                    "%b.%d",
                    "%b. %d",
                ]  # Different patterns to handle variations

                for pattern in patterns:
                    try:
                        birthday_date = datetime.datetime.strptime(
                            character["birthday"], pattern
                        )
                        break
                    except ValueError:
                        continue

                birthday_this_year = birthday_date.replace(year=today.year)

                # Check if the birthday falls on the previous day or within the next 30 days
                if prev_day <= birthday_this_year <= next_30_days:
                    char = self.bot.pjsk.characters_game[character["characterId"] - 1]
                    name = (
                        str(char["givenName"]) + " " + str(char["firstName"])
                        if char.get("firstName") and char.get("unit") != "piapro"
                        else (
                            str(char["firstName"]) + " " + str(char["givenName"])
                            if char.get("firstName")
                            else char["givenName"]
                        )
                    )
                    upcoming_birthdays.append(
                        f"{name} - {character['birthday'].replace('.', ' ')}"
                    )

                # If the birthday has already passed, check for next year's birthday
                elif birthday_this_year < prev_day:
                    birthday_next_year = birthday_this_year.replace(year=today.year + 1)
                    if today <= birthday_next_year <= next_30_days:
                        upcoming_birthdays.append(
                            f"{name} - {character['birthday'].replace('.', ' ')}"
                        )

            to_send = (
                " |     | ".join(upcoming_birthdays[::-1])
                if upcoming_birthdays
                else "No upcoming birthdays in the next 30 days."
            )
            await ctx.reply(to_send)

    @commands.command(aliases=["char"])
    async def character(
        self,
        ctx: commands.Context,
        char: Annotated[str, converters.CharacterConverter] = None,
    ):
        if not (await self.bot.run_checks(ctx, True, False)):
            return
        await self.bot.command_ran(ctx)
        if char:
            character = self.bot.pjsk.characters[char["id"] - 1]
            char_game = self.bot.pjsk.characters_game[character["characterId"] - 1]
            name = (
                str(char_game["givenName"]) + " " + str(char_game["firstName"])
                if char_game.get("firstName") and char_game.get("unit") != "piapro"
                else (
                    str(char_game["firstName"]) + " " + str(char_game["givenName"])
                    if char_game.get("firstName")
                    else char_game["givenName"]
                )
            )

            stuff = f"{name} - {self.bot.pjsk.unit_map[char_game['unit']]} |  | {'VA - ' + character['characterVoice'] + ' |  | ' if character.get('characterVoice') else ''}Birthday - {character['birthday'].replace('.', ' ')} || Gender - {char_game['gender'].capitalize()} || Height (3rd anni) - {character['height']} |  | !char_profile, !char_intro"  # TODO prefix
            await ctx.reply(stuff)
        else:
            await ctx.reply("Character not found.")

    @commands.command(aliases=["char_profile"])
    async def character_profile(
        self,
        ctx: commands.Context,
        char: Annotated[str, converters.CharacterConverter] = None,
    ):
        if not (await self.bot.run_checks(ctx, True, False)):
            return
        await self.bot.command_ran(ctx)
        if char:
            character = self.bot.pjsk.characters[char["id"] - 1]
            char_game = self.bot.pjsk.characters_game[character["characterId"] - 1]
            name = (
                str(char_game["givenName"]) + " " + str(char_game["firstName"])
                if char_game.get("firstName") and char_game.get("unit") != "piapro"
                else (
                    str(char_game["firstName"]) + " " + str(char_game["givenName"])
                    if char_game.get("firstName")
                    else char_game["givenName"]
                )
            )

            if character.get("school"):
                school = f"{character['school'].replace('HS', 'High School')} (Year {character['schoolYear'] if character['schoolYear'] != '-' else 'N/A'})"
            else:
                school = None

            stuff = f"{name} - {self.bot.pjsk.unit_map[char_game['unit']]}{' |  | ' + school if school else ''} |  | Hobbies: {character['hobby']} || Special Skills: {character['specialSkill']} || Hates: {character['weak']}, {character['hatedFood']} || Loves: {character['favoriteFood']} |  | !char, !char_intro"  # TODO: prefix
            await ctx.reply(stuff)
        else:
            await ctx.reply("Character not found.")

    @commands.command(aliases=["char_intro", "character_intro", "char_introduction"])
    async def character_introduction(
        self,
        ctx: commands.Context,
        char: Annotated[str, converters.CharacterConverter] = None,
    ):
        if not (await self.bot.run_checks(ctx, True, False)):
            return
        await self.bot.command_ran(ctx)
        if char:
            character = self.bot.pjsk.characters[char["id"] - 1]
            char_game = self.bot.pjsk.characters_game[character["characterId"] - 1]
            name = (
                str(char_game["givenName"]) + " " + str(char_game["firstName"])
                if char_game.get("firstName") and char_game.get("unit") != "piapro"
                else (
                    str(char_game["firstName"]) + " " + str(char_game["givenName"])
                    if char_game.get("firstName")
                    else char_game["givenName"]
                )
            )

            stuff = f"{name} - {self.bot.pjsk.unit_map[char_game['unit']]} |   | {character['introduction']} |   | !char, !char_profile"  # TODO: prefix
            await ctx.reply(stuff)
        else:
            await ctx.reply("Character not found.")


def prepare(bot: TwitchBot):
    bot.add_cog(CharCog(bot))
