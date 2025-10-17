import discord
from discord.ext import commands, tasks
from discord import app_commands

from discord.app_commands import locale_str
from COGS.discord_translations import translations

from main import DiscordBot

import time, csv, math, asyncio
from collections import defaultdict
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

from COGS.progress_generate import (
    generate_progress,
    DifficultyCategory,
    generate_general_progress,
    StrDifficultyCategory,
)


class DataAnalysis(commands.Cog):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

        self.cooldown_progress = {}
        self.cooldown_summary = {}
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
        for uid, last_ran in list(self.cooldown_summary.items()):
            if time.time() - last_ran > 120:  # 2 minutes
                self.cooldown_summary.pop(uid, None)

    async def generate_summary(
        self, user_data: dict, region: str, now: int, private: bool, user: discord.User
    ) -> BytesIO:
        difficulty_counts = {}

        def _make():
            for music_id, ds in self.bot.pjsk.difficulties.items():
                for difficulty in ds.keys():
                    check_regions = [region]
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

                    difficulty_counts[difficulty] = (
                        difficulty_counts.get(difficulty, 0) + 1
                    )

            user_data["userMusicDifficultyClearCount"]
            # [{'musicDifficultyType': 'easy', 'liveClear': 33, 'fullCombo': 22, 'allPerfect': 17}]
            # 0 easy 1 normal 2 hard 3 expert 4 master 5 append

            data = [
                StrDifficultyCategory(
                    difficulty="append",
                    ap_count=user_data["userMusicDifficultyClearCount"][5][
                        "allPerfect"
                    ],
                    fc_count=user_data["userMusicDifficultyClearCount"][5]["fullCombo"],
                    clear_count=user_data["userMusicDifficultyClearCount"][5][
                        "liveClear"
                    ],
                    all_count=difficulty_counts["append"],
                ),
                StrDifficultyCategory(
                    difficulty="master",
                    ap_count=user_data["userMusicDifficultyClearCount"][4][
                        "allPerfect"
                    ],
                    fc_count=user_data["userMusicDifficultyClearCount"][4]["fullCombo"],
                    clear_count=user_data["userMusicDifficultyClearCount"][4][
                        "liveClear"
                    ],
                    all_count=difficulty_counts["master"],
                ),
                StrDifficultyCategory(
                    difficulty="expert",
                    ap_count=user_data["userMusicDifficultyClearCount"][3][
                        "allPerfect"
                    ],
                    fc_count=user_data["userMusicDifficultyClearCount"][3]["fullCombo"],
                    clear_count=user_data["userMusicDifficultyClearCount"][3][
                        "liveClear"
                    ],
                    all_count=difficulty_counts["expert"],
                ),
                StrDifficultyCategory(
                    difficulty="hard",
                    ap_count=user_data["userMusicDifficultyClearCount"][2][
                        "allPerfect"
                    ],
                    fc_count=user_data["userMusicDifficultyClearCount"][2]["fullCombo"],
                    clear_count=user_data["userMusicDifficultyClearCount"][2][
                        "liveClear"
                    ],
                    all_count=difficulty_counts["hard"],
                ),
                StrDifficultyCategory(
                    difficulty="normal",
                    ap_count=user_data["userMusicDifficultyClearCount"][1][
                        "allPerfect"
                    ],
                    fc_count=user_data["userMusicDifficultyClearCount"][1]["fullCombo"],
                    clear_count=user_data["userMusicDifficultyClearCount"][1][
                        "liveClear"
                    ],
                    all_count=difficulty_counts["normal"],
                ),
                StrDifficultyCategory(
                    difficulty="easy",
                    ap_count=user_data["userMusicDifficultyClearCount"][0][
                        "allPerfect"
                    ],
                    fc_count=user_data["userMusicDifficultyClearCount"][0]["fullCombo"],
                    clear_count=user_data["userMusicDifficultyClearCount"][0][
                        "liveClear"
                    ],
                    all_count=difficulty_counts["easy"],
                ),
            ]

            img = generate_general_progress(data)

            img = Image.open(img)

            SCALE = 2
            new_height = img.height + (100 * SCALE)
            new_img = Image.new(
                "RGBA", (img.width, new_height), (50, 50, 50, 255)
            )  # Dark gray bar
            new_img.paste(img, (0, (100 * SCALE)))

            draw = ImageDraw.Draw(new_img)
            font = ImageFont.truetype("DATA/data/ASSETS/rodinntlg_eb.otf", 30 * SCALE)
            font_2 = ImageFont.truetype("DATA/data/ASSETS/rodinntlg_m.otf", 30 * SCALE)
            font_3 = ImageFont.truetype("DATA/data/ASSETS/rodinntlg_m.otf", 20 * SCALE)

            new_height = img.height + 100 * SCALE  # Adjusting for one region
            new_img = Image.new(
                "RGBA", (img.width, new_height), (50, 50, 50, 255)
            )  # Dark gray bar
            new_img.paste(img, (0, 100 * SCALE))

            timestamp = now
            data_date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
                "%Y-%m-%d"
            )
            data_time = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
                "%H:%M"
            )

            draw = ImageDraw.Draw(new_img)
            font = ImageFont.truetype("DATA/data/ASSETS/rodinntlg_eb.otf", 30 * SCALE)
            font_2 = ImageFont.truetype("DATA/data/ASSETS/rodinntlg_m.otf", 30 * SCALE)
            font_3 = ImageFont.truetype("DATA/data/ASSETS/rodinntlg_m.otf", 20 * SCALE)

            # Draw user information
            draw.text(
                (10, 15 * SCALE),
                (f"{user_data['user']['name']}" if not private else f"{user.name}"),
                font=font,
                fill="white",
            )
            draw.text(
                (10, 60 * SCALE),
                (
                    f"{region.upper()} ID: {user_data['user']['userId']}"
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
            output = BytesIO()
            new_img.save(output, format="PNG")
            output.seek(0)
            return output

        output = await to_process_with_timeout(_make)

        return output

    async def generate_progress(
        self, data: dict, difficulty: str, private: bool, user: discord.User
    ) -> BytesIO:
        def _make():
            RESULT_PRIORITY = {
                "full_perfect": 4,
                "full_combo": 3,
                "clear": 2,
                "not_clear": 1,
                None: 0,
            }

            diffs = defaultdict(int)
            current = {}
            added = set()

            check_regions = set(data.keys())
            pjsk_diffs = self.bot.pjsk.difficulties

            # --- First pass: all available difficulties ---
            for music_id, ds in pjsk_diffs.items():
                diff_data = ds.get(difficulty)
                if not diff_data:
                    continue

                leak, song_regions = methods.Tools.get_music_regions(music_id)
                if leak:
                    continue
                if not (check_regions & set(song_regions)):
                    continue

                if difficulty == "append":
                    _, append_regions = methods.Tools.get_music_append_regions(music_id)
                    if not (check_regions & set(append_regions)):
                        continue

                playlevel = diff_data["playLevel"]
                if isinstance(playlevel, list):
                    playlevel = playlevel[1]

                key = (music_id, difficulty)
                if key not in added:
                    added.add(key)
                    diffs[playlevel] += 1

            # --- Second pass: player progress ---
            for region, region_data in data.items():
                # detect new data structure (flat list under userMusicResults)
                if "userMusicResults" in region_data:
                    results_list = region_data["userMusicResults"]
                    for result in results_list:
                        if result["musicDifficultyType"] != difficulty:
                            continue

                        music_id = result["musicId"]
                        key = (music_id, difficulty)
                        diff_entry = pjsk_diffs.get(music_id, {}).get(difficulty)
                        if not diff_entry:
                            continue

                        playlevel = diff_entry["playLevel"]
                        if isinstance(playlevel, list):
                            playlevel = playlevel[1]

                        if key not in added:
                            added.add(key)
                            diffs[playlevel] += 1

                        best_result = current.get(key, [playlevel, None])[1]
                        res = result["playResult"]

                        if (
                            best_result is None
                            or RESULT_PRIORITY[res] > RESULT_PRIORITY[best_result]
                        ):
                            best_result = res

                        current[key] = [playlevel, best_result]

                # old data structure (nested userMusics)
                elif "userMusics" in region_data:
                    for song_data in region_data["userMusics"]:
                        for s_info in song_data.get("userMusicDifficultyStatuses", []):
                            if s_info["musicDifficulty"] != difficulty:
                                continue

                            music_id = s_info["musicId"]
                            key = (music_id, difficulty)
                            diff_entry = pjsk_diffs.get(music_id, {}).get(difficulty)
                            if not diff_entry:
                                continue

                            playlevel = diff_entry["playLevel"]
                            if isinstance(playlevel, list):
                                playlevel = playlevel[1]

                            if key not in added:
                                added.add(key)
                                diffs[playlevel] += 1

                            best_result = current.get(key, [playlevel, None])[1]
                            for result in s_info["userMusicResults"]:
                                res = result["playResult"]
                                if (
                                    best_result is None
                                    or RESULT_PRIORITY[res]
                                    > RESULT_PRIORITY[best_result]
                                ):
                                    best_result = res

                            current[key] = [playlevel, best_result]

            # --- Third pass: aggregate results ---
            difficulties = {
                pl: {"all": count, "ap": 0, "fc": 0, "clear": 0}
                for pl, count in diffs.items()
            }

            for (music_id, diff), (pl, res) in current.items():
                if not res or res == "not_clear":
                    continue
                entry = difficulties[pl]
                entry["clear"] += 1
                if res in ("full_combo", "full_perfect"):
                    entry["fc"] += 1
                if res == "full_perfect":
                    entry["ap"] += 1

            final_results = [
                DifficultyCategory(pl, v["ap"], v["fc"], v["clear"], v["all"])
                for pl, v in sorted(difficulties.items())
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

        # Local helper that uses horizontal lines (fast) to paint an RGBA gradient
        def _create_gradient_rgba(start_color, end_color, width, height):
            grad = Image.new("RGBA", (width, height))
            draw_grad = ImageDraw.Draw(grad)
            # support both RGB and RGBA tuples
            sc = list(start_color) + [255] * (4 - len(start_color))
            ec = list(end_color) + [255] * (4 - len(end_color))
            r0, g0, b0, a0 = sc[:4]
            r1, g1, b1, a1 = ec[:4]
            h = height or 1
            for y in range(h):
                t = y / h
                r = int(r0 + (r1 - r0) * t)
                g = int(g0 + (g1 - g0) * t)
                b = int(b0 + (b1 - b0) * t)
                a = int(a0 + (a1 - a0) * t)
                # draw a horizontal line with RGBA fill
                draw_grad.line([(0, y), (width, y)], fill=(r, g, b, a))
            return grad

        # text_wrap preserved but micro-optimized: local alias for multiline_textbbox
        def text_wrap(text, font, drawing: ImageDraw.ImageDraw, max_width, max_height):
            def textsize_from_bbox(bbox):
                return (bbox[2] - bbox[0], bbox[3] - bbox[1])

            lines = [[]]
            words = text.split(" ")
            mttb = drawing.multiline_textbbox

            for i, word in enumerate(words):
                test_line = lines[-1] + ([word] if i == len(words) - 1 else [word, " "])
                test_text = "\n".join(
                    ["".join(line) for line in lines[:-1]] + ["".join(test_line)]
                )
                w, h = textsize_from_bbox(mttb((0, 0), test_text, font=font))

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
                        mttb(
                            (0, 0),
                            "\n".join(["".join(line) for line in lines]),
                            font=font,
                        )
                    )
                    if w > max_width:
                        # Word still doesn't fit; split by character
                        lines.pop()
                        current_line = []
                        for char in word:
                            current_line.append(char)
                            w, h = textsize_from_bbox(
                                mttb(
                                    (0, 0),
                                    "\n".join(["".join(current_line)]),
                                    font=font,
                                )
                            )
                            if w > max_width:
                                lines.append(current_line[:-1])
                                current_line = [current_line[-1]]
                                w, h = textsize_from_bbox(
                                    mttb(
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
            while True:
                bbox = mttb(
                    (0, 0),
                    "\n".join(["".join(line).rstrip() for line in lines]),
                    font=font,
                )
                if textsize_from_bbox(bbox)[1] <= max_height:
                    break
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
                    textsize_from_bbox(mttb((0, 0), last_line + "...", font=font))[0]
                    > max_width
                ):
                    if len(last_line) > 1:
                        last_line = last_line[:-1]
                    else:
                        last_line = "..."
                        break
                lines[-1] = list(last_line + "...")

            return "\n".join(["".join(line).rstrip() for line in lines])

        # Grid determination kept unchanged
        def determine_grid(song_count: int):
            column_options = [3, 4, 5, 2]
            best_fit = None
            min_gaps = float("inf")

            for columns in column_options:
                rows = math.ceil(song_count / columns)
                gaps = (rows * columns) - song_count

                if gaps == 0:  # Perfect fit
                    return rows, columns

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

        # Create base image
        image = Image.new("RGBA", (WIDTH, HEIGHT), "#FFFFFF")
        draw = ImageDraw.Draw(image)

        # background kitty
        kitty_image = Image.open(KITTY_PATH).resize((WIDTH, HEIGHT), Image.LANCZOS)
        image.paste(kitty_image, (0, 0))

        # Top bar and text
        header_font = ImageFont.truetype(FONT_PATH, int(48 * SCALE))
        watermark_font = ImageFont.truetype(FONT_PATH, int(30 * SCALE))
        filtered = " - FCs Only" if fc_only else " - APs Only" if ap_only else ""
        draw.rectangle(
            [(0, 0), (WIDTH, HEADER_HEIGHT)], fill="#b4ccfa", outline="#00194a"
        )
        draw.text(
            (10, int(14 * SCALE)),
            f"Your best {song_count} chart{'s' if song_count != 1 else ''}" + filtered,
            fill="black",
            font=header_font,
        )
        draw.text(
            (10, int(65 * SCALE)),
            "Generated by Sbotga",
            fill="black",
            font=watermark_font,
        )

        GUTTER_WIDTH = int(60 * SCALE)
        GUTTER_HEIGHT = int(70 * SCALE)
        CARD_WIDTH = int(
            (WIDTH - (GUTTER_WIDTH * (amount_columns + 1))) / amount_columns
        )
        CARD_HEIGHT = int(
            (HEIGHT - HEADER_HEIGHT - (GUTTER_HEIGHT * (amount_rows + 1))) / amount_rows
        )
        JACKET_SIZE = (CARD_HEIGHT - int(20 * SCALE), CARD_HEIGHT - int(20 * SCALE))

        difficulty_colors = {
            "append": "DATA/data/ASSETS/append_color.jpg",
            "hard": "DATA/data/ASSETS/hard_color.jpg",
            "normal": "DATA/data/ASSETS/normal_color.jpg",
            "easy": "DATA/data/ASSETS/easy_color.jpg",
            "master": "DATA/data/ASSETS/master_color.jpg",
            "expert": "DATA/data/ASSETS/expert_color.jpg",
        }
        indicator_images = {
            "append_ap": "DATA/data/ASSETS/append_ap.png",
            "append_fc": "DATA/data/ASSETS/append_fc.png",
            "normal_ap": "DATA/data/ASSETS/normal_ap.png",
            "normal_fc": "DATA/data/ASSETS/normal_fc.png",
        }

        # Jackets / paths
        jackets = [song["path"] for song in songs]

        # Preload indicators once (resized)
        indicators = {
            key: Image.open(path).resize((72, 72), Image.LANCZOS).convert("RGBA")
            for key, path in indicator_images.items()
        }

        # Preload difficulty images sized to CARD_WIDTH x CARD_HEIGHT
        difficulty_images = {
            key: Image.open(path)
            .resize((CARD_WIDTH, CARD_HEIGHT), Image.LANCZOS)
            .convert("RGBA")
            for key, path in difficulty_colors.items()
        }

        # Resize jacket images once (or None)
        jacket_images = [
            Image.open(path).resize(JACKET_SIZE, Image.LANCZOS) if path else None
            for path in jackets
        ]

        # Precreate some fonts used inside loop with scale-aware sizes
        difficulty_font_small = ImageFont.truetype(FONT_PATH, int(22 * SCALE))
        difficulty_font_label = ImageFont.truetype(FONT_PATH, int(20 * SCALE))
        song_title_font = ImageFont.truetype(FONT_PATH, int(35 * SCALE))
        big_header_font = header_font  # alias for ranking draw

        total_difficulty = 0.0

        # iterate once (idx used for jacket_images indexing)
        for idx, song in enumerate(songs):
            gridX = idx % amount_columns
            gridY = idx // amount_columns

            xPos = gridX * CARD_WIDTH + (GUTTER_WIDTH * (gridX + 1))
            yPos = HEADER_HEIGHT + (gridY * CARD_HEIGHT) + (GUTTER_HEIGHT * (gridY + 1))

            difficulty_number = song["constant"]
            badge_type = song["difficulty"]
            ap_fc = song["ap_or_fc"].upper()

            # Difficulty background (use preloaded image)
            difficulty_img = difficulty_images[badge_type]
            # Slightly larger copy for stroke/background to preserve original visual
            difficulty_img_resized = difficulty_img.resize(
                (CARD_WIDTH + 12 * SCALE, CARD_HEIGHT + 12 * SCALE), Image.LANCZOS
            )
            image.paste(
                difficulty_img_resized, (xPos - int(6 * SCALE), yPos - int(6 * SCALE))
            )

            # sample safe pixel positions
            w_s, h_s = difficulty_img.size
            sample_x = min(5, max(0, w_s - 1))
            sample_y = min(5, max(0, h_s - 1))
            tl_color = difficulty_img.getpixel((sample_x, sample_y))
            br_color = difficulty_img.getpixel(
                (max(0, CARD_WIDTH - 5), max(0, CARD_HEIGHT - 5))
            )

            # Create gradient stroke around card (fast)
            STROKE_SIZE = int(20 * SCALE)
            grad_w = CARD_WIDTH + STROKE_SIZE
            grad_h = CARD_HEIGHT + STROKE_SIZE
            gradient = _create_gradient_rgba(tl_color, br_color, grad_w, grad_h)

            # rounded mask for stroke
            mask = Image.new("L", (grad_w, grad_h), 0)
            draw_mask = ImageDraw.Draw(mask)
            draw_mask.rounded_rectangle(
                [(0, 0), (grad_w, grad_h)], radius=int(12 * SCALE), fill=255
            )

            image.paste(gradient, (xPos - int(9 * SCALE), yPos - int(9 * SCALE)), mask)

            # base card
            draw.rounded_rectangle(
                [(xPos, yPos), (xPos + CARD_WIDTH, yPos + CARD_HEIGHT)],
                radius=int(8 * SCALE),
                fill="white",
            )

            # jacket placement
            jacket_x = xPos + int(20 * SCALE)
            jacket_y = yPos + (CARD_HEIGHT - JACKET_SIZE[1]) // 2
            if jacket_images[idx]:
                image.paste(jacket_images[idx], (jacket_x, jacket_y))

            # difficulty badge (top-left)
            difficulty_badge_x = xPos - int(10 * SCALE)
            difficulty_badge_y = yPos - int(30 * SCALE)
            difficulty_badge_width = int(120 * SCALE)
            difficulty_badge_height = int(50 * SCALE)
            badge_grad = _create_gradient_rgba(
                tl_color, br_color, difficulty_badge_width, difficulty_badge_height
            )
            badge_mask = Image.new(
                "L", (difficulty_badge_width, difficulty_badge_height), 0
            )
            dm = ImageDraw.Draw(badge_mask)
            dm.rounded_rectangle(
                [(0, 0), (difficulty_badge_width, difficulty_badge_height)],
                radius=int(12 * SCALE),
                fill=255,
            )
            image.paste(
                badge_grad, (difficulty_badge_x, difficulty_badge_y), badge_mask
            )

            # stroke around badge
            draw.rounded_rectangle(
                [
                    (difficulty_badge_x, difficulty_badge_y),
                    (
                        difficulty_badge_x + difficulty_badge_width,
                        difficulty_badge_y + difficulty_badge_height,
                    ),
                ],
                radius=int(12 * SCALE),
                outline="#222222",
                width=int(3 * SCALE),
            )

            # difficulty number text on badge
            difficulty_text = f"{math.ceil(difficulty_number * 10) / 10:.1f}"
            tb = draw.textbbox((0, 0), difficulty_text, font=difficulty_font_small)
            text_width = tb[2] - tb[0]
            text_height = tb[3] - tb[1]
            text_x = difficulty_badge_x + (difficulty_badge_width - text_width) / 2
            text_y = difficulty_badge_y + (difficulty_badge_height - text_height) / 2
            draw.text(
                (text_x, text_y),
                difficulty_text,
                fill="white",
                font=difficulty_font_small,
            )

            # Title wrapping & drawing
            song_title = song["name"]
            max_length_px = CARD_WIDTH - JACKET_SIZE[0] - int(28 * SCALE)
            wrapped_title = text_wrap(
                song_title,
                song_title_font,
                draw,
                max_length_px,
                CARD_HEIGHT - int(50 * SCALE),
            )

            # difficulty label below title
            difficulty_label = badge_type.upper()
            tb_label = draw.textbbox(
                (0, 0), difficulty_label, font=difficulty_font_label
            )
            difficulty_height = tb_label[3] - tb_label[1]

            tb_title = draw.textbbox((0, 0), wrapped_title, font=song_title_font)
            title_height = tb_title[3] - tb_title[1]

            total_text_height = title_height + difficulty_height + int(10 * SCALE)
            title_y_position = yPos + (CARD_HEIGHT - total_text_height) // 2
            title_x = xPos + JACKET_SIZE[0] + int(20 * SCALE)

            draw.text(
                (title_x + int(10 * SCALE), title_y_position),
                wrapped_title,
                fill="black",
                font=song_title_font,
            )
            difficulty_y = title_y_position + title_height + int(10 * SCALE)
            draw.text(
                (title_x + int(10 * SCALE), difficulty_y),
                difficulty_label,
                fill="black",
                font=difficulty_font_label,
            )

            # accumulate difficulty for ranking
            total_difficulty += float(difficulty_number)

            # indicator icon bottom-right
            indicator_key = (
                f"{'normal' if badge_type != 'append' else 'append'}_{ap_fc.lower()}"
            )
            indicator = indicators[indicator_key]
            indicator_x = xPos + CARD_WIDTH - int(40 * SCALE)
            indicator_y = yPos + CARD_HEIGHT - int(40 * SCALE)
            image.paste(indicator, (indicator_x, indicator_y), indicator)

        # final ranking text
        overall_ranking = total_difficulty / (song_count or 1)
        ranking_text = f"Ranking: {overall_ranking:.2f}"
        ranking_bbox = draw.textbbox((0, 0), ranking_text, font=big_header_font)
        ranking_width = ranking_bbox[2] - ranking_bbox[0]
        draw.text(
            (WIDTH - ranking_width - int(10 * SCALE), int(24 * SCALE)),
            ranking_text,
            fill="black",
            font=big_header_font,
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
        """
        Builds a Best-30 image for the given user data.
        - Supports both old nested format (userMusics -> userMusicDifficultyStatuses -> userMusicResults)
        and the new flat per-region format (userMusicResults list with musicDifficultyType).
        - Preserves original selection logic (effective_level = playLevel + ap(+1) + append(+2)),
        AP preferred over FC when deduping, sliding threshold down until song_count satisfied.
        - Respects `private` to hide usernames/IDs.
        """

        from io import BytesIO
        from collections import defaultdict
        from PIL import Image, ImageDraw, ImageFont
        from datetime import datetime, timezone

        assert not (fc_only and ap_only)

        def _make(region: str):
            # helpers -----------------------------------------------------------------
            def _build_diff_map(diffs_list):
                """Build a map (musicId, musicDifficulty) -> base_playlevel (with rerate handling)."""
                m = {}
                for d in diffs_list:
                    key = (d.get("musicId"), d.get("musicDifficulty"))
                    pl = d.get("playLevel")
                    if isinstance(pl, list):
                        pl = pl[1]
                    m[key] = pl
                return m

            def _process_region_entries(region_key, region_data):
                """
                Return list of candidate tuples:
                (effective_level, music_id, difficulty, is_ap_flag)
                Handles both old nested userMusics -> userMusicDifficultyStatuses -> userMusicResults
                and new flat userMusicResults list (with musicDifficultyType).
                """
                candidates = []
                api = methods.Tools.get_api(region_key)
                diffs = api.get_master_data("musicDifficulties.json")
                diff_map = _build_diff_map(diffs)

                def maybe_append_candidate(music_id, difficulty, result_dict):
                    fc_flag = bool(result_dict.get("fullComboFlg"))
                    ap_flag = bool(result_dict.get("fullPerfectFlg"))

                    if not (fc_flag or ap_flag):
                        return

                    # Respect filters
                    if ap_flag and fc_only:
                        return
                    if ap_only and not ap_flag:
                        return

                    key = (music_id, difficulty)
                    base_level = diff_map.get(key)
                    if base_level is None:
                        return

                    eff = base_level
                    if ap_flag:
                        eff += 1
                    if difficulty == "append":
                        eff += 2

                    candidates.append((eff, music_id, difficulty, ap_flag))

                # New flat format
                if isinstance(region_data, dict) and "userMusicResults" in region_data:
                    for res in region_data.get("userMusicResults", ()):
                        difficulty = res.get("musicDifficultyType") or res.get(
                            "musicDifficulty"
                        )
                        if difficulty is None:
                            continue
                        maybe_append_candidate(res.get("musicId"), difficulty, res)

                # Old nested format
                elif isinstance(region_data, dict) and "userMusics" in region_data:
                    for entry in region_data.get("userMusics", ()):
                        music_id = entry.get("musicId")
                        for diff in entry.get("userMusicDifficultyStatuses", ()):
                            difficulty = diff.get("musicDifficulty")
                            for res in diff.get("userMusicResults", ()):
                                maybe_append_candidate(music_id, difficulty, res)

                return candidates

            # ---------------------------------------------------------------------
            # 1) Collect candidates (either for single region or across all regions)
            # ---------------------------------------------------------------------
            query_params = []
            if region == "all":
                for reg_key, reg_data in data.items():
                    if not isinstance(reg_data, dict):
                        continue
                    query_params.extend(_process_region_entries(reg_key, reg_data))
            else:
                # caller may pass whole data dict or a single-region object
                region_data = data
                if region in data and isinstance(data[region], dict):
                    region_data = data[region]
                query_params = _process_region_entries(region, region_data)

            if not query_params:
                # no candidates => return empty image bytes (or an empty BytesIO)
                return BytesIO()

            # ---------------------------------------------------------------------
            # 2) Sort candidates (level desc, prefer ap when tie)
            # ---------------------------------------------------------------------
            query_params.sort(key=lambda t: (t[0], t[3]), reverse=True)

            # Compute baseline highest_fc and adjust if top entry is append
            highest_fc = query_params[0][0]
            if query_params and query_params[0][2] == "append":
                highest_fc -= 2

            # ---------------------------------------------------------------------
            # 3) Threshold expansion efficiently (group by level)
            # ---------------------------------------------------------------------
            non_append_by_level = defaultdict(list)
            append_by_level = defaultdict(list)
            for eff, mid, diff_name, ap_flag in query_params:
                if diff_name == "append":
                    append_by_level[eff].append((eff, mid, diff_name, ap_flag))
                else:
                    non_append_by_level[eff].append((eff, mid, diff_name, ap_flag))

            sorted_non_append_levels = sorted(non_append_by_level.keys(), reverse=True)
            final_hf = highest_fc
            selected_non_append = []
            # Decrease final_hf until we get enough non-append entries or reach 0
            while final_hf >= 0:
                threshold = final_hf - 2
                selected_non_append = []
                for lvl in sorted_non_append_levels:
                    if lvl >= threshold:
                        selected_non_append.extend(non_append_by_level[lvl])
                    else:
                        break
                if len(selected_non_append) >= song_count or final_hf == 0:
                    break
                final_hf -= 1

            append_threshold = final_hf - 2
            selected_append = []
            for lvl, entries in append_by_level.items():
                if lvl >= append_threshold:
                    selected_append.extend(entries)

            # ---------------------------------------------------------------------
            # 4) Deduplicate preserving AP-over-FC preference
            # ---------------------------------------------------------------------
            chosen_map = {}

            def consider_entry(entry):
                eff, mid, diff_name, ap_flag = entry
                key = (mid, diff_name)
                existing = chosen_map.get(key)
                if existing is None:
                    chosen_map[key] = entry
                    return
                # prefer AP over FC (replace if new is AP and existing is FC)
                if not existing[3] and ap_flag:
                    chosen_map[key] = entry

            # Non-append first, then append (mimics original logic)
            for e in selected_non_append:
                consider_entry(e)
            for e in selected_append:
                consider_entry(e)

            # ---------------------------------------------------------------------
            # 5) Build songs list (call external helpers once per chosen entry)
            # ---------------------------------------------------------------------
            songs = []
            for eff, mid, diff_name, ap_flag in chosen_map.values():
                songs.append(
                    {
                        "music_id": mid,
                        "path": methods.Tools.get_music_jacket(mid),
                        "difficulty": diff_name,
                        "name": methods.Tools.get_music_name(mid),
                        "constant": self.bot.get_constant_sync(mid, diff_name, ap_flag),
                        "ap_or_fc": "ap" if ap_flag else "fc",
                    }
                )

            songs = sorted(songs, key=lambda s: s["constant"], reverse=True)[
                :song_count
            ]

            # ---------------------------------------------------------------------
            # 6) Build image with header area for region(s) and user info
            # ---------------------------------------------------------------------
            img = self.draw_b30(
                songs, fc_only=fc_only, ap_only=ap_only, song_count=song_count
            )
            img = Image.open(img)

            SCALE = 2
            if region == "all":
                num_regions = len(data)
                header_height = num_regions * 100 * SCALE
                new_height = img.height + header_height
                new_img = Image.new("RGBA", (img.width, new_height), (50, 50, 50, 255))
                new_img.paste(img, (0, header_height))
            else:
                num_regions = 1
                header_height = 100 * SCALE
                new_height = img.height + header_height
                new_img = Image.new("RGBA", (img.width, new_height), (50, 50, 50, 255))
                new_img.paste(img, (0, header_height))

            draw = ImageDraw.Draw(new_img)
            font_bold = ImageFont.truetype(
                "DATA/data/ASSETS/rodinntlg_eb.otf", 30 * SCALE
            )
            font_med = ImageFont.truetype(
                "DATA/data/ASSETS/rodinntlg_m.otf", 30 * SCALE
            )
            font_small = ImageFont.truetype(
                "DATA/data/ASSETS/rodinntlg_m.otf", 20 * SCALE
            )

            region_height_offset = 0

            def draw_user_info_for_region(region_key, region_obj):
                nonlocal region_height_offset
                # region_obj should contain 'now' and 'userGamedata' normally
                timestamp = region_obj.get("now", 0) / 1000
                data_date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
                    "%Y-%m-%d"
                )
                data_time = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
                    "%H:%M"
                )

                user_gamedata = (
                    region_obj.get("userGamedata", {})
                    if isinstance(region_obj, dict)
                    else {}
                )
                # When not private prefer the region's reported user name/id; otherwise show discord user
                name_to_display = (
                    user_gamedata.get("name")
                    if (not private and user_gamedata.get("name"))
                    else user.name
                )
                id_to_display = (
                    user_gamedata.get("userId")
                    if (not private and user_gamedata.get("userId"))
                    else f"{region_key.upper()} Account"
                )

                draw.text(
                    (10, region_height_offset + 15 * SCALE),
                    str(name_to_display),
                    font=font_bold,
                    fill="white",
                )
                draw.text(
                    (10, region_height_offset + 60 * SCALE),
                    f"{region_key.upper()} ID: {id_to_display}",
                    font=font_small,
                    fill="white",
                )
                draw.text(
                    (img.width - 215 * SCALE, region_height_offset + 15 * SCALE),
                    f"{data_date}",
                    font=font_med,
                    fill="white",
                )
                draw.text(
                    (img.width - 200 * SCALE, region_height_offset + 50 * SCALE),
                    f"{data_time} UTC",
                    font=font_med,
                    fill="white",
                )

                # separator
                line_y = region_height_offset + 100 * SCALE
                draw.line((0, line_y, img.width, line_y), fill="white", width=2)
                region_height_offset += 100 * SCALE

            if region == "all":
                # iterate regions in data order
                for reg_key, reg_obj in data.items():
                    draw_user_info_for_region(reg_key, reg_obj)
            else:
                # single region: caller may have passed whole data mapping or the single region object
                region_obj = (
                    data[region]
                    if (region in data and isinstance(data[region], dict))
                    else data
                )
                draw_user_info_for_region(region, region_obj)

            # ---------------------------------------------------------------------
            # 7) Return image BytesIO
            # ---------------------------------------------------------------------
            output = BytesIO()
            new_img.save(output, format="PNG")
            output.seek(0)
            return output

        # Run _make in executor/worker (original used to_process_with_timeout wrapper)
        output = await to_process_with_timeout(_make, region, timeout=80)
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
                        f"I don't have access to **any** of your account data.\n\nThis requires a temporary data transfer. {tools.command_mention(self.bot, 'user pjsk update_data')}"
                    )
                    return await ctx.reply(embed=embed)

            if not data:
                embed = embeds.error_embed(
                    f"I don't have access to your account data.\n\nThis requires a temporary data transfer. {tools.command_mention(self.bot, 'user pjsk update_data')}",
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
                        f"I don't have access to **any** of your account data.\n\nThis requires a temporary data transfer. {tools.command_mention(self.bot, 'user pjsk update_data')}"
                    )
                    return await ctx.reply(embed=embed)

            if not data:
                embed = embeds.error_embed(
                    f"I don't have access to your account data.\n\nThis requires a temporary data transfer. {tools.command_mention(self.bot, 'user pjsk update_data')}"
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
            )  # 1.5 minutes
            if cooldown_end > current_time:
                embed = embeds.error_embed(
                    (
                        f"You recently ran b30. Try again <t:{int(cooldown_end)}:R>.\n"
                        f"-# 90 second cooldown. Subscribe (monthly) to shorten the cooldown to 20 seconds. See {tools.command_mention(self.bot, 'donate')}"
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
        if count not in [10, 30, 50]:
            if sub_level < 2:
                embed = embeds.error_embed(
                    (
                        f"Changing the song count is a premium-only feature. (Free: `10, 30, 50`)\n"
                        f"-# Donate to use. See {tools.command_mention(self.bot, 'donate')}"
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
                        f"I don't have access to your {region.upper()} account data.\n\nThis requires a temporary data transfer. {tools.command_mention(self.bot, 'user pjsk update_data')}"
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
                        description=f"I don't have access to **any** of your account data.\n\nThis requires a temporary data transfer. {tools.command_mention(self.bot, 'user pjsk update_data')}"
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
            desc = f"""**Best {count} Chart{'s' if count != 1 else ''} - Rating Info**\n-# Constants are more specific difficulties, eg. `31` -> `31.4`. These are community rated.\n1. Constants exist for Expert, Master, and Append. For Hard, Normal, and Easy, it'll default to `xx.0`\n2. Constants will default to `xx.0` if not rated.\n3. FC will take `-1` off of the constant. AP to get the full constant rating.\n\n-# Constants are opinionated. Do not take seriously. Constants WILL be different for different people, they are community rated with a 'general' agreement.\b-# Constants are rated based on AP difficulty, not FC difficulty."""
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
            )  # 1.5 minutes
            if cooldown_end > current_time:
                embed = embeds.error_embed(
                    (
                        f"You recently ran progress. Try again <t:{int(cooldown_end)}:R>.\n"
                        f"-# 90 second cooldown. Subscribe (monthly) to shorten the cooldown to 20 seconds. See {tools.command_mention(self.bot, 'donate')}"
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
                        f"I don't have access to your {region.upper()} account data.\n\nThis requires a temporary data transfer. {tools.command_mention(self.bot, 'user pjsk update_data')}"
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
                        f"I don't have access to **any** of your account data.\n\nThis requires a temporary data transfer. {tools.command_mention(self.bot, 'user pjsk update_data')}",
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

    @app_commands.command(
        auto_locale_strings=False,
        name=locale_str("summary", key="summary.name", file="commands"),
        description=locale_str("summary.desc", file="commands"),
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.autocomplete(
        region=autocompletes.autocompletes.pjsk_region(["en", "jp", "tw", "kr", "cn"])
    )
    @app_commands.describe(
        region=locale_str("general.region"), private=locale_str("general.pjsk_private")
    )
    async def user_summary(
        self,
        interaction: discord.Interaction,
        region: str = "default",
        private: bool = False,
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
            settings = await self.bot.user_data.discord.get_settings(
                interaction.user.id
            )
            if region == "default":
                region = settings["default_region"]

        sub_level = await self.bot.subscribed(interaction.user)
        current_time = time.time()
        if sub_level < 3:
            cooldown_end = (
                self.cooldown_summary.get(interaction.user.id, 0) + 90
            )  # 1.5 minutes
            if cooldown_end > current_time:
                embed = embeds.error_embed(
                    (
                        f"You recently ran summary. Try again <t:{int(cooldown_end)}:R>.\n"
                        f"-# 90 second cooldown. Subscribe (monthly) to shorten the cooldown to 20 seconds. See {tools.command_mention(self.bot, 'donate')}"
                    )
                )
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )
        else:
            cooldown_end = (
                self.cooldown_summary.get(interaction.user.id, 0) + 20
            )  # 20 seconds
            if cooldown_end > current_time:
                embed = embeds.error_embed(
                    f"You recently ran summary already. Try again <t:{int(cooldown_end)}:R>."
                )
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )

        old_cooldown = self.cooldown_summary.get(interaction.user.id, 0)
        self.cooldown_summary[interaction.user.id] = time.time()

        try:
            await interaction.response.defer(thinking=True)
            pjsk_id = await self.bot.user_data.discord.get_pjsk_id(
                interaction.user.id, region
            )
            if not pjsk_id:
                self.cooldown_summary[interaction.user.id] = old_cooldown
                return await interaction.followup.send(
                    embed=embeds.error_embed(
                        f"You are not linked to a PJSK {region.upper()} account.",
                    ).set_footer(text="Your cooldown was reset.")
                )

            await interaction.followup.send(
                embed=embeds.embed("Please wait while we generate your image...")
            )

            api = methods.Tools.get_api(region)
            data = api.get_profile(pjsk_id, forced=True)

            img = await self.generate_summary(
                data, region, round(time.time()), private, interaction.user
            )
            embed = embeds.embed(
                title="Your PJSK Summary", color=discord.Color.dark_gold()
            )
            file = discord.File(img, "image.png")
            embed.set_image(url="attachment://image.png")
            embed.set_footer(text="Limited time songs included.")
            await interaction.edit_original_response(embed=embed, attachments=[file])
        except:
            self.cooldown_summary[interaction.user.id] = old_cooldown
            raise


async def setup(bot: DiscordBot):
    await bot.add_cog(DataAnalysis(bot))
