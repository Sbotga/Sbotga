import discord
from discord.ext import commands, tasks
from discord import app_commands

from discord.app_commands import locale_str
from COGS.discord_translations import translations

from main import DiscordBot

import time, csv, math, asyncio
from datetime import datetime, timezone
from io import BytesIO, StringIO
import typing

import aiohttp
from PIL import Image, ImageDraw, ImageFont

from DATA.helpers import discord_autocompletes as autocompletes
from DATA.helpers import tools
from DATA.helpers import embeds
from DATA.helpers.unblock import to_process_with_timeout
from DATA.helpers import converters

from DATA.game_api import methods

from COGS.progress_generate import generate_progress, DifficultyCategory


class DataAnalysis(commands.Cog):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

        self.cooldown_progress = {}
        self.cooldown_b30 = {}

        self.cog_tasks.start()

    def cog_unload(self):
        """Cancel the task to prevent orphaned tasks."""
        self.cog_tasks.cancel()

    @tasks.loop(seconds=60)
    async def cog_tasks(self):
        for uid, last_ran in list(self.cooldown_b30.items()):
            if time.time() - last_ran > 120:  # 2 minutes
                self.cooldown_b30.pop(uid, None)
        for uid, last_ran in list(self.cooldown_progress.items()):
            if time.time() - last_ran > 120:  # 2 minutes
                self.cooldown_progress.pop(uid, None)

    async def generate_progress(
        self, data: dict, difficulty: str, private: bool, user: discord.User
    ) -> BytesIO:
        def _make():
            diffs = {}
            added = []
            current = {}
            RESULT_PRIORITY = {
                "full_perfect": 4,
                "full_combo": 3,
                "clear": 2,
                "not_clear": 1,
                None: 0,
            }

            for music_id, ds in self.bot.pjsk.difficulties.items():
                if ds.get(difficulty):
                    check_regions = list(data.keys())
                    leak, song_available_regions = methods.Tools.get_music_regions(
                        music_id
                    )
                    song_has_append_regions = methods.Tools.get_music_append_regions(
                        music_id
                    )
                    if leak:  # Leak on all regions
                        continue
                    if not any(
                        m_ar in check_regions for m_ar in song_available_regions
                    ):  # It's not found in any of the check regions.
                        continue
                    if difficulty == "append" and (
                        not any(
                            m_ar in check_regions for m_ar in song_has_append_regions
                        )
                    ):  # It's append and append was not found in any of the check regions.
                        continue

                    playlevel = ds[difficulty]["playLevel"]
                    if type(playlevel) == list:
                        playlevel = playlevel[1]  # rerated
                    if f"{music_id}{difficulty}" in added:
                        continue
                    else:
                        added.append(f"{music_id}{difficulty}")
                        if not diffs.get(playlevel):
                            diffs[playlevel] = 1
                        else:
                            diffs[playlevel] += 1

            for r, d in data.items():
                song_progress_info = {}
                for song_data in d["userMusics"]:
                    for song_progress_info in song_data["userMusicDifficultyStatuses"]:
                        if song_progress_info["musicDifficulty"] != difficulty:
                            continue
                        playlevel = self.bot.pjsk.difficulties[
                            song_progress_info["musicId"]
                        ][difficulty]["playLevel"]
                        if type(playlevel) == list:
                            playlevel = playlevel[1]  # rerated

                        # In case Master Data wasn't correctly updated
                        # Prevent broken donuts.
                        # Especially since adding Appends doesn't have a "release date", meaning any updates are done directly to master data and may not reflect until the next update
                        if f"{song_progress_info['musicId']}{difficulty}" in added:
                            pass
                        else:
                            added.append(f"{song_progress_info['musicId']}{difficulty}")
                            if not diffs.get(playlevel):
                                diffs[playlevel] = 1
                            else:
                                diffs[playlevel] += 1
                        # End diff added check.

                        c_d = current.get(
                            f"{song_progress_info['musicId']}{difficulty}",
                            [playlevel, None],
                        )
                        for result in song_progress_info["userMusicResults"]:
                            res = result["playResult"]

                            # Compare current result with existing one based on priority
                            if (
                                c_d[1] is None
                                or RESULT_PRIORITY[res] > RESULT_PRIORITY[c_d[1]]
                            ):
                                c_d[1] = res

                        current[f"{song_progress_info['musicId']}{difficulty}"] = c_d

            difficulties = {
                playlevel: {"all": count, "ap": 0, "fc": 0, "clear": 0}
                for playlevel, count in diffs.items()
            }
            for _, result in current.items():
                if result[1] in [None, "not_clear"]:
                    continue
                elif result[1] in ["clear"]:
                    difficulties[result[0]]["clear"] += 1
                elif result[1] in ["full_combo"]:
                    difficulties[result[0]]["clear"] += 1
                    difficulties[result[0]]["fc"] += 1
                elif result[1] in ["full_perfect"]:
                    difficulties[result[0]]["clear"] += 1
                    difficulties[result[0]]["fc"] += 1
                    difficulties[result[0]]["ap"] += 1

            final_results = [
                DifficultyCategory(
                    diff, value["ap"], value["fc"], value["clear"], value["all"]
                )
                for diff, value in sorted(difficulties.items())
            ]

            img = generate_progress(final_results, difficulty)

            img = Image.open(img)

            SCALE = 2
            new_height = img.height + (
                len(data) * 100 * SCALE
            )  # Adjusting for multiple regions
            new_img = Image.new(
                "RGBA", (img.width, new_height), (50, 50, 50, 255)
            )  # Dark gray bar
            new_img.paste(img, (0, (len(data) * 100 * SCALE)))

            draw = ImageDraw.Draw(new_img)
            font = ImageFont.truetype("DATA/data/ASSETS/rodinntlg_eb.otf", 30 * SCALE)
            font_2 = ImageFont.truetype("DATA/data/ASSETS/rodinntlg_m.otf", 30 * SCALE)
            font_3 = ImageFont.truetype("DATA/data/ASSETS/rodinntlg_m.otf", 20 * SCALE)

            region_height_offset = 0
            for region, d in data.items():
                timestamp = d["now"] / 1000

                data_date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
                    "%Y-%m-%d"
                )
                data_time = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
                    "%H:%M"
                )
                # Apply font styles
                draw.text(
                    (10, region_height_offset + 15 * SCALE),
                    f"{d['userGamedata']['name']}" if not private else f"{user.name}",
                    font=font,
                    fill="white",
                )
                draw.text(
                    (10, region_height_offset + 60 * SCALE),
                    (
                        f"{region.upper()} ID: {d['userGamedata']['userId']}"
                        if not private
                        else f"{region.upper()} Account"
                    ),
                    font=font_3,
                    fill="white",
                )
                draw.text(
                    (img.width - 215 * SCALE, region_height_offset + 15 * SCALE),
                    f"{data_date}",
                    font=font_2,
                    fill="white",
                )
                draw.text(
                    (img.width - 200 * SCALE, region_height_offset + 50 * SCALE),
                    f"{data_time} UTC",
                    font=font_2,
                    fill="white",
                )

                # Add a white line separator after each region's section
                line_y = region_height_offset + 100 * SCALE
                draw.line((0, line_y, img.width, line_y), fill="white", width=2)
                region_height_offset += (
                    100 * SCALE  # Move the offset down by 100px for each region
                )
            output = BytesIO()
            new_img.save(output, format="PNG")
            output.seek(0)
            return output

        output = await to_process_with_timeout(_make)

        return output

    def draw_b30(
        self, songs: list, fc_only: bool, ap_only: bool, song_count: int
    ) -> BytesIO:
        """
        [
            {
                "path": "/image.png",
                "difficulty": "append",
                "name": "test",
                "constant": 32.3,
                "ap_or_fc": "ap"
            }
        ]
        """

        def text_wrap(text, font, writing, max_width, max_height):
            def textsize_from_bbox(
                text_left, text_top, text_right, text_bottom
            ) -> tuple:
                return (text_right - text_left, text_bottom - text_top)

            lines = [[]]
            words = text.split(" ")

            for i, word in enumerate(words):
                test_line = lines[-1] + ([word] if i == len(words) - 1 else [word, " "])
                test_text = "\n".join(
                    ["".join(line) for line in lines[:-1]] + ["".join(test_line)]
                )

                w, h = textsize_from_bbox(
                    *writing.multiline_textbbox((0, 0), test_text, font=font)
                )

                if w <= max_width:
                    lines[-1].append(word)
                    if i != len(words) - 1:
                        lines[-1].append(" ")
                else:
                    if lines[-1]:
                        lines.append([])
                    lines[-1].append(word)
                    if i != len(words) - 1:
                        lines[-1].append(" ")

                    w, h = textsize_from_bbox(
                        *writing.multiline_textbbox(
                            (0, 0),
                            "\n".join(["".join(line) for line in lines]),
                            font=font,
                        )
                    )
                    if w > max_width:  # Word still doesn't fit; split by character
                        lines.pop()
                        current_line = []
                        for char in word:
                            current_line.append(char)
                            w, h = textsize_from_bbox(
                                *writing.multiline_textbbox(
                                    (0, 0),
                                    "\n".join(["".join(current_line)]),
                                    font=font,
                                )
                            )
                            if w > max_width:
                                lines.append(current_line[:-1])
                                current_line = [current_line[-1]]
                                w, h = textsize_from_bbox(
                                    *writing.multiline_textbbox(
                                        (0, 0),
                                        "\n".join(["".join(line) for line in lines]),
                                        font=font,
                                    )
                                )
                                if h > max_height:
                                    break
                        if current_line:
                            lines.append(current_line)

            # Remove empty lines
            lines = [line for line in lines if "".join(line).strip()]

            trimmed = False
            while (
                textsize_from_bbox(
                    *writing.multiline_textbbox(
                        (0, 0),
                        "\n".join(["".join(line).rstrip() for line in lines]),
                        font=font,
                    )
                )[1]
                > max_height
            ):
                trimmed = True
                if len(lines) > 1:
                    lines.pop()
                else:
                    lines[-1] = lines[-1][: max(0, len(lines[-1]) - 1)]
                    if lines[-1]:
                        lines[-1][-1] = lines[-1][-1][:-3] + "..."
                    else:
                        lines[-1] = ["..."]
                    break

            if trimmed and lines:
                last_line = "".join(lines[-1]).rstrip()
                while (
                    textsize_from_bbox(
                        *writing.multiline_textbbox(
                            (0, 0), last_line + "...", font=font
                        )
                    )[0]
                    > max_width
                ):
                    if len(last_line) > 1:
                        last_line = last_line[:-1]
                    else:
                        last_line = "..."
                        break
                lines[-1] = list(last_line + "...")

            return "\n".join(["".join(line).rstrip() for line in lines])

        def determine_grid(song_count: int):
            column_options = [3, 4, 5, 2]
            best_fit = None
            min_gaps = float("inf")

            for columns in column_options:
                rows = math.ceil(song_count / columns)
                gaps = (rows * columns) - song_count

                if gaps == 0:  # Perfect fit
                    return rows, columns

                # Select the configuration with the fewest gaps
                if gaps < min_gaps:
                    min_gaps = gaps
                    best_fit = (rows, columns)

            return best_fit

        amount_rows, amount_columns = determine_grid(song_count)

        base_width = 2000  # Width for 3 columns
        WIDTH = int(base_width * (amount_columns / 3))

        HEADER_HEIGHT = 100
        base_height = 2500  # Height for 10 rows
        HEIGHT = int(base_height * (amount_rows / 10)) + HEADER_HEIGHT

        SCALE = 1
        WIDTH *= SCALE
        HEIGHT *= SCALE
        HEADER_HEIGHT *= SCALE

        FONT_PATH = "DATA/data/ASSETS/rodinntlg_eb.otf"

        KITTY_PATH = "DATA/data/ASSETS/kitty.png"

        # Create base image with 2x resolution
        image = Image.new("RGBA", (WIDTH, HEIGHT), "#FFFFFF")
        draw = ImageDraw.Draw(image)

        # Open and resize the kitty.png image to match the base image dimensions
        kitty_image = Image.open(KITTY_PATH).resize((WIDTH, HEIGHT), Image.LANCZOS)

        # Paste the resized kitty image onto the base image
        image.paste(kitty_image, (0, 0))

        # Top bar
        draw.rectangle(
            [(0, 0), (WIDTH, HEADER_HEIGHT)], fill="#b4ccfa", outline="#00194a"
        )

        # Top-left text
        font = ImageFont.truetype(FONT_PATH, 48 * SCALE)
        filtered = " - FCs Only" if fc_only else " - APs Only" if ap_only else ""
        draw.text(
            (10, 14 * SCALE),
            f"Your best {song_count} chart{'s' if song_count != 1 else ''}" + filtered,
            fill="black",
            font=font,
        )
        watermark = ImageFont.truetype(FONT_PATH, 30 * SCALE)
        draw.text((10, 65 * SCALE), "Generated by Sbotga", fill="black", font=watermark)

        GUTTER_WIDTH = 60 * SCALE
        GUTTER_HEIGHT = 70 * SCALE
        CARD_WIDTH = int(
            (WIDTH - (GUTTER_WIDTH * (amount_columns + 1))) / amount_columns
        )
        CARD_HEIGHT = int(
            (HEIGHT - HEADER_HEIGHT - (GUTTER_HEIGHT * (amount_rows + 1))) / amount_rows
        )
        JACKET_SIZE = (CARD_HEIGHT - 20 * SCALE, CARD_HEIGHT - 20 * SCALE)

        # Difficulty Assets (JPG backgrounds)
        difficulty_colors = {
            "append": "DATA/data/ASSETS/append_color.jpg",
            "hard": "DATA/data/ASSETS/hard_color.jpg",
            "normal": "DATA/data/ASSETS/normal_color.jpg",
            "easy": "DATA/data/ASSETS/easy_color.jpg",
            "master": "DATA/data/ASSETS/master_color.jpg",
            "expert": "DATA/data/ASSETS/expert_color.jpg",
        }

        # Indicator Assets (PNG for transparency)
        indicator_images = {
            "append_ap": "DATA/data/ASSETS/append_ap.png",
            "append_fc": "DATA/data/ASSETS/append_fc.png",
            "normal_ap": "DATA/data/ASSETS/normal_ap.png",
            "normal_fc": "DATA/data/ASSETS/normal_fc.png",
        }

        # Jackets (Default Path set to 001 for now)
        jackets = [song["path"] for song in songs]

        # Preload assets
        indicators = {
            key: Image.open(path).resize((72, 72), Image.LANCZOS)
            for key, path in indicator_images.items()
        }

        difficulty_images = {
            key: Image.open(path)
            .resize((CARD_WIDTH, CARD_HEIGHT), Image.LANCZOS)
            .convert("RGBA")
            for key, path in difficulty_colors.items()
        }

        jacket_images = [
            Image.open(path).resize(JACKET_SIZE, Image.LANCZOS) if path else None
            for path in jackets
        ]

        # Initialize total difficulty for ranking calculation
        total_difficulty = 0

        # Draw cards
        idx = 0
        for song in songs:
            gridX = idx % amount_columns
            gridY = idx // amount_columns

            xPos = gridX * CARD_WIDTH + (GUTTER_WIDTH * (gridX + 1))
            yPos = HEADER_HEIGHT + (gridY * CARD_HEIGHT) + (GUTTER_HEIGHT * (gridY + 1))

            difficulty_number = song["constant"]
            badge_type = song["difficulty"]

            # Randomize AP/FC status
            ap_fc = song["ap_or_fc"].upper()

            # Extract Color from Difficulty Image
            difficulty_img = difficulty_images[badge_type]
            difficulty_img_resized = difficulty_img.resize(
                (CARD_WIDTH + 12 * SCALE, CARD_HEIGHT + 12 * SCALE), Image.LANCZOS
            )
            image.paste(difficulty_img_resized, (xPos - 6 * SCALE, yPos - 6 * SCALE))

            # Sample the top-left and bottom-right corner colors for the gradient
            top_left_color = difficulty_img.getpixel((5, 5))
            bottom_right_color = difficulty_img.getpixel(
                (CARD_WIDTH - 5, CARD_HEIGHT - 5)
            )

            # Generate the gradient for the stroke
            def create_gradient(start_color, end_color, width, height):
                gradient = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                for y in range(height):
                    # Calculate the blend factor for each pixel along the y-axis
                    blend_factor = y / height
                    r = int(
                        start_color[0] * (1 - blend_factor)
                        + end_color[0] * blend_factor
                    )
                    g = int(
                        start_color[1] * (1 - blend_factor)
                        + end_color[1] * blend_factor
                    )
                    b = int(
                        start_color[2] * (1 - blend_factor)
                        + end_color[2] * blend_factor
                    )
                    a = int(
                        start_color[3] * (1 - blend_factor)
                        + end_color[3] * blend_factor
                    )

                    for x in range(width):
                        gradient.putpixel((x, y), (r, g, b, a))

                return gradient

            # Create the gradient based on sampled colors
            STROKE_SIZE = 20 * SCALE
            gradient = create_gradient(
                top_left_color,
                bottom_right_color,
                CARD_WIDTH + STROKE_SIZE,
                CARD_HEIGHT + STROKE_SIZE,
            )

            # Create a rounded rectangle mask for the gradient
            mask = Image.new(
                "L", (CARD_WIDTH + STROKE_SIZE, CARD_HEIGHT + STROKE_SIZE), 0
            )
            draw_mask = ImageDraw.Draw(mask)
            draw_mask.rounded_rectangle(
                [(0, 0), (CARD_WIDTH + STROKE_SIZE, CARD_HEIGHT + STROKE_SIZE)],
                radius=12 * SCALE,  # Radius of the rounded corners
                fill=255,  # White to keep the gradient within the rounded area
            )

            # Paste the gradient onto the image as the stroke, using the mask to keep it rounded
            image.paste(gradient, (xPos - 9 * SCALE, yPos - 9 * SCALE), mask)

            # Draw the base card (no stroke, just rounded corners)
            draw.rounded_rectangle(
                [(xPos, yPos), (xPos + CARD_WIDTH, yPos + CARD_HEIGHT)],
                radius=8 * SCALE,
                fill="white",
                outline=None,
            )

            # Jacket vertical centering
            jacket_x = xPos + 20 * SCALE
            jacket_y = yPos + (CARD_HEIGHT - JACKET_SIZE[1]) // 2  # Center vertically

            if jacket_images[idx]:
                image.paste(jacket_images[idx], (jacket_x, jacket_y))

            # Top-Left Difficulty Badge
            difficulty_badge_x = xPos - 10 * SCALE
            difficulty_badge_y = yPos - 30 * SCALE
            difficulty_badge_width = 120 * SCALE
            difficulty_badge_height = 50 * SCALE

            # Create the gradient based on sampled colors
            gradient = create_gradient(
                top_left_color,
                bottom_right_color,
                difficulty_badge_width,
                difficulty_badge_height,
            )

            # Create a rounded rectangle mask for the gradient
            mask = Image.new("L", (difficulty_badge_width, difficulty_badge_height), 0)
            draw_mask = ImageDraw.Draw(mask)
            draw_mask.rounded_rectangle(
                [(0, 0), (difficulty_badge_width, difficulty_badge_height)],
                radius=12 * SCALE,  # Radius of the rounded corners
                fill=255,  # White to keep the gradient within the rounded area
            )

            # Paste the gradient onto the image as the badge fill, using the mask to keep it rounded
            image.paste(gradient, (difficulty_badge_x, difficulty_badge_y), mask)

            # Stroke (black outline) with rounded corners
            draw.rounded_rectangle(
                [
                    (difficulty_badge_x, difficulty_badge_y),
                    (
                        difficulty_badge_x + difficulty_badge_width,
                        difficulty_badge_y + difficulty_badge_height,
                    ),
                ],
                radius=12 * SCALE,
                outline="#222222",  # Black stroke
                width=3 * SCALE,
            )

            # Difficulty Text (Random difficulty number inside the rectangle)
            difficulty_text = f"{math.ceil(difficulty_number * 10) / 10:.1f}"
            difficulty_font = ImageFont.truetype(
                FONT_PATH, 22 * SCALE
            )  # Slightly smaller font
            text_bbox = draw.textbbox((0, 0), difficulty_text, font=difficulty_font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            text_x = difficulty_badge_x + (difficulty_badge_width - text_width) / 2
            text_y = difficulty_badge_y + (difficulty_badge_height - text_height) / 2

            draw.text(
                (text_x, text_y), difficulty_text, fill="white", font=difficulty_font
            )

            song_title_font = ImageFont.truetype(FONT_PATH, 35 * SCALE)
            song_title = song["name"]
            max_length_px = CARD_WIDTH - JACKET_SIZE[0] - 28 * SCALE

            # Wrap the song title text
            text = text_wrap(
                song_title,
                song_title_font,
                draw,
                max_length_px,
                CARD_HEIGHT - 50 * SCALE,
            )
            song_title = text

            # Difficulty text height
            difficulty_text = f"{badge_type.upper()}"
            difficulty_font = ImageFont.truetype(FONT_PATH, 20 * SCALE)
            difficulty_bbox = draw.textbbox(
                (0, 0), difficulty_text, font=difficulty_font
            )
            difficulty_height = difficulty_bbox[3] - difficulty_bbox[1]

            # Song title height (using the same font as the title)
            song_title_bbox = draw.textbbox((0, 0), song_title, font=song_title_font)
            title_height = song_title_bbox[3] - song_title_bbox[1]

            # Calculate the total height of the title and difficulty text block
            total_text_height = (
                title_height + difficulty_height + 10 * SCALE
            )  # Add space between title and difficulty

            # Center the text block vertically in the available space
            title_y_position = yPos + (CARD_HEIGHT - total_text_height) // 2

            # Draw the song title
            title_x = xPos + JACKET_SIZE[0] + 20 * SCALE
            draw.text(
                (title_x + 10 * SCALE, title_y_position),
                song_title,
                fill="black",
                font=song_title_font,
            )

            # Draw the difficulty text below the title
            difficulty_x = xPos + JACKET_SIZE[0] + 20 * SCALE
            difficulty_y = (
                title_y_position + title_height + 10 * SCALE
            )  # Offset from the title text
            draw.text(
                (difficulty_x + 10 * SCALE, difficulty_y),
                difficulty_text,
                fill="black",
                font=difficulty_font,
            )

            # Update total difficulty for ranking calculation
            total_difficulty += difficulty_number

            indicator = indicators[
                f"{'normal' if badge_type != 'append' else 'append'}_{ap_fc.lower()}"
            ]
            indicator_x = xPos + CARD_WIDTH - 40 * SCALE
            indicator_y = yPos + CARD_HEIGHT - 40 * SCALE
            image.paste(indicator, (indicator_x, indicator_y), indicator)

            idx += 1

        overall_ranking = total_difficulty / song_count

        ranking_text = f"Ranking: {overall_ranking:.2f}"
        ranking_bbox = draw.textbbox((0, 0), ranking_text, font=font)
        ranking_width = ranking_bbox[2] - ranking_bbox[0]
        draw.text(
            (WIDTH - ranking_width - 10 * SCALE, 24 * SCALE),
            ranking_text,
            fill="black",
            font=font,
        )

        obj = BytesIO()
        image.save(obj, "PNG")
        obj.seek(0)
        return obj

    async def generate_b30(
        self,
        data: dict,
        user: discord.User,
        region: str = "jp",
        private: bool = False,
        fc_only: bool = False,
        ap_only: bool = False,
        song_count: int = 30,
    ):
        assert not (fc_only and ap_only)

        def _make(region: str):
            if region == "all":
                # If region is 'all', iterate over each region in data
                query_params = []
                region_height_offset = 0  # Keep track of height offset for each region
                for reg, d in data.items():
                    music_data = d["userMusics"]
                    user_data = d["userGamedata"]
                    user_id = user_data["userId"]
                    user_name = user_data["name"]
                    timestamp = d["now"] / 1000

                    api = methods.Tools.get_api(reg)

                    diffs = api.get_master_data("musicDifficulties.json")

                    for entry in music_data:
                        for diff in entry["userMusicDifficultyStatuses"]:
                            difficulty = diff["musicDifficulty"]
                            temp_queries = []
                            for result in diff["userMusicResults"]:
                                if result["fullComboFlg"] or result["fullPerfectFlg"]:
                                    if result["fullPerfectFlg"]:
                                        if fc_only:
                                            break
                                    if ap_only and not result["fullPerfectFlg"]:
                                        continue

                                    music_id = entry["musicId"]
                                    diff_entry = next(
                                        (
                                            d
                                            for d in diffs
                                            if d["musicId"] == music_id
                                            and d["musicDifficulty"] == difficulty
                                        ),
                                        None,
                                    )
                                    if diff_entry:
                                        effective_level = diff_entry["playLevel"]
                                        if type(effective_level) == list:
                                            effective_level = effective_level[
                                                1
                                            ]  # rerated
                                        if result["fullPerfectFlg"]:
                                            effective_level += 1
                                        if difficulty == "append":
                                            effective_level += 2
                                        temp_queries.append(
                                            (
                                                effective_level,
                                                music_id,
                                                difficulty,
                                                result["fullPerfectFlg"],
                                            )
                                        )
                                query_params += temp_queries

                query_params.sort(reverse=True, key=lambda x: (x[0], x[3]))
                highest_fc = query_params[0][0] if query_params else 0

                if query_params and query_params[0][2] == "append":
                    highest_fc -= 2

                append_entries = [
                    entry
                    for entry in query_params
                    if entry[2] == "append" and entry[0] >= highest_fc - 2
                ]
                filtered_query_params = list(
                    set(
                        [
                            entry
                            for entry in query_params
                            if entry[2] != "append" and entry[0] >= highest_fc - 2
                        ]
                    )
                )

                while len(filtered_query_params) < song_count and highest_fc > 0:
                    filtered_query_params = list(
                        set(
                            [
                                entry
                                for entry in query_params
                                if entry[2] != "append" and entry[0] >= highest_fc - 2
                            ]
                        )
                    )
                    append_entries = [
                        entry
                        for entry in query_params
                        if entry[2] == "append" and entry[0] >= highest_fc - 2
                    ]
                    highest_fc -= 1
            else:
                # If region is not 'all', process the specific region's data
                music_data = data["userMusics"]
                user_data = data["userGamedata"]
                user_id = user_data["userId"]
                user_name = user_data["name"]

                api = methods.Tools.get_api(region)

                diffs = api.get_master_data("musicDifficulties.json")

                # Step 1: Build the Query
                query_params = []
                for entry in music_data:
                    for diff in entry["userMusicDifficultyStatuses"]:
                        difficulty = diff["musicDifficulty"]
                        temp_queries = []
                        for result in diff["userMusicResults"]:
                            if result["fullComboFlg"] or result["fullPerfectFlg"]:
                                if result["fullPerfectFlg"]:
                                    if fc_only:
                                        break
                                if ap_only and not result["fullPerfectFlg"]:
                                    continue

                                music_id = entry["musicId"]
                                diff_entry = next(
                                    (
                                        d
                                        for d in diffs
                                        if d["musicId"] == music_id
                                        and d["musicDifficulty"] == difficulty
                                    ),
                                    None,
                                )
                                if diff_entry:
                                    effective_level = diff_entry["playLevel"]
                                    if type(effective_level) == list:
                                        effective_level = effective_level[1]  # rerated
                                    if result["fullPerfectFlg"]:
                                        effective_level += 1
                                    if difficulty == "append":
                                        effective_level += 2
                                    temp_queries.append(
                                        (
                                            effective_level,
                                            music_id,
                                            difficulty,
                                            result["fullPerfectFlg"],
                                        )
                                    )
                            query_params += temp_queries
                query_params.sort(reverse=True, key=lambda x: (x[0], x[3]))
                highest_fc = query_params[0][0] if query_params else 0

                if query_params and query_params[0][2] == "append":
                    highest_fc -= 2

                append_entries = [
                    entry
                    for entry in query_params
                    if entry[2] == "append" and entry[0] >= highest_fc - 2
                ]
                filtered_query_params = list(
                    set(
                        [
                            entry
                            for entry in query_params
                            if entry[2] != "append" and entry[0] >= highest_fc - 2
                        ]
                    )
                )

                while len(filtered_query_params) < song_count and highest_fc > 0:
                    filtered_query_params = list(
                        set(
                            [
                                entry
                                for entry in query_params
                                if entry[2] != "append" and entry[0] >= highest_fc - 2
                            ]
                        )
                    )
                    append_entries = [
                        entry
                        for entry in query_params
                        if entry[2] == "append" and entry[0] >= highest_fc - 2
                    ]
                    highest_fc -= 1

            songs = []
            entries = filtered_query_params + append_entries

            # Adding songs with overwriting logic
            for level, music_id, difficulty, ap in entries:
                song = {
                    "music_id": music_id,
                    "path": methods.Tools.get_music_jacket(music_id),
                    "difficulty": difficulty,
                    "name": methods.Tools.get_music_name(music_id),
                    "constant": (self.bot.get_constant_sync(music_id, difficulty, ap)),
                    "ap_or_fc": "ap" if ap else "fc",
                }

                existing_song = next(
                    (
                        s
                        for s in songs
                        if s["music_id"] == music_id and s["difficulty"] == difficulty
                    ),
                    None,
                )

                if existing_song:
                    if song["ap_or_fc"] == "ap" and existing_song["ap_or_fc"] == "fc":
                        songs.remove(existing_song)
                    else:
                        continue  # Skip adding this song as the existing one is better or equal

                songs.append(song)

            songs = sorted(songs, key=lambda s: s["constant"], reverse=True)[
                :song_count
            ]

            img = self.draw_b30(
                songs, fc_only=fc_only, ap_only=ap_only, song_count=song_count
            )
            img = Image.open(img)

            SCALE = 2

            if region == "all":
                # Step 3: Modify the Image
                new_height = img.height + (
                    len(data) * 100 * SCALE
                )  # Adjusting for multiple regions
                new_img = Image.new(
                    "RGBA", (img.width, new_height), (50, 50, 50, 255)
                )  # Dark gray bar
                new_img.paste(img, (0, (len(data) * 100 * SCALE)))

                draw = ImageDraw.Draw(new_img)
                font = ImageFont.truetype(
                    "DATA/data/ASSETS/rodinntlg_eb.otf", 30 * SCALE
                )
                font_2 = ImageFont.truetype(
                    "DATA/data/ASSETS/rodinntlg_m.otf", 30 * SCALE
                )
                font_3 = ImageFont.truetype(
                    "DATA/data/ASSETS/rodinntlg_m.otf", 20 * SCALE
                )

                # Draw user information for each region
                for region, d in data.items():
                    timestamp = d["now"] / 1000

                    data_date = datetime.fromtimestamp(
                        timestamp, tz=timezone.utc
                    ).strftime("%Y-%m-%d")
                    data_time = datetime.fromtimestamp(
                        timestamp, tz=timezone.utc
                    ).strftime("%H:%M")
                    # Apply font styles
                    draw.text(
                        (10, region_height_offset + 15 * SCALE),
                        (
                            f"{d['userGamedata']['name']}"
                            if not private
                            else f"{user.name}"
                        ),
                        font=font,
                        fill="white",
                    )
                    draw.text(
                        (10, region_height_offset + 60 * SCALE),
                        (
                            f"{region.upper()} ID: {d['userGamedata']['userId']}"
                            if not private
                            else f"{region.upper()} Account"
                        ),
                        font=font_3,
                        fill="white",
                    )
                    draw.text(
                        (img.width - 215 * SCALE, region_height_offset + 15 * SCALE),
                        f"{data_date}",
                        font=font_2,
                        fill="white",
                    )
                    draw.text(
                        (img.width - 200 * SCALE, region_height_offset + 50 * SCALE),
                        f"{data_time} UTC",
                        font=font_2,
                        fill="white",
                    )

                    # Add a white line separator after each region's section
                    line_y = region_height_offset + 100 * SCALE
                    draw.line((0, line_y, img.width, line_y), fill="white", width=2)
                    region_height_offset += (
                        100 * SCALE  # Move the offset down by 100px for each region
                    )
            else:
                # Step 3: Modify the Image
                new_height = img.height + 100 * SCALE  # Adjusting for one region
                new_img = Image.new(
                    "RGBA", (img.width, new_height), (50, 50, 50, 255)
                )  # Dark gray bar
                new_img.paste(img, (0, 100 * SCALE))

                timestamp = data["now"] / 1000
                data_date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
                    "%Y-%m-%d"
                )
                data_time = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
                    "%H:%M"
                )

                draw = ImageDraw.Draw(new_img)
                font = ImageFont.truetype(
                    "DATA/data/ASSETS/rodinntlg_eb.otf", 30 * SCALE
                )
                font_2 = ImageFont.truetype(
                    "DATA/data/ASSETS/rodinntlg_m.otf", 30 * SCALE
                )
                font_3 = ImageFont.truetype(
                    "DATA/data/ASSETS/rodinntlg_m.otf", 20 * SCALE
                )

                # Draw user information
                draw.text(
                    (10, 15 * SCALE),
                    f"{user_name}" if not private else f"{user.name}",
                    font=font,
                    fill="white",
                )
                draw.text(
                    (10, 60 * SCALE),
                    (
                        f"{region.upper()} ID: {user_id}"
                        if not private
                        else f"{region.upper()} Account"
                    ),
                    font=font_3,
                    fill="white",
                )
                draw.text(
                    (img.width - 215 * SCALE, 10 * SCALE),
                    f"{data_date}",
                    font=font_2,
                    fill="white",
                )
                draw.text(
                    (img.width - 200 * SCALE, 50 * SCALE),
                    f"{data_time} UTC",
                    font=font_2,
                    fill="white",
                )

            # Step 4: Return as BytesIO
            output = BytesIO()
            new_img.save(output, format="PNG")
            output.seek(0)
            return output

        output = await to_process_with_timeout(_make, region, timeout=40)

        return output

    def is_owner():
        async def predicate(ctx: commands.Context):
            return ctx.author.id in ctx.bot.owner_ids

        return commands.check(predicate)

    @commands.command(name="dev_progress")
    @is_owner()
    async def dev_progress(
        self,
        ctx: commands.Context,
        user_id: typing.Union[discord.User, str],
        region: str,
        difficulty: str,
    ):
        try:
            if region not in ["en", "jp", "tw", "kr", "cn", "all"]:
                return await ctx.reply(
                    await translations.other_context_translate(
                        locale_str(
                            "errors.unsupported_region",
                            replacements={"{region}": region.upper()},
                        ),
                        ctx.message,
                        "en-US",
                        ctx.bot,
                    )
                )
            if isinstance(user_id, discord.User):
                pjsk_id = await self.bot.user_data.discord.get_pjsk_id(
                    user_id.id, region="en"
                )
                pjsk_id_jp = await self.bot.user_data.discord.get_pjsk_id(
                    user_id.id, region="jp"
                )
            else:
                pjsk_id = user_id
            if region != "all":
                api = methods.Tools.get_api(region)
                data = api.attempt_get_user_data(pjsk_id)
                data = {region: data}
            elif region == "all":
                data = {}
                for api, region in [(api, api.app_region) for api in methods.all_apis]:
                    pjsk_id = await self.bot.user_data.discord.get_pjsk_id(
                        ctx.author.id, region
                    )
                    if not pjsk_id:
                        continue
                    acc_data = api.attempt_get_user_data(pjsk_id)
                    if not acc_data:
                        continue
                    data[region] = acc_data
                if not data:
                    embed = embeds.error_embed(
                        "I don't have access to **any** of your account data.\n\nThis requires a temporary data transfer. </user pjsk update_data:1325347278805929994>"
                    )
                    return await ctx.reply(embed=embed)

            if not data:
                embed = embeds.error_embed(
                    "I don't have access to your account data.\n\nThis requires a temporary data transfer. </user pjsk update_data:1325347278805929994>",
                )
                return await ctx.reply(embed=embed)

            await ctx.reply("ok")

            img = await self.generate_progress(
                data=data, user=ctx.author, difficulty=difficulty, private=False
            )
            embed = embeds.embed(title="Your Progress", color=discord.Color.dark_gold())
            file = discord.File(img, "image.png")
            embed.set_image(url="attachment://image.png")
            await ctx.reply(embed=embed, file=file)
        except Exception as e:
            self.bot.traceback(e)

    @commands.command(name="dev_b30")
    @is_owner()
    async def dev_b30(
        self,
        ctx: commands.Context,
        user_id: typing.Union[discord.User, str],
        region: str,
    ):
        try:
            if region not in ["en", "jp", "tw", "kr", "cn", "all"]:
                return await ctx.reply(
                    await translations.other_context_translate(
                        locale_str(
                            "errors.unsupported_region",
                            replacements={"{region}": region.upper()},
                        ),
                        ctx.message,
                        "en-US",
                        ctx.bot,
                    )
                )
            if isinstance(user_id, discord.User):
                pjsk_id = await self.bot.user_data.discord.get_pjsk_id(
                    user_id.id, region="en"
                )
                pjsk_id_jp = await self.bot.user_data.discord.get_pjsk_id(
                    user_id.id, region="jp"
                )
            else:
                pjsk_id = user_id

            if region != "all":
                api = methods.Tools.get_api(region)
                data = api.attempt_get_user_data(pjsk_id)
            elif region == "all":
                data = {}
                for api, region in [(api, api.app_region) for api in methods.all_apis]:
                    pjsk_id = await self.bot.user_data.discord.get_pjsk_id(
                        ctx.author.id, region
                    )
                    if not pjsk_id:
                        continue
                    acc_data = api.attempt_get_user_data(pjsk_id)
                    if not acc_data:
                        continue
                    data[region] = acc_data
                if not data:
                    embed = embeds.error_embed(
                        "I don't have access to **any** of your account data.\n\nThis requires a temporary data transfer. </user pjsk update_data:1325347278805929994>"
                    )
                    return await ctx.reply(embed=embed)

            if not data:
                embed = embeds.error_embed(
                    "I don't have access to your account data.\n\nThis requires a temporary data transfer. </user pjsk update_data:1325347278805929994>"
                )
                return await ctx.reply(embed=embed)

            await ctx.reply("ok")

            img = await self.generate_b30(
                data=data, user=ctx.author, region=region, private=False
            )
            embed = embeds.embed(title="Your b30", color=discord.Color.dark_gold())
            file = discord.File(img, "image.png")
            embed.set_image(url="attachment://image.png")
            await ctx.reply(embed=embed, file=file)
        except Exception as e:
            self.bot.traceback(e)

    @app_commands.command(
        auto_locale_strings=False,
        name=locale_str("b30", key="b30.name", file="commands"),
        description=locale_str("b30.desc", file="commands"),
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.autocomplete(
        region=autocompletes.autocompletes.pjsk_region(
            ["en", "jp", "tw", "kr", "cn", "all"]
        ),
        filter=autocompletes.autocompletes.custom_values(
            {"AP Only": "ap", "FC Only": "fc"}
        ),
        count=autocompletes.autocompletes.range(1, 50),
    )
    @app_commands.describe(
        region=locale_str("general.region"),
        private=locale_str("general.pjsk_private"),
        filter=locale_str("b30.describes.filter", file="commands"),
        count=locale_str("b30.describes.count", file="commands"),
    )
    async def user_b30(
        self,
        interaction: discord.Interaction,
        region: str = "all",
        private: bool = False,
        filter: str = None,
        count: int = 30,
    ):
        filter = filter.lower().strip() if filter else filter
        region = region.lower().strip()
        if region not in ["en", "jp", "tw", "kr", "cn", "all"]:
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
        if filter not in ["ap", "fc", None]:
            return await interaction.response.send_message(
                embed=embeds.error_embed("Unsupported filter."), ephemeral=True
            )
        if filter == "ap":
            ap_only = True
            fc_only = False
        elif filter == "fc":
            fc_only = True
            ap_only = False
        else:
            fc_only = False
            ap_only = False

        sub_level = await self.bot.subscribed(interaction.user)
        current_time = time.time()
        if sub_level < 3:
            cooldown_end = (
                self.cooldown_b30.get(interaction.user.id, 0) + 90
            )  # 1 minute
            if cooldown_end > current_time:
                embed = embeds.error_embed(
                    (
                        f"You recently ran b30. Try again <t:{int(cooldown_end)}:R>.\n"
                        f"-# 90 second cooldown. Subscribe (monthly) to shorten the cooldown to 20 seconds. See </donate:1326321351417528442>"
                    )
                )
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )
        else:
            cooldown_end = (
                self.cooldown_b30.get(interaction.user.id, 0) + 20
            )  # 20 seconds
            if cooldown_end > current_time:
                embed = embeds.error_embed(
                    f"You recently ran b30 already. Try again <t:{int(cooldown_end)}:R>."
                )
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )
        if count != 30:
            if sub_level < 2:
                embed = embeds.error_embed(
                    (
                        f"Changing the song count is a premium-only feature.\n"
                        f"-# Donate to use. See </donate:1326321351417528442>"
                    )
                )
                return await interaction.response.send_message(embed=embed)
            if count > 50 or count < 1:
                embed = embeds.error_embed(
                    (f"Invalid song count. Please choose from 1-50.")
                )
                return await interaction.response.send_message(embed=embed)
        old_cooldown = self.cooldown_b30.get(interaction.user.id, 0)
        self.cooldown_b30[interaction.user.id] = time.time()

        try:
            await interaction.response.defer(thinking=True)

            if region != "all":
                pjsk_id = await self.bot.user_data.discord.get_pjsk_id(
                    interaction.user.id, region
                )
                if not pjsk_id:
                    self.cooldown_b30[interaction.user.id] = old_cooldown
                    return await interaction.followup.send(
                        embed=embeds.error_embed(
                            f"You are not linked to a PJSK {region.upper()} account."
                        ).set_footer(text="Your cooldown was reset.")
                    )
                api = methods.Tools.get_api(region)
                data = api.attempt_get_user_data(pjsk_id)
                if not data:
                    self.cooldown_b30[interaction.user.id] = old_cooldown
                    embed = embeds.error_embed(
                        f"I don't have access to your {region.upper()} account data.\n\nThis requires a temporary data transfer. </user pjsk update_data:1325347278805929994>"
                    ).set_footer(text="Your cooldown was reset.")
                    return await interaction.followup.send(embed=embed)
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
                    self.cooldown_b30[interaction.user.id] = old_cooldown
                    embed = embeds.error_embed(
                        description="I don't have access to **any** of your account data.\n\nThis requires a temporary data transfer. </user pjsk update_data:1325347278805929994>"
                    ).set_footer(text="Your cooldown was reset.")
                    return await interaction.followup.send(embed=embed)

            await interaction.followup.send(
                embed=embeds.embed(
                    "Please wait while we generate your image...\nThis can take a while!"
                )
            )

            img = await self.generate_b30(
                data=data,
                user=interaction.user,
                region=region,
                private=private,
                fc_only=fc_only,
                ap_only=ap_only,
                song_count=count,
            )
            filtered = " - FCs Only" if fc_only else " - APs Only" if ap_only else ""
            desc = f"""**Best {count} Chart{'s' if count != 1 else ''} - Rating Info**\n-# Constants are more specific difficulties, eg. `31` -> `31.4`. These are community rated.\n1. Constants exist for Expert, Master, and Append. For Hard, Normal, and Easy, it'll default to `xx.0`\n2. Constants will default to `xx.0` if not rated.\n3. FC will take `-1` off of the constant. AP to get the full constant rating."""
            embed = embeds.embed(
                title=f"Your B{count}" + filtered,
                description=desc,
                color=discord.Color.dark_gold(),
            )
            file = discord.File(img, "image.png")
            embed.set_image(url="attachment://image.png")
            await interaction.edit_original_response(embed=embed, attachments=[file])
        except:
            self.cooldown_b30[interaction.user.id] = old_cooldown
            raise

    @app_commands.command(
        auto_locale_strings=False,
        name=locale_str("progress", key="progress.name", file="commands"),
        description=locale_str("progress.desc", file="commands"),
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.autocomplete(
        region=autocompletes.autocompletes.pjsk_region(
            ["en", "jp", "tw", "kr", "cn", "all"]
        ),
        difficulty=autocompletes.autocompletes.pjsk_difficulties,
    )
    @app_commands.describe(
        region=locale_str("general.region"),
        private=locale_str("general.pjsk_private"),
        difficulty=locale_str("general.difficulty_default_master"),
    )
    async def user_progress(
        self,
        interaction: discord.Interaction,
        difficulty: str = "default",
        region: str = "default",
        private: bool = False,
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
        if (difficulty == "default") or (region == "default"):
            settings = await self.bot.user_data.discord.get_settings(
                interaction.user.id
            )
            if difficulty == "default":
                difficulty = settings["default_difficulty"]
            if region == "default":
                region = settings["default_region"]
        odiff = difficulty
        difficulty = converters.DiffFromPJSK(difficulty)
        if not difficulty:
            embed = embeds.error_embed(
                locale_str(
                    "errors.unsupported_difficulty",
                    replacements={"{difficulty}": odiff},
                )
            )
            await interaction.response.send_message(embed=embed)
            return

        sub_level = await self.bot.subscribed(interaction.user)
        current_time = time.time()
        if sub_level < 3:
            cooldown_end = (
                self.cooldown_progress.get(interaction.user.id, 0) + 90
            )  # 1 minute
            if cooldown_end > current_time:
                embed = embeds.error_embed(
                    (
                        f"You recently ran progress. Try again <t:{int(cooldown_end)}:R>.\n"
                        f"-# 90 second cooldown. Subscribe (monthly) to shorten the cooldown to 20 seconds. See </donate:1326321351417528442>"
                    )
                )
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )
        else:
            cooldown_end = (
                self.cooldown_progress.get(interaction.user.id, 0) + 20
            )  # 20 seconds
            if cooldown_end > current_time:
                embed = embeds.error_embed(
                    f"You recently ran progress already. Try again <t:{int(cooldown_end)}:R>."
                )
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )
        old_cooldown = self.cooldown_progress.get(interaction.user.id, 0)
        self.cooldown_progress[interaction.user.id] = time.time()

        try:
            await interaction.response.defer(thinking=True)
            if region != "all":
                pjsk_id = await self.bot.user_data.discord.get_pjsk_id(
                    interaction.user.id, region
                )
                if not pjsk_id:
                    self.cooldown_progress[interaction.user.id] = old_cooldown
                    return await interaction.followup.send(
                        embed=embeds.error_embed(
                            f"You are not linked to a PJSK {region.upper()} account.",
                        ).set_footer(text="Your cooldown was reset.")
                    )
                api = methods.Tools.get_api(region)
                data = api.attempt_get_user_data(pjsk_id)
                if not data:
                    self.cooldown_progress[interaction.user.id] = old_cooldown
                    embed = embeds.error_embed(
                        f"I don't have access to your {region.upper()} account data.\n\nThis requires a temporary data transfer. </user pjsk update_data:1325347278805929994>"
                    ).set_footer(text="Your cooldown was reset.")
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
                    self.cooldown_progress[interaction.user.id] = old_cooldown
                    embed = embeds.error_embed(
                        "I don't have access to **any** of your account data.\n\nThis requires a temporary data transfer. </user pjsk update_data:1325347278805929994>",
                    ).set_footer(text="Your cooldown was reset.")
                    return await interaction.followup.send(embed=embed)

            await interaction.followup.send(
                embed=embeds.embed("Please wait while we generate your image...")
            )

            img = await self.generate_progress(
                data, difficulty, private, interaction.user
            )
            embed = embeds.embed(
                title="Your PJSK Progress", color=discord.Color.dark_gold()
            )
            file = discord.File(img, "image.png")
            embed.set_image(url="attachment://image.png")
            embed.set_footer(
                text="Difficulties use JP rerates! Limited time songs included."
            )
            await interaction.edit_original_response(embed=embed, attachments=[file])
        except:
            self.cooldown_progress[interaction.user.id] = old_cooldown
            raise


async def setup(bot: DiscordBot):
    await bot.add_cog(DataAnalysis(bot))
