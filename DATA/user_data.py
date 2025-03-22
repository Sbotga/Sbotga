import time, json, datetime, math

from typing import List, Dict, Any

import asyncpg

from DATA.helpers.caseinsensitivedict import CaseInsensitiveDict
from DATA.helpers.user_cache import get_user_name_from_id


class USER_DATA:
    def __init__(self):
        self.users_using = []
        self.users = []
        self.to_join_ids = []
        self.user_ids = []
        self.using_reminders = []
        self.last_reminder = 0
        self.db: asyncpg.Pool = None

        with open("data.json") as f:
            self.data = json.load(f)
            if "REMINDER_DATA" in self.data:
                self.last_reminder = self.data.get("REMINDER_DATA")
            elif "REMINDER" in self.data:
                self.using_reminders = self.data.get("REMINDER")

        self.discord = None

    async def fetch_data(self):
        self.discord = self._DISCORD(self.db)
        async with self.db.acquire() as conn:
            # Fetch user IDs where whitelisted is TRUE and blacklisted is FALSE
            rows = await conn.fetch(
                """
                SELECT twitch_id, activated FROM users 
                WHERE whitelisted = TRUE AND (blacklisted = FALSE OR blacklisted IS NULL)
                """
            )

            self.user_ids = [row["twitch_id"] for row in rows]

            for row in rows:
                user_id = row["twitch_id"]
                user_name = get_user_name_from_id(user_id)
                if user_name is None:
                    self.to_join_ids.append(user_id)
                else:
                    self.users.append(user_name)
                if row["activated"]:
                    self.users_using.append(str(user_id))

    def update_last_reminder(self) -> int:
        t = time.time()
        self.data["REMINDER_DATA"] = t
        self.update()
        return t

    def toggle_reminders(self, user: str) -> bool:
        # Check if the user is already in the using_reminders list
        if user in self.using_reminders:
            # If the user is in the list, remove them and set reminders to False
            self.using_reminders.remove(user)
            new = False
        else:
            # If the user is not in the list, add them and set reminders to True
            self.using_reminders.append(user)
            new = True

        self.update()
        return new

    def update(self) -> None:
        self.data["REMINDER"] = self.using_reminders
        with open("users.json", "w+") as f:
            json.dump(json.loads(json.dumps(self.data)), f, indent=4)

    # Whitelist a user
    async def whitelist_user(self, user: str, twitch_id: int) -> str:
        await self.verify_twitch_user(twitch_id)
        self.users.append(user)
        self.user_ids.append(twitch_id)
        self.user_ids = list(set(self.user_ids))  # Ensure unique user IDs

        async with self.db.acquire() as conn:
            # Update the 'whitelisted' field to True for the user
            await conn.execute(
                "UPDATE users SET whitelisted = $1 WHERE twitch_id = $2",
                True,
                twitch_id,
            )

        return user

    # Blacklist a user
    async def blacklist_user(self, user: str, twitch_id: int) -> str:
        try:
            # Remove the user from the list if found
            index = self.users.index(user.lower())
            del self.users[index]
        except ValueError:
            pass

        try:
            # Remove the user ID if found
            while True:
                self.user_ids.remove(twitch_id)
        except ValueError:
            pass

        async with self.db.acquire() as conn:
            # Update the 'blacklisted' field to True for the user
            await conn.execute(
                "UPDATE users SET blacklisted = $1 WHERE twitch_id = $2",
                True,
                twitch_id,
            )

        return user

    # Unwhitelist a user
    async def unwhitelist_user(self, user: str, twitch_id: int) -> str:
        try:
            # Remove the user from the whitelist list if found
            self.users.remove(user)
        except ValueError:
            pass

        try:
            # Remove the user ID from the list
            while True:
                self.user_ids.remove(twitch_id)
        except ValueError:
            pass

        async with self.db.acquire() as conn:
            # Update the 'whitelisted' field to False for the user
            await conn.execute(
                "UPDATE users SET whitelisted = $1 WHERE twitch_id = $2",
                False,
                twitch_id,
            )

        return user

    # Unblacklist a user
    async def unblacklist_user(self, user: str, twitch_id: int) -> str:
        try:
            # Remove the user from the blacklist list if found
            self.users.remove(user)
        except ValueError:
            pass

        try:
            # Remove the user ID from the list
            while True:
                self.user_ids.remove(twitch_id)
        except ValueError:
            pass

        async with self.db.acquire() as conn:
            # Update the 'blacklisted' field to False for the user
            await conn.execute(
                "UPDATE users SET blacklisted = $1 WHERE twitch_id = $2",
                False,
                twitch_id,
            )

        return user

    # Get ranked data
    async def get_ranked(self, twitch_id: str):
        """
        Fetch ranked data for a user.
        Defaults to 0 values if no data exists.
        """
        twitch_id = int(twitch_id)  # Convert the user argument (string) to integer
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT wins, losses, draws, max_winstreak, winstreak FROM ranked WHERE twitch_id = $1",
                twitch_id,
            )
            if row:
                return dict(row)
            else:
                # If the user is not found, return default values
                return {
                    "wins": 0,
                    "losses": 0,
                    "draws": 0,
                    "max_winstreak": 0,
                    "winstreak": 0,
                }

    # Add a win to the ranked data
    async def add_ranked_win(self, twitch_id: str):
        """
        Increment the wins and winstreak.
        """
        twitch_id = int(twitch_id)  # Convert the user argument (string) to integer
        async with self.db.acquire() as conn:
            # Fetch current ranked data
            row = await conn.fetchrow(
                "SELECT wins, winstreak, max_winstreak FROM ranked WHERE twitch_id = $1",
                twitch_id,
            )
            if row:
                wins = row["wins"] + 1
                winstreak = row["winstreak"] + 1
                max_winstreak = max(row["max_winstreak"], winstreak)
                await conn.execute(
                    """
                    UPDATE ranked SET wins = $1, winstreak = $2, max_winstreak = $3
                    WHERE twitch_id = $4
                    """,
                    wins,
                    winstreak,
                    max_winstreak,
                    twitch_id,
                )
            else:
                # If no data exists, insert new data
                await conn.execute(
                    """
                    INSERT INTO ranked (twitch_id, wins, losses, draws, max_winstreak, winstreak)
                    VALUES ($1, 1, 0, 0, 1, 1)
                    """,
                    twitch_id,
                )
        return await self.get_ranked(twitch_id)

    # Add a loss or draw to the ranked data
    async def add_ranked_loss_or_draw(self, twitch_id: str, ld: str = "loss"):
        """
        Increment the losses or draws, and reset winstreak.
        """
        twitch_id = int(twitch_id)  # Convert the user argument (string) to integer
        async with self.db.acquire() as conn:
            # Fetch current ranked data
            row = await conn.fetchrow(
                "SELECT losses, draws, winstreak FROM ranked WHERE twitch_id = $1",
                twitch_id,
            )
            if row:
                losses = row["losses"] + 1 if ld == "loss" else row["losses"]
                draws = row["draws"] + 1 if ld == "draw" else row["draws"]
                await conn.execute(
                    """
                    UPDATE ranked SET losses = $1, draws = $2, winstreak = 0
                    WHERE twitch_id = $3
                    """,
                    losses,
                    draws,
                    twitch_id,
                )
            else:
                # If no data exists, insert new data with default losses or draws
                await conn.execute(
                    """
                    INSERT INTO ranked (twitch_id, wins, losses, draws, max_winstreak, winstreak)
                    VALUES ($1, 0, 1 if ld == "loss" else 0, 1 if ld == "draw" else 0, 0, 0)
                    """,
                    twitch_id,
                )
        return await self.get_ranked(twitch_id)

    # Reset ranked data for a user
    async def reset_ranked(self, twitch_id: str):
        """
        Reset all ranked data to default values.
        """
        twitch_id = int(twitch_id)  # Convert the user argument (string) to integer
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                UPDATE ranked SET wins = 0, losses = 0, draws = 0, max_winstreak = 0, winstreak = 0
                WHERE twitch_id = $1
                """,
                twitch_id,
            )
        return await self.get_ranked(twitch_id)

    async def get_display(self, user: str, num: int):
        async with self.db.acquire() as conn:
            # Fetch displays JSON from the users table for the specific user
            row = await conn.fetchrow(
                "SELECT displays FROM users WHERE twitch_id = $1", int(user)
            )

            if row and row["displays"]:
                displays = json.loads(row["displays"])
                # Get the display corresponding to the given number, or return default if not found
                return displays.get(str(num), {"url": "", "hidden": True})
            return {"url": "", "hidden": True}

    async def set_display(self, user: str, num: int, data: dict):
        async with self.db.acquire() as conn:
            # Fetch the current displays JSON for the user
            row = await conn.fetchrow(
                "SELECT displays FROM users WHERE twitch_id = $1", int(user)
            )

            if row:
                displays = json.loads(row["displays"]) or {}
                # Update the display for the specified number
                displays[str(num)] = data
                # Update the displays field in the database
                await conn.execute(
                    "UPDATE users SET displays = $1 WHERE twitch_id = $2",
                    json.dumps(displays),
                    int(user),
                )
            else:
                # If user does not exist, insert a new user with the display data
                await conn.execute(
                    """
                    INSERT INTO users (twitch_id, displays) 
                    VALUES ($1, $2)
                    """,
                    int(user),
                    {str(num): data},
                )

    async def check_display(self, user: str, num: int, ac: dict):
        active_connections = ac
        user_key = f"user_{user}"

        # Check if the user and number exist in the active connections
        if user_key in active_connections and num in active_connections[user_key]:
            websockets = active_connections[user_key][num]
            return (
                len(websockets) > 0
            )  # Return True if there are websockets, False otherwise

        return False

    async def activate_user(self, user: str):
        async with self.db.acquire() as conn:
            # Set the user's activated status to True
            await conn.execute(
                "UPDATE users SET activated = $1 WHERE twitch_id = $2", True, int(user)
            )

            # Append the user to the users_using list
            self.users_using.append(user)

    async def deactivate_user(self, user: str):
        async with self.db.acquire() as conn:
            # Set the user's activated status to False
            await conn.execute(
                "UPDATE users SET activated = $1 WHERE twitch_id = $2", False, int(user)
            )

            # Remove the user from the users_using list
            if user in self.users_using:
                self.users_using.remove(user)

    async def add_to_counter(self, user: str, counter: str, amount: int) -> int:
        async with self.db.acquire() as conn:
            # Fetch counters and wrap them in CaseInsensitiveDict
            result = await conn.fetchrow(
                """
                SELECT counters
                FROM counters
                WHERE twitch_id = $1
                """,
                int(user),
            )

            counters = CaseInsensitiveDict(
                result["counters"] if result and result["counters"] else {}
            )

            # Modify the counter
            current_value = counters.get(counter, 0)
            counters[counter] = current_value + amount

            # Update the database with modified counters
            await conn.execute(
                """
                UPDATE counters
                SET counters = $1
                WHERE twitch_id = $2
                """,
                json.dumps(counters),
                int(user),
            )

            return counters.get(counter, 0)

    async def set_counter(self, user: str, counter: str, amount: int) -> int:
        async with self.db.acquire() as conn:
            # Fetch counters and wrap them in CaseInsensitiveDict
            result = await conn.fetchrow(
                """
                SELECT counters
                FROM counters
                WHERE twitch_id = $1
                """,
                int(user),
            )

            counters = CaseInsensitiveDict(
                result["counters"] if result and result["counters"] else {}
            )

            # Set the counter value
            counters[counter] = amount

            # Update the database with modified counters
            await conn.execute(
                """
                UPDATE counters
                SET counters = $1
                WHERE twitch_id = $2
                """,
                json.dumps(counters),
                int(user),
            )

            return amount

    async def add_counter(self, user: str, counter: str) -> str:
        async with self.db.acquire() as conn:
            # Fetch existing counters or initialize if not present
            result = await conn.fetchrow(
                """
                SELECT counters
                FROM counters
                WHERE twitch_id = $1
                """,
                int(user),
            )

            counters = CaseInsensitiveDict(
                result["counters"] if result and result["counters"] else {}
            )

            # Add new counter with value 0 if it doesn't exist
            if counter not in counters:
                counters[counter] = 0

            # Update the database with modified counters
            await conn.execute(
                """
                UPDATE counters
                SET counters = $1
                WHERE twitch_id = $2
                """,
                json.dumps(counters),
                int(user),
            )

        return counter

    async def reset_counter(self, user: str, counter: str) -> int:
        async with self.db.acquire() as conn:
            # Fetch counters and wrap them in CaseInsensitiveDict
            result = await conn.fetchrow(
                """
                SELECT counters
                FROM counters
                WHERE twitch_id = $1
                """,
                int(user),
            )

            counters = CaseInsensitiveDict(
                result["counters"] if result and result["counters"] else {}
            )

            # Reset the counter to 0
            counters[counter] = 0

            # Update the database with modified counters
            await conn.execute(
                """
                UPDATE counters
                SET counters = $1
                WHERE twitch_id = $2
                """,
                json.dumps(counters),
                int(user),
            )

            return 0

    async def remove_counter(self, user: str, counter: str) -> int:
        async with self.db.acquire() as conn:
            # Fetch counters and wrap them in CaseInsensitiveDict
            result = await conn.fetchrow(
                """
                SELECT counters
                FROM counters
                WHERE twitch_id = $1
                """,
                int(user),
            )

            counters = CaseInsensitiveDict(
                result["counters"] if result and result["counters"] else {}
            )

            # Remove the counter if it exists
            if counter in counters:
                del counters[counter]

            # Update the database with modified counters
            await conn.execute(
                """
                UPDATE counters
                SET counters = $1
                WHERE twitch_id = $2
                """,
                json.dumps(counters),
                int(user),
            )

            return 0

    async def get_counter(self, user: str, counter: str) -> int:
        async with self.db.acquire() as conn:
            # Fetch the counter value from the JSON
            result = await conn.fetchrow(
                """
                SELECT counters
                FROM counters
                WHERE twitch_id = $1
                """,
                int(user),
            )

            if result and result["counters"]:
                return CaseInsensitiveDict(result["counters"]).get(counter, 0)
            return 0

    async def get_counters(self, user: str) -> dict:
        async with self.db.acquire() as conn:
            # Fetch all counters for the user
            result = await conn.fetchrow(
                """
                SELECT counters
                FROM counters
                WHERE twitch_id = $1
                """,
                int(user),
            )

            if result and result["counters"]:
                return CaseInsensitiveDict(result["counters"])
            return CaseInsensitiveDict()

    async def verify_twitch_user(self, user: str):
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE twitch_id = $1", int(user)
            )

            if row:
                pass
            else:
                # If user does not exist, insert a new user with the display data
                await conn.execute(
                    """
                    INSERT INTO users (twitch_id) 
                    VALUES ($1)
                    """,
                    int(user),
                )

    class _DISCORD:
        def __init__(self, db: asyncpg.Pool):
            self.db = db

            self.SETTING_DEFAULTS = {
                "first_time_guess_end": True,
                "default_region": "en",
                "mirror_charts_by_default": False,
                "default_difficulty": "master",
            }

        async def verify_discord_user(self, user_id: int):
            async with self.db.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM users WHERE discord_id = $1", user_id
                )
                if row:
                    pass
                else:
                    # If user does not exist, insert a new user with the display data
                    await conn.execute(
                        """
                        INSERT INTO users (discord_id) 
                        VALUES ($1)
                        """,
                        user_id,
                    )

        async def verify_discord_guild(self, guild_id: int):
            async with self.db.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM guilds WHERE guild_id = $1", guild_id
                )
                if row:
                    pass
                else:
                    # If guild does not exist, insert a new guild
                    await conn.execute(
                        """
                        INSERT INTO guilds (guild_id) 
                        VALUES ($1)
                        """,
                        guild_id,
                    )

        async def update_pjsk_id(self, user_id: int, pjsk_id: int, region: str):
            await self.verify_discord_user(user_id)
            async with self.db.acquire() as conn:
                await conn.execute(
                    f"""
                    UPDATE users
                    SET pjsk_id_{region} = $1
                    WHERE discord_id = $2
                    """,
                    pjsk_id,
                    user_id,
                )

        async def remove_pjsk_id(self, user_id: int, region: str):
            await self.verify_discord_user(user_id)
            async with self.db.acquire() as conn:
                await conn.execute(
                    f"""
                    UPDATE users
                    SET pjsk_id_{region} = $1
                    WHERE discord_id = $2
                    """,
                    None,
                    user_id,
                )

        async def set_banned(self, user_id: int, blacklisted: bool) -> None:
            await self.verify_discord_user(user_id)
            async with self.db.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE users
                    SET blacklisted = $1
                    WHERE discord_id = $2
                    """,
                    blacklisted,
                    user_id,
                )

        async def get_banned(self, user_id: int) -> bool:
            await self.verify_discord_user(user_id)
            async with self.db.acquire() as conn:
                result = await conn.fetchrow(
                    f"""
                    SELECT blacklisted
                    FROM users
                    WHERE discord_id = $1
                    """,
                    user_id,
                )
                return (
                    result["blacklisted"] if result and result["blacklisted"] else False
                )

        async def get_pjsk_id(self, user_id: int, region: str) -> int | None:
            await self.verify_discord_user(user_id)
            async with self.db.acquire() as conn:
                result = await conn.fetchrow(
                    f"""
                    SELECT pjsk_id_{region}
                    FROM users
                    WHERE discord_id = $1
                    """,
                    user_id,
                )
                return (
                    result["pjsk_id_" + region]
                    if result and result["pjsk_id_" + region]
                    else None
                )

        async def get_discord_user_id_from_pjsk_id(
            self, pjsk_id: int, region: str
        ) -> int | None:
            pjsk_id = int(pjsk_id)
            async with self.db.acquire() as conn:
                result = await conn.fetchrow(
                    f"""
                    SELECT discord_id
                    FROM users
                    WHERE pjsk_id_{region} = $1
                    """,
                    pjsk_id,
                )
                return result["discord_id"] if result else None

        async def get_guesses(self, user_id: int, key: str = None) -> dict:
            await self.verify_discord_user(user_id)
            async with self.db.acquire() as conn:
                result = await conn.fetchrow(
                    f"""
                    SELECT guess_stats
                    FROM users
                    WHERE discord_id = $1
                    """,
                    user_id,
                )
                stuff = (
                    json.loads(result["guess_stats"])
                    if result and result["guess_stats"]
                    else {}
                )
                return (
                    stuff.get(key, {"fail": 0, "success": 0, "ragequit": 0, "hint": 0})
                    if key
                    else stuff
                )

        async def get_settings(self, user_id: int, key: str = None) -> dict | Any:
            await self.verify_discord_user(user_id)
            async with self.db.acquire() as conn:
                assert key in self.SETTING_DEFAULTS or key == None
                if key:
                    key = key.lower().strip()
                result = await conn.fetchrow(
                    f"""
                    SELECT settings
                    FROM users
                    WHERE discord_id = $1
                    """,
                    user_id,
                )
                stuff = (
                    json.loads(result["settings"])
                    if result and result["settings"]
                    else {}
                )
                return (
                    stuff.get(key, self.SETTING_DEFAULTS[key])
                    if key
                    else {
                        key: stuff.get(key, value)
                        for key, value in self.SETTING_DEFAULTS.items()
                    }
                )

        async def change_settings(self, user_id: int, key: str, value) -> dict:
            await self.verify_discord_user(user_id)
            async with self.db.acquire() as conn:
                key = key.lower().strip()
                assert key in self.SETTING_DEFAULTS
                result = await conn.fetchrow(
                    f"""
                    SELECT settings
                    FROM users
                    WHERE discord_id = $1
                    """,
                    user_id,
                )
                stuff = (
                    json.loads(result["settings"])
                    if result and result["settings"]
                    else {}
                )
                stuff[key] = value

                for key, value in stuff.copy().items():
                    if key not in self.SETTING_DEFAULTS.keys():
                        stuff.pop(key, 0)

                await conn.execute(
                    """
                    UPDATE users
                    SET settings = $1
                    WHERE discord_id = $2
                    """,
                    json.dumps(stuff),
                    user_id,
                )
                return stuff

        async def add_guesses(
            self, user_id: int, key: str, stat: str, return_all: bool = False
        ) -> dict:
            await self.verify_discord_user(user_id)

            async with self.db.acquire() as conn:
                # Fetch the current guess_stats from the database
                result = await conn.fetchrow(
                    """
                    SELECT guess_stats
                    FROM users
                    WHERE discord_id = $1
                    """,
                    user_id,
                )

                # If no result, initialize an empty dict
                guess_stats = (
                    json.loads(result["guess_stats"])
                    if result and result["guess_stats"]
                    else {}
                )

                # Check if the key exists, if not, create it with default values
                if key not in guess_stats:
                    guess_stats[key] = {
                        "fail": 0,
                        "success": 0,
                        "ragequit": 0,
                        "hint": 0,
                    }

                # Increment the specified stat for the key
                if stat in guess_stats[key]:
                    guess_stats[key][stat] += 1  # Or any other logic for incrementing

                # Update the guess_stats column with the modified data
                await conn.execute(
                    """
                    UPDATE users
                    SET guess_stats = $1
                    WHERE discord_id = $2
                    """,
                    json.dumps(guess_stats),
                    user_id,
                )

                if return_all:
                    data = {
                        "fail": 0,
                        "success": 0,
                        "ragequit": 0,
                        "hint": 0,
                    }
                    for value in guess_stats.values():
                        data["fail"] += value["fail"]
                        data["success"] += value["success"]
                        data["ragequit"] += value["ragequit"]
                        data["hint"] += value["hint"]
                    return data
                return guess_stats[key]

        async def reset_guesses(self, user_id: int, key: str, stat: str = None) -> dict:
            await self.verify_discord_user(user_id)

            async with self.db.acquire() as conn:
                # Fetch the current guess_stats from the database
                result = await conn.fetchrow(
                    """
                    SELECT guess_stats
                    FROM users
                    WHERE discord_id = $1
                    """,
                    user_id,
                )

                # If no result, initialize an empty dict
                guess_stats = (
                    json.loads(result["guess_stats"])
                    if result and result["guess_stats"]
                    else {}
                )

                # Check if the key exists, if not, create it with default values
                if key not in guess_stats:
                    guess_stats[key] = {
                        "fail": 0,
                        "success": 0,
                        "ragequit": 0,
                        "hint": 0,
                    }

                assert stat in [None, "fail", "success", "ragequit", "hint"]

                if stat:
                    if stat in guess_stats[key]:
                        guess_stats[key][stat] = 0
                    else:
                        guess_stats[key] = {
                            "fail": 0,
                            "success": 0,
                            "ragequit": 0,
                            "hint": 0,
                        }

                # Update the guess_stats column with the modified data
                await conn.execute(
                    """
                    UPDATE users
                    SET guess_stats = $1
                    WHERE discord_id = $2
                    """,
                    json.dumps(guess_stats),
                    user_id,
                )

                return guess_stats[key]

        async def get_guesses_position(self, guess_type: str, user_id: int):
            """
            user pos, user page
            """
            per_page = 25

            # Construct the query for getting the leaderboard position and stats in a single query
            query = f"""
            WITH user_stats AS (
                SELECT 
                    discord_id,
                    COALESCE(CAST(guess_stats->'{guess_type}'->>'success' AS INT), 0) AS success,
                    COALESCE(CAST(guess_stats->'{guess_type}'->>'fail' AS INT), 0) AS fail
                FROM users
                WHERE discord_id = $1
            ),
            leaderboard AS (
                SELECT 
                    discord_id,
                    CAST(guess_stats->'{guess_type}'->>'success' AS INT) AS score,
                    ROW_NUMBER() OVER (
                        ORDER BY CAST(guess_stats->'{guess_type}'->>'success' AS INT) DESC, id
                    ) AS rank
                FROM users
                WHERE guess_stats ? $2
            )
            SELECT 
                COALESCE(user_stats.success + user_stats.fail, 0) AS total_guesses,
                COALESCE(leaderboard.rank, 0) AS user_position
            FROM user_stats
            LEFT JOIN leaderboard ON leaderboard.discord_id = user_stats.discord_id
            """

            user_result = await self.db.fetchrow(query, user_id, guess_type)

            if user_result:
                total_guesses = user_result["total_guesses"]
                if total_guesses == 0:
                    user_position = 0
                    user_page = 0
                else:
                    user_position = user_result["user_position"]
                    user_page = (user_position + per_page - 1) // per_page
            else:
                user_position = 0
                user_page = 0

            return user_position, user_page

        async def get_guesses_leaderboard(
            self, guess_type: str, page: int, user_id: int
        ):
            """
            leaderboard for this page, user pos, user page, total pages
            """
            per_page = 25

            # Fetch total number of users with the specified guess_type
            total_result = await self.db.fetchval(
                """
                SELECT COUNT(*)
                FROM users
                WHERE guess_stats ? $1
                """,
                guess_type,
            )
            total_pages = (
                total_result + per_page - 1
            ) // per_page  # Calculate total pages

            # Validate page number against total_pages
            if page > total_pages and total_pages > 0:
                page = total_pages  # Adjust to the last valid page

            # Fetch leaderboard data for the current page
            leaderboard = await self.db.fetch(
                f"""
                SELECT id, discord_id, 
                    guess_stats->'{guess_type}'->>'success' AS success,
                    CAST(guess_stats->'{guess_type}'->>'success' AS INT) AS score
                FROM users
                WHERE guess_stats ? $1
                ORDER BY score DESC, id ASC
                LIMIT $2 OFFSET $3
                """,
                guess_type,
                per_page,
                (page - 1) * per_page,
            )

            user_position, user_page = await self.get_guesses_position(
                guess_type, user_id
            )

            return leaderboard, user_position, user_page, total_pages

        async def get_guesses_at_rank(self, guess_type: str, rank: int):
            """
            Fetch the user at a specific rank for the given guess_type.
            """
            # Fetch leaderboard data for the user at the specific rank
            leaderboard_at_rank = await self.db.fetchrow(
                f"""
                SELECT id, discord_id, 
                    guess_stats->'{guess_type}'->>'success' AS success,
                    CAST(guess_stats->'{guess_type}'->>'success' AS INT) AS score
                FROM users
                WHERE guess_stats ? $1
                ORDER BY score DESC, id ASC
                OFFSET $2 LIMIT 1
                """,
                guess_type,
                (rank - 1),  # OFFSET is zero-based
            )

            return leaderboard_at_rank

        async def add_currency(self, user_id: int, amount: int) -> int:
            """Add (or subtract) currency and return the new balance."""
            await self.verify_discord_user(user_id)
            async with self.db.acquire() as conn:
                result = await conn.fetchrow(
                    """
                    UPDATE users
                    SET currency = currency + $1
                    WHERE discord_id = $2
                    RETURNING currency;
                    """,
                    amount,
                    user_id,
                )
                return result["currency"] if result else 0

        async def get_currency(self, user_id: int) -> int:
            """Get the user's current currency balance."""
            await self.verify_discord_user(user_id)
            async with self.db.acquire() as conn:
                result = await conn.fetchrow(
                    """
                    SELECT currency
                    FROM users
                    WHERE discord_id = $1;
                    """,
                    user_id,
                )
                return result["currency"] if result else 0

        async def add_achievement(
            self, user_id: int, achievement_id: str, rank: int, rewards: list
        ):
            """Add an achievement with a specific rank and rewards."""
            await self.verify_discord_user(user_id)
            async with self.db.acquire() as conn:
                result = await conn.fetchrow(
                    """
                    SELECT achievements FROM users WHERE discord_id = $1;
                    """,
                    user_id,
                )

                achievements = (
                    json.loads(result["achievements"])
                    if result and result["achievements"]
                    else {}
                )

                # Ensure the structure exists
                if achievement_id not in achievements:
                    achievements[achievement_id] = {"granted": {}}

                # Add the rank entry
                if str(rank) not in achievements[achievement_id]["granted"]:
                    achievements[achievement_id]["granted"][str(rank)] = {
                        "date": datetime.datetime.now(
                            datetime.timezone.utc
                        ).isoformat(),
                        "rewards": rewards,
                    }

                # Update the database
                await conn.execute(
                    """
                    UPDATE users SET achievements = $1 WHERE discord_id = $2;
                    """,
                    json.dumps(achievements),
                    user_id,
                )

        async def get_achievements(self, user_id: int) -> dict:
            """Retrieve the user's achievements."""
            await self.verify_discord_user(user_id)
            async with self.db.acquire() as conn:
                result = await conn.fetchrow(
                    """
                    SELECT achievements FROM users WHERE discord_id = $1;
                    """,
                    user_id,
                )
                return (
                    json.loads(result["achievements"])
                    if result and result["achievements"]
                    else {}
                )

        async def remove_achievement(
            self, user_id: int, achievement_id: str, rank: int = None
        ):
            """Remove a specific rank of an achievement."""
            await self.verify_discord_user(user_id)
            async with self.db.acquire() as conn:
                result = await conn.fetchrow(
                    """
                    SELECT achievements FROM users WHERE discord_id = $1;
                    """,
                    user_id,
                )

                achievements = (
                    json.loads(result["achievements"])
                    if result and result["achievements"]
                    else {}
                )

                # Remove the specified rank
                if rank:
                    if (
                        achievement_id in achievements
                        and str(rank) in achievements[achievement_id]["granted"]
                    ):
                        del achievements[achievement_id]["granted"][str(rank)]

                        # If no more ranks remain, remove the achievement entry
                        if not achievements[achievement_id]["granted"]:
                            del achievements[achievement_id]
                else:
                    del achievements[achievement_id]

                # Update the database
                await conn.execute(
                    """
                    UPDATE users SET achievements = $1 WHERE discord_id = $2;
                    """,
                    json.dumps(achievements),
                    user_id,
                )

        async def has_achievement(self, user_id: int, achievement_id: str) -> int:
            """Check if the user has a specific achievement, returning rank."""
            await self.verify_discord_user(user_id)
            async with self.db.acquire() as conn:
                result = await conn.fetchrow(
                    """
                    SELECT achievements FROM users WHERE discord_id = $1;
                    """,
                    user_id,
                )

                achievements = (
                    json.loads(result["achievements"])
                    if result and result["achievements"]
                    else {}
                )

                # Check if the achievement exists
                if achievement_id not in achievements:
                    return 0

                granted = achievements[achievement_id]["granted"]

                # Get the highest rank (key) in granted
                highest_rank = max(int(rank) for rank in granted.keys())

                return highest_rank

        async def add_experience(self, user_id: int, amount: int) -> int:
            """Add experience and return the new total."""
            await self.verify_discord_user(user_id)
            async with self.db.acquire() as conn:
                result = await conn.fetchrow(
                    """
                    UPDATE users
                    SET experience = experience + $1
                    WHERE discord_id = $2
                    RETURNING experience;
                    """,
                    amount,
                    user_id,
                )
                return result["experience"] if result else 0

        async def get_experience(self, user_id: int) -> int:
            """Get the user's current experience."""
            await self.verify_discord_user(user_id)
            async with self.db.acquire() as conn:
                result = await conn.fetchrow(
                    """
                    SELECT experience
                    FROM users
                    WHERE discord_id = $1;
                    """,
                    user_id,
                )
                return result["experience"] if result else 0

        @staticmethod
        def incremental_xp(level: int) -> int:
            """
            Returns the XP required to go from (level-1) to level.
            For level 1, returns 0.
            For level >= 2, calculates:
                XP = a * (level^b - (level-1)^b)
            then caps it to a maximum of 39,000.
            """
            # Fitting parameters and cap
            a = 34.48
            b = 1.45
            max_increment = 39000  # Maximum XP increase per level
            if level <= 1:
                return 0
            xp_needed = a * (math.pow(level, b) - math.pow(level - 1, b))
            return min(int(xp_needed), max_increment)

        @staticmethod
        def xp_for_level(level: int) -> int:
            """
            Returns the total XP required to reach a given level.
            This is computed as the sum of incremental XP values for levels 2 to 'level'.
            """
            total_xp = 0
            for lvl in range(2, level + 1):
                total_xp += USER_DATA._DISCORD.incremental_xp(lvl)
            return total_xp

        @staticmethod
        def calculate_level(experience: int) -> tuple[int, int, int]:
            """
            Given a total experience value, calculates:
            - The current level.
            - XP already accumulated in the current level.
            - XP required for the next level.
            This function uses the incremental_xp function independently.
            """
            level = 1
            total_xp = 0

            # Increment levels until the next level's XP would exceed the experience.
            while True:
                next_increment = USER_DATA._DISCORD.incremental_xp(level + 1)
                if total_xp + next_increment > experience:
                    break
                total_xp += next_increment
                level += 1

            xp_into_level = experience - total_xp
            xp_for_next = USER_DATA._DISCORD.incremental_xp(level + 1)
            return level, xp_into_level, xp_for_next

        async def toggle_guessing(self, guild_id: int, enabled: bool) -> int:
            """Toggle guessing on/off in a Discord gulid"""
            await self.verify_discord_guild(guild_id)
            async with self.db.acquire() as conn:
                result = await conn.fetchrow(
                    """
                    UPDATE guilds
                    SET guessing_enabled = $1
                    WHERE guild_id = $2
                    RETURNING guessing_enabled;
                    """,
                    enabled,
                    guild_id,
                )
                return result["guessing_enabled"] if result else True

        async def guessing_enabled(self, guild_id: int) -> bool:
            """Check if guessing is enabled for the given guild."""
            await self.verify_discord_guild(guild_id)
            async with self.db.acquire() as conn:
                result = await conn.fetchrow(
                    "SELECT guessing_enabled FROM guilds WHERE guild_id = $1", guild_id
                )
                return result["guessing_enabled"] if result else True


user_data = USER_DATA()
