import twitchio
from twitchio.ext import commands

from main import TwitchBot

import datetime

from DATA.helpers.fuzzy_match import fuzzy_match_to_dict_key


class EventsCog(commands.Cog):
    def __init__(self, bot: TwitchBot):
        self.bot = bot

    @commands.command()
    async def event(self, ctx: commands.Context, *, title: str = None):
        if not (await self.bot.run_checks(ctx, activated_check=True, game_check=True)):
            return
        if title == None:
            pass
        else:
            title = str(title).lower().strip().strip("󠀀")
            try:
                title = self.bot.pjsk.katsu.romaji(title).strip("?").lower().strip()
            except:
                pass
        await self.bot.command_ran(ctx)

        def format_event_times(event_data):
            def time_diff_str(start, end, details=True):
                delta = end - start
                years = delta.days // 365
                months = (delta.days % 365) // 30
                days = (delta.days % 365) % 30
                hours, remainder = divmod(delta.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)

                parts = []
                if years > 0:
                    parts.append(f"{years} year{'s' if years != 1 else ''}")
                if months > 0:
                    parts.append(f"{months} month{'s' if months != 1 else ''}")
                if days > 0:
                    parts.append(f"{days} day{'s' if days != 1 else ''}")
                if details:
                    if hours > 0:
                        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
                    if minutes > 0:
                        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
                    if seconds > 0:
                        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

                return ", ".join(parts)

            now = datetime.datetime.now(datetime.timezone.utc)
            start_at = datetime.datetime.fromtimestamp(
                event_data["startAt"] / 1000, datetime.timezone.utc
            )
            closed_at = datetime.datetime.fromtimestamp(
                event_data["closedAt"] / 1000, datetime.timezone.utc
            )
            aggregate_at = datetime.datetime.fromtimestamp(
                event_data["aggregateAt"] / 1000, datetime.timezone.utc
            )

            if start_at > now:
                time_until_start = time_diff_str(now, start_at)
                return f"Event starts in {time_until_start} and lasts for {time_diff_str(start_at, closed_at)}."
            elif aggregate_at > now:
                time_since_start = time_diff_str(start_at, now)
                time_left = time_diff_str(now, aggregate_at)
                return f"Event started {time_since_start} ago. Time left: {time_left}."
            elif closed_at > now:
                time_since_start = time_diff_str(start_at, now, details=False)
                time_since_stop = time_diff_str(aggregate_at, now)
                time_left = time_diff_str(now, closed_at)
                return f"Event started {time_since_start} ago and ended {time_since_stop} ago. Next event starts in {time_left}."
            else:
                time_since_start = time_diff_str(start_at, now, details=False)
                time_since_aggregate = time_diff_str(aggregate_at, now, details=False)
                return f"Event started {time_since_start} ago and ended {time_since_aggregate} ago."

        if title and title.isdigit():
            title = int(title)
            ot = title
            title = self.bot.pjsk.events.get(title)
            if title:
                title = title["name"]
            else:
                return await ctx.reply(f"No event found with id {ot}.")

        if title in self.bot.pjsk.event_maps:
            data = self.bot.pjsk.events[self.bot.pjsk.event_maps[title]]
            id = data["id"]
            await ctx.reply(
                ("(JP EVENT!) " if data["jp"] else "")
                + f"{data['name']} |     | {self.bot.pjsk.event_type_map[data['eventType']]} |     | {self.bot.pjsk.unit_map[data['unit']]} |     | {format_event_times(data)}"
                + f" |     | https://sekai.best/event/{id}"
            )
            return
        elif title and title.lower() not in [
            "jp",
            "next",
            "jp next",
            "next jp",
            "upcoming",
            "jp upcoming",
            "upcoming jp",
        ]:
            if type(title) == int:
                data = self.bot.pjsk.events.get(title)
            else:
                matched_key = fuzzy_match_to_dict_key(title, self.bot.pjsk.event_maps)
                if matched_key is not None:
                    data = self.bot.pjsk.events[self.bot.pjsk.event_maps[matched_key]]
                else:
                    data = None
            if data:
                id = data["id"]
                await ctx.reply(
                    ("(JP EVENT!) " if data["jp"] else "")
                    + f"{data['name']} |     | {self.bot.pjsk.event_type_map[data['eventType']]} |     | {self.bot.pjsk.unit_map[data['unit']]} |     | {format_event_times(data)}"
                    + f" |     | https://sekai.best/event/{id}"
                )
                return
            else:
                await ctx.reply(f"Event not found.")
        elif not title:
            data = self.bot.pjsk.event_latest["en"]
            id = data["id"]
            await ctx.reply(
                ("(JP EVENT!) " if data["jp"] else "")
                + f"{data['name']} |     | {self.bot.pjsk.event_type_map[data['eventType']]} |     | {self.bot.pjsk.unit_map[data['unit']]} |     | {format_event_times(data)}"
                + f" |     | https://sekai.best/event/{id}"
            )
            return
        elif title.lower() in [
            "jp",
            "next",
            "jp next",
            "next jp",
            "upcoming",
            "jp upcoming",
            "upcoming jp",
        ]:
            data = (
                self.bot.pjsk.event_latest["jp"]
                if title.lower() == "jp"
                else (
                    self.bot.pjsk.event_next["en"]
                    if title.lower() in ["next", "upcoming"]
                    else self.bot.pjsk.event_next["jp"]
                )
            )
            if data:
                id = data["id"]
                await ctx.reply(
                    ("(JP EVENT!) " if data["jp"] else "")
                    + f"{data['name']} |     | {self.bot.pjsk.event_type_map[data['eventType']]} |     | {self.bot.pjsk.unit_map[data['unit']]} |     | {format_event_times(data)}"
                    + f" |     | https://sekai.best/event/{id}"
                )
            else:
                await ctx.reply("No data found for next event.")
            return
        else:
            await ctx.reply(f"Event not found.")


def prepare(bot: TwitchBot):
    bot.add_cog(EventsCog(bot))
