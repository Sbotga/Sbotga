import discord
from discord import app_commands

from typing import List
from itertools import islice

from DATA.data.pjsk import pjsk, pjsk_data

from DATA.game_api import methods

ALLOWED_REGIONS = ["jp", "en", "tw", "kr", "cn", "all"]

GUESSING_TYPES = {
    "Jacket": "jacket",
    "Jacket 30px": "jacket_30px",
    "Jacket Black and White": "jacket_bw",
    "Jacket Challenge": "jacket_challenge",
    "Character": "character",
    "Character Black and White": "character_bw",
    "Chart": "chart",
    "Chart Append": "chart_append",
    "Event": "event",
    "Song Note Count": "notes",
}

DIFFICULTIES = {
    "Master": "master",
    "Expert": "expert",
    "Hard": "hard",
    "Normal": "normal",
    "Easy": "easy",
    "Append": "append",
}


class Autocompletes:
    def __init__(self, pjsk: pjsk_data):
        self.pjsk = pjsk

    def range(self, min_value: int, max_value: int | str):
        assert type(max_value) == int or max_value == "inf"
        if max_value == "inf":
            max_value = 500

        async def _range(interaction: discord.Interaction, current: str):
            """Autocomplete function for a numeric range."""
            try:
                current_value = int(current) if current.isdigit() else 0
            except ValueError:
                current_value = min_value

            return [
                discord.app_commands.Choice(name=str(i), value=str(i))
                for i in range(min_value, max_value + 1)
                if str(i).startswith(current)
            ][:25]

        return _range

    def pjsk_region(self, allowed_regions: list[str], temp_allow_cn: bool = False):
        invalid_regions = [
            region for region in allowed_regions if region not in ALLOWED_REGIONS
        ]
        if invalid_regions:
            raise ValueError(f"Invalid regions provided: {', '.join(invalid_regions)}")

        # TODO: remove cn as they become supported
        if not temp_allow_cn:
            allowed_regions = [
                region for region in allowed_regions if region not in ["cn"]
            ]

        async def _region(interaction: discord.Interaction, current: str):
            """Autocomplete function for region selection with validation."""
            current_lower = current.lower()
            return [
                discord.app_commands.Choice(name=region.upper(), value=region)
                for region in allowed_regions
                if current_lower in region.lower()
            ][
                :25
            ]  # Discord allows a maximum of 25 choices

        return _region

    def custom_values(self, values: dict):
        async def _getvalue(interaction: discord.Interaction, current: str):
            current_lower = current.lower()
            return [
                discord.app_commands.Choice(name=name, value=value)
                for name, value in values.items()
                if current_lower in name.lower()
            ][
                :25
            ]  # Discord allows a maximum of 25 choices

        return _getvalue

    async def pjsk_difficulties(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        current_lower = current.lower()
        return [
            app_commands.Choice(name=key, value=value)
            for key, value in DIFFICULTIES.items()
            if current_lower in key.lower() or current_lower in value.lower()
        ][:25]

    async def pjsk_guessing_types(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        current_lower = current.lower()
        return [
            app_commands.Choice(name=key, value=value)
            for key, value in GUESSING_TYPES.items()
            if current_lower in key.lower() or current_lower in value.lower()
        ][:25]

    async def pjsk_char(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        full_names = []
        chars = [value["givenName"] for value in self.pjsk.characters_game]
        for value in self.pjsk.characters_game:
            name = (
                str(value["givenName"]) + " " + str(value["firstName"])
                if value.get("firstName") and value.get("unit") != "piapro"
                else (
                    str(value["firstName"]) + " " + str(value["givenName"])
                    if value.get("firstName")
                    else value["givenName"]
                )
            )
            full_names.append(name)
            if value.get("firstName"):
                chars.append(str(value["givenName"]) + " " + str(value["firstName"]))
                chars.append(str(value["firstName"]) + " " + str(value["givenName"]))
                chars.append(str(value["firstName"]))
        vas = [
            value["characterVoice"]
            for value in self.pjsk.characters
            if value.get("characterVoice")
        ]
        ac = set(
            [
                name
                for name in full_names
                if (current.lower() in name.lower())
                or (current.lower().replace(" ", "") in name.lower().replace(" ", ""))
            ]
        )
        if len(ac) == 0:
            ac = set(
                [
                    name
                    for name in vas
                    if (current.lower() in name.lower())
                    or (
                        current.lower().replace(" ", "")
                        in name.lower().replace(" ", "")
                    )
                ]
            )

        ac = [app_commands.Choice(name=name, value=name) for name in ac]
        return ac[:25]

    async def pjsk_card(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        if current == "":
            return [
                app_commands.Choice(
                    name="Card search. Supports rarity (1*, 2*, birthday, etc.), character, and attribute.",
                    value="tutorial_choice",
                )
            ]

        # Precompute rarity mapping
        rarity_mapping = {
            "1*": "1☆",
            "2*": "2☆",
            "3*": "3☆",
            "4*": "4☆",
            "birthday": "🎀",
            "bday": "🎀",
            "bd": "🎀",
        }

        # Replace rarities in input, ensuring we match entire words only
        current = current.lower()
        current_parts = current.split()
        replaced_parts = []

        for part in current_parts:
            if part in rarity_mapping:
                replaced_parts.append(rarity_mapping[part])
            else:
                replaced_parts.append(part)

        # Check for conflicting rarities
        rarities = [part for part in replaced_parts if part in rarity_mapping.values()]
        if len(rarities) > 1:
            return [app_commands.Choice(name="Invalid search", value="invalid_search")]

        # Helper to parse card names
        def parse_card_name(name: str):
            """
            Parses the card name into components:
            CHARACTER NAME - 4☆ [Attribute] CARD NAME
            Returns (character_name, rarity, attribute, card_name).
            """
            parts = name.split(" - ")
            if len(parts) < 2:
                return None, None, None, None

            character_name = parts[0].lower()
            card_details = parts[1].lower().split(" ")

            rarity = card_details[0] if card_details else None
            attribute = (
                card_details[1].strip("[]")
                if len(card_details) > 1 and "[" in card_details[1]
                else None
            )
            card_name = " ".join(card_details[2:]) if len(card_details) > 2 else None

            return character_name, rarity, attribute, card_name

        # Preprocess card data
        parsed_cards = []
        for name, value in pjsk.cards_en_jp.items():
            parsed = parse_card_name(name)
            if parsed[0]:  # Ensure valid parsing
                parsed_cards.append((name, value, *parsed))

        # Filter matches
        matches = []
        for name, value, character_name, rarity, attribute, card_name in parsed_cards:
            if all(
                any(
                    part in field
                    for field in (character_name, rarity, attribute, card_name)
                    if field
                )
                for part in replaced_parts
            ):
                matches.append(
                    app_commands.Choice(
                        name=f"({str(value)}) " + name, value=str(value)
                    )
                )
                if len(matches) >= 25:  # Stop early if we hit the max
                    break

        # Return results or invalid search
        if not matches:
            return [app_commands.Choice(name="Invalid search", value="invalid_search")]

        return matches

    async def pjsk_song(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        song_titles = list(self.pjsk._titles.keys()) + [
            str(id) for id in self.pjsk._titles.values()
        ]

        # Use a generator for efficient filtering
        matches = (
            title
            for title in song_titles
            if (current.lower() in title.lower())
            or (current.lower().replace(" ", "") in title.lower().replace(" ", ""))
        )

        def noid(gen) -> List[str]:
            """Remove all items that are digits from the generator."""
            return list(islice((item for item in gen if not item.isdigit()), 25))

        def onlyid(gen) -> List[str]:
            """Remove all items that are not digits from the generator."""
            return list(islice((item for item in gen if item.isdigit()), 25))

        # Apply appropriate filter based on `current`
        filtered_matches = noid(matches) if not current.isdigit() else onlyid(matches)

        # Return the first 25 matches as app_commands.Choice objects
        return [
            app_commands.Choice(name=title, value=title) for title in filtered_matches
        ]


autocompletes = Autocompletes(pjsk)
