import twitchio
from twitchio.ext import commands

from main import TwitchBot

import base64
from io import BytesIO
from typing import Annotated

from easy_pil import Editor, load_image_async

from DATA.helpers.fuzzy_match import fuzzy_match_to_dict_key
from DATA.helpers import converters
from DATA.helpers.user_cache import getch_user_id


class DisplaysCog(commands.Cog):
    def __init__(self, bot: TwitchBot):
        self.bot = bot

    @commands.group()
    async def display(self, ctx: commands.Context):
        if len(ctx.message.content.strip().strip("󠀀").split(" ")) == 1:
            await ctx.reply(
                f'Setup a PJSK bot display! You can add displays as browser sources with your URL https://pjsk.econuker.xyz/user/{str((await getch_user_id(self.bot, ctx.channel.name)))}/bsrc/display_num (replace "display_num" with your display number, you can have infinite displays)'
            )

    @display.command()
    async def hide(
        self,
        ctx: commands.Context,
        num: Annotated[int, converters.Integer] = None,
    ):
        if ctx.message.content.split(" ")[0].lower().endswith("hide"):
            return
        if num == None:
            num = 1
        if not (
            await self.bot.run_checks(
                ctx, activated_check=True, game_check=False, permission_level=3
            )
        ):
            return
        await self.bot.command_ran(ctx)
        if not await self.bot.user_data.check_display(
            str((await getch_user_id(self.bot, ctx.channel.name))),
            num,
            self.bot.active_connections,
        ):
            await ctx.reply(f"Display {num} not active! Check your sources.")
            return
        await self.bot.send_image_update(
            self.bot, (await getch_user_id(self.bot, ctx.channel.name)), num, "hide"
        )
        await ctx.reply(f"Display {num} | Hidden")

    @display.command()
    async def show(
        self,
        ctx: commands.Context,
        num: Annotated[int, converters.Integer] = None,
    ):
        if ctx.message.content.split(" ")[0].lower().endswith("show"):
            return
        if num == None:
            num = 1
        if not (
            await self.bot.run_checks(
                ctx, activated_check=True, game_check=False, permission_level=3
            )
        ):
            return
        await self.bot.command_ran(ctx)
        if not await self.bot.user_data.check_display(
            str((await getch_user_id(self.bot, ctx.channel.name))),
            num,
            self.bot.active_connections,
        ):
            await ctx.reply(f"Display {num} not active! Check your sources.")
            return
        await self.bot.send_image_update(
            self.bot, (await getch_user_id(self.bot, ctx.channel.name)), num, "show"
        )
        await ctx.reply(f"Display {num} | Shown")

    @display.command()
    async def team(self, ctx: commands.Context, *, args):
        event = self.bot.pjsk.event_latest["en"]  # TODO: jp

        args = args.strip("󠀀").strip().split()
        team = ""
        num = 1
        if len(args) >= 2:
            if args[-1].isdigit():
                num = int(args.pop())  # Remove the last element (source number)
        team = " ".join(args)

        if type(num) != int:
            num = 1

        if ctx.message.content.split(" ")[0].lower().endswith("team"):
            return

        if not (
            await self.bot.run_checks(
                ctx, activated_check=True, game_check=False, permission_level=3
            )
        ):
            return

        await self.bot.command_ran(ctx)
        if not await self.bot.user_data.check_display(
            str((await getch_user_id(self.bot, ctx.channel.name))),
            num,
            self.bot.active_connections,
        ):
            await ctx.reply(f"Display {num} not active! Check your sources.")
            return

        if event["eventType"] != "cheerful_carnival":
            return await ctx.reply(
                f"Not a Cheerful Carnival! Cannot display a team image."
            )

        teams = {
            eventt["teamName"]: eventt["assetbundleName"]
            for eventt in self.bot.pjsk.cc_teams
            if eventt["eventId"] == event["id"]
        }
        team = fuzzy_match_to_dict_key(team, teams)
        if not team:
            return await ctx.reply(f"Team not found! See: {', '.join(teams.keys())}")

        team_num = teams[team]

        url = f"https://storage.sekai.best/sekai-en-assets/event/{event['assetbundleName']}/team_image_rip/{team_num}.webp"
        await self.bot.send_image_update(
            self.bot,
            (await getch_user_id(self.bot, ctx.channel.name)),
            num,
            "update",
            url,
        )
        await ctx.reply(f"Display {num} | " + event["name"] + f" Team {team}")

    @display.command(
        aliases=["jacket_ap", "jacket_clear", "jacket_fc", "jacket_fail"]
    )  # TODO: music, song alias, it's broken af, will overwrite the song command
    async def jacket(self, ctx: commands.Context, *, args):
        diffs = [
            "ex",
            "mas",
            "apd",
            "hard",
            "ez",
            "norm",
            "normal",
            "easy",
            "expert",
            "master",
            "append",
        ]
        if ctx.message.content.split(" ")[0].lower().endswith("jacket"):
            return
        if (
            ctx.message.content.split(" ")[0]
            .lower()
            .endswith(("jacket_ap", "jacket_fc", "jacket_clear", "jacket_fail"))
        ):
            return
        if ctx.message.content.split(" ")[1].lower() != "jacket":
            status = ctx.message.content.split(" ")[1].lower().split("_")[-1]
        else:
            status = False
        args = args.strip().strip("󠀀").split()
        song_name = ""
        diff = None
        num = 1
        if len(args) >= 2:
            if args[-1].isdigit():
                num = int(args.pop())  # Remove the last element (source number)
        if len(args) >= 2:
            if len(args) >= 1 and args[-1].lower() in diffs:
                diff = args.pop().lower()
        song_name = " ".join(args)

        if type(num) != int:
            num = 1

        # Use the SongConverter to get the song object
        song = converters.SongConverter(ctx, song_name)

        difficulty_map = {
            "ex": "expert",
            "mas": "master",
            "apd": "append",
            "hard": "hard",
            "ez": "easy",
            "norm": "normal",
            "normal": "normal",
            "easy": "easy",
            "expert": "expert",
            "master": "master",
            "append": "append",
        }

        diff = difficulty_map.get(diff, "easy")

        if not (
            await self.bot.run_checks(
                ctx, activated_check=True, game_check=False, permission_level=3
            )
        ):
            return
        await self.bot.command_ran(ctx)
        if not await self.bot.user_data.check_display(
            str((await getch_user_id(self.bot, ctx.channel.name))),
            num,
            self.bot.active_connections,
        ):
            await ctx.reply(f"Display {num} not active! Check your sources.")
            return
        if not song:
            await ctx.reply("Song not found.")
        else:
            if diff:

                async def fetch_and_edit_image(
                    song_jacket_url, diff="easy", status: bool | str = False
                ):
                    image_path = f"DATA/data/ASSETS/{diff}_color.jpg"
                    second_image_path = f'DATA/data/ASSETS/{"normal" if diff != "append" else "append"}_{status}.png'
                    size_percentage = 0.25
                    margin_percentage = 0.02

                    jacket_image = await load_image_async(song_jacket_url)
                    editor = Editor(image_path)

                    background_width, background_height = editor.image.size

                    jacket_editor = Editor(jacket_image)
                    jacket_width, jacket_height = jacket_editor.image.size
                    scaled_jacket = jacket_editor.resize(
                        (
                            background_width - 2 * int(0.05 * background_width),
                            background_height - 2 * int(0.05 * background_height),
                        )
                    )

                    x_position = (background_width - scaled_jacket.image.size[0]) // 2
                    y_position = (background_height - scaled_jacket.image.size[1]) // 2

                    editor.paste(scaled_jacket, (x_position, y_position))

                    if status:
                        second_image_editor = Editor(second_image_path)
                        second_image_width, second_image_height = (
                            second_image_editor.image.size
                        )

                        # Resize the second image to be 8% of the background image size
                        second_image_scaled_width = int(
                            background_width * size_percentage
                        )
                        second_image_scaled_height = int(
                            background_height * size_percentage
                        )

                        second_image_editor.resize(
                            (second_image_scaled_width, second_image_scaled_height)
                        )

                        # Calculate bottom-right corner position with some margin
                        x_offset = (
                            background_width
                            - second_image_scaled_width
                            - int(margin_percentage * background_width)
                        )
                        y_offset = (
                            background_height
                            - second_image_scaled_height
                            - int(margin_percentage * background_height)
                        )

                        # Paste the second image onto the bottom-right corner of the background
                        editor.paste(second_image_editor, (x_offset, y_offset))

                    buffered = BytesIO()
                    editor.save(buffered, file_format="PNG")

                    return base64.b64encode(buffered.getvalue()).decode()

                url = await fetch_and_edit_image(song.jacket_url, diff, status)
                url = f"data:image/png;base64,{url}"
            else:
                url = song.jacket_url
            await self.bot.send_image_update(
                self.bot,
                (await getch_user_id(self.bot, ctx.channel.name)),
                num,
                "update",
                url,
            )
            await ctx.reply(
                f"Display {num} | "
                + song.readable.split("|")[0].strip()
                + (f" {diff.capitalize()}" if diff else "")
                + (f" {status.upper()}" if status else "")
            )

    # @display.command()
    # async def chart(self, ctx: commands.Context, *, args):
    #     args = args.strip()
    #     num = args.split(" ")[-1]
    #     song = converters.SongConverter(ctx, args)
    #     if len(args.split(" ")) != 1:
    #         num = converters.Integer(ctx, num)
    #     if num == None or type(num) != int:
    #         num = 1
    #     if not (await self.bot.run_checks(ctx, activated_check=True, game_check=False, permission_level=3)): return
    #     await self.bot.command_ran(ctx)
    #     if not await self.bot.user_data.check_display(str((await getch_user_id(self.bot, ctx.channel.name))), num, self.bot.active_connections):
    #         await ctx.reply(f"Display {num} not active! Check your sources.")
    #         return
    #     if not song:
    #         await ctx.reply("Song not found.")
    #     else:
    #         await self.bot.send_image_update(self.bot, (await getch_user_id(self.bot, ctx.channel.name)), num, "update", song.chart_url)
    #         await ctx.reply(song.chart_url)


def prepare(bot: TwitchBot):
    bot.add_cog(DisplaysCog(bot))
