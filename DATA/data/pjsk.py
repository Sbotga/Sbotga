import cutlet
import re, datetime, time, asyncio, threading, json, os, unicodedata, traceback

import requests

from DATA.user_data import user_data

from DATA.game_api import methods

from DATA.helpers.tools import generate_secure_string


class pjsk_data:
    def __init__(self):
        self._defs = {}

        self.katsu = cutlet.Cutlet()
        self.katsu_foreignless = cutlet.Cutlet()
        self.katsu_foreignless.use_foreign_spelling = False

        self.refreshing = []
        self._refreshed_at = 0
        self.refresh_data()

    def refresh_data(self):
        if self.refreshing:
            return
        thread_code = generate_secure_string(10)
        self.refreshing.append(thread_code)
        print("Refreshing data")
        try:
            try:
                self.music_meta = requests.get(
                    "https://storage.sekai.best/sekai-best-assets/music_metas.json"
                ).json()
            except:
                self.music_meta = []

            # Functions and Tools
            def simplify_title(title):
                text = (
                    unicodedata.normalize("NFKD", title)
                    .encode("ascii", "ignore")
                    .decode("utf-8")
                )
                text = text.lower().strip()
                STAR_LIKE = (
                    r"[\u2600-\u26FF]"  # Miscellaneous Symbols (includes stars like ★, ☆, ✩, ✪)
                    r"|[\U0001F300-\U0001F5FF]"  # Miscellaneous Symbols and Pictographs (includes 🌟)
                )

                text = re.sub(STAR_LIKE, " ", text)
                return title

            # Requests
            events = methods.pjsk_game_api.get_master_data(
                "events.json", force=True, deepcopy=True
            )
            events_jp = methods.pjsk_game_api_jp.get_master_data(
                "events.json", force=True, deepcopy=True
            )
            self.characters = methods.pjsk_game_api.get_master_data(
                "characterProfiles.json", force=True, deepcopy=True
            )
            self.characters_game = methods.pjsk_game_api.get_master_data(
                "gameCharacters.json", force=True, deepcopy=True
            )
            self.cc_teams = methods.pjsk_game_api.get_master_data(
                "cheerfulCarnivalTeams.json", force=True, deepcopy=True
            )

            # Maps
            self.unit_map = {
                "all": None,
                "other": "Other",
                "none": "No Main Unit",
                "vocaloid": "VIRTUAL SINGER",
                "piapro": "VIRTUAL SINGER",
                "school_refusal": "Nightcord at 25:00",
                "light_sound": "Leo/need",
                "light_music_club": "Leo/need",
                "idol": "MORE MORE JUMP!",
                "street": "Vivid BAD SQUAD",
                "theme_park": "Wonderlands×Showtime",
            }
            self.event_type_map = {
                "marathon": "Marathon",
                "cheerful_carnival": "Cheerful Carnival",
                "world_bloom": "World Link",
            }

            musics = [
                api.get_master_data("musics.json", force=True, deepcopy=True)
                for api in methods.all_apis
            ]
            music_difficulties = [
                api.get_master_data("musicDifficulties.json", force=True, deepcopy=True)
                for api in methods.all_apis
            ]
            music_tags = [
                api.get_master_data("musicTags.json", force=True, deepcopy=True)
                for api in methods.all_apis
            ]
            all_da_events = [
                api.get_master_data("events.json", force=True, deepcopy=True)
                for api in methods.all_apis
            ]

            for songs in musics:
                for data in songs:
                    if data["id"] == 388 and not data["title"].endswith(" [APPEND]"):
                        data["title"] += " [APPEND]"
                        break

            if len(self.refreshing) > 1:
                self.refreshing.remove(thread_code)
                return

            # Cards
            print("Card mapping!")
            self.cards = {}
            self.cards_en_jp = {}
            card_map_path = "DATA/data/card_map.json"
            if os.path.exists(card_map_path):
                with open(card_map_path, "r", encoding="utf8") as f:
                    try:
                        cd = json.load(f)
                        self.cards = cd["cards"]
                        self.cards_en_jp = cd["cards_en_jp"]
                    except:
                        pass
            temp_chara_data = methods.pjsk_game_api.get_master_data(
                "gameCharacters.json", force=True, deepcopy=True
            )
            temp_jp_cards = methods.pjsk_game_api_jp.get_master_data(
                "cards.json", force=True, deepcopy=True
            )
            for api in methods.all_apis:
                card_data = api.get_master_data("cards.json", force=True, deepcopy=True)
                for card in card_data:
                    if methods.pjsk_game_api_jp.isleak_card(card["id"], temp_jp_cards):
                        continue
                    name = methods.Tools.get_card_name(
                        card["id"],
                        False,
                        include_character=True,
                        include_rarity=True,
                        include_attribute=True,
                        use_emojis=False,
                        region=api.app_region,
                        provided_chara_data=temp_chara_data,
                        provided_card_data=card_data,
                    )
                    if name not in self.cards:
                        self.cards[name] = card["id"]
                    if api.app_region == "en":
                        self.cards_en_jp[name] = card["id"]
                    if api.app_region == "jp":
                        if card["id"] not in self.cards_en_jp.values():
                            self.cards_en_jp[name] = card["id"]
                        name = self.katsu_foreignless.romaji(name).replace(" ]", "]")
                        self.cards[name] = card["id"]
            with open(card_map_path, "w+", encoding="utf8") as f:
                json.dump(
                    {"cards": self.cards, "cards_en_jp": self.cards_en_jp}, f, indent=4
                )

            # Title Maps
            print("Song title mapping!")
            self._title_maps = {}
            self._titles = {}
            for i, songs in enumerate(musics):
                for data in songs:
                    update = False
                    title = data["title"].strip()
                    if data["id"] not in self._title_maps.values():
                        update = True
                    self._title_maps[title] = data["id"]
                    if update:
                        self._titles[title] = data["id"]
                    if i == 1:  # jp
                        try:
                            self._title_maps[
                                self.katsu.romaji(data["pronunciation"])
                            ] = data["id"]
                            self._title_maps[self.katsu.romaji(title)] = data["id"]
                        except Exception as e:
                            print(e)
                        try:
                            self._title_maps[
                                self.katsu_foreignless.romaji(data["pronunciation"])
                            ] = data["id"]
                            self._title_maps[self.katsu_foreignless.romaji(title)] = (
                                data["id"]
                            )
                            if update:
                                self._titles[
                                    self.katsu_foreignless.romaji(
                                        data["pronunciation"]
                                    ).title()
                                ] = data["id"]
                                self._titles[
                                    self.katsu_foreignless.romaji(title).title()
                                ] = data["id"]
                        except Exception as e:
                            print(e)

            # Event Maps
            print("Event mapping!")
            self._event_maps = {}
            for data in events:
                title = data["name"].lower().strip()
                simplified_title = simplify_title(title)
                self._event_maps[title] = data["id"]
                if simplified_title != title:
                    self._event_maps[simplified_title] = data["id"]
            for data in events_jp:
                title = data["name"].strip()
                self._event_maps[title] = data["id"]
                try:
                    self._event_maps[self.katsu.romaji(title)] = data["id"]
                except:
                    try:
                        new_title = "".join(
                            [self.katsu.romaji(char) for char in [*title]]
                        )
                        self._event_maps[new_title] = data["id"]
                    except:
                        pass
                try:
                    self._event_maps[self.katsu_foreignless.romaji(title)] = data["id"]
                except:
                    try:
                        new_title = "".join(
                            [self.katsu_foreignless.romaji(char) for char in [*title]]
                        )
                        self._event_maps[new_title] = data["id"]
                    except:
                        pass
                # Check if there are custom titles defined for this data["id"]
                # if data["id"] in self.custom_title_definitions:
                #     custom_titles = self.custom_title_definitions[data["id"]]
                #     for custom_title in custom_titles:
                #         self._event_maps[custom_title.lower().strip()] = data["id"]

            # Events
            next_event = False
            now = datetime.datetime.now(datetime.timezone.utc)
            start_at = datetime.datetime.fromtimestamp(
                events[-1]["startAt"] / 1000, datetime.timezone.utc
            )
            if start_at > now:
                next_event = True

            jp_next_event = False
            now = datetime.datetime.now(datetime.timezone.utc)
            start_at = datetime.datetime.fromtimestamp(
                events_jp[-1]["startAt"] / 1000, datetime.timezone.utc
            )
            if start_at > now:
                jp_next_event = True

            self._event_latest = {
                "en": events[-2] if next_event else events[-1],
                "jp": events_jp[-2] if jp_next_event else events_jp[-1],
            }
            self._event_next = {
                "en": events[-1] if next_event else None,
                "jp": events_jp[-1] if jp_next_event else None,
            }
            self._events = {}
            for data in events:
                data["jp"] = False
                data.pop("eventRankingRewardRanges", None)
                self._events[data["id"]] = data
            for data in events_jp:
                data["jp"] = True
                data.pop("eventRankingRewardRanges", None)
                if data["id"] not in self._events:
                    self._events[data["id"]] = data

            index_region_map = {0: "en", 1: "jp", 2: "tw", 3: "kr", 4: "cn"}

            # Event key mapping
            print("Event converter mapping!")
            self.all_events_raw = {}
            for i, events_raw in enumerate(all_da_events):
                region = index_region_map[i]
                for data in events_raw:
                    title = data["name"].lower().strip()
                    add_data = (
                        data
                        if (
                            region == "en"
                            or (data["id"] not in self.all_events_raw.keys())
                        )
                        else self.all_events_raw[data["id"]]
                    )
                    simplified_title = simplify_title(title)
                    if title not in self.all_events_raw:
                        self.all_events_raw[title] = add_data
                        if simplified_title != title:
                            self.all_events_raw[simplified_title] = add_data
                    if region == "jp":
                        name = self.katsu_foreignless.romaji(title)
                        self.all_events_raw[name] = add_data
                        name = self.katsu.romaji(title)
                        self.all_events_raw[name] = data
                    short = data["assetbundleName"].split("_")[1]
                    if short not in self.all_events_raw:
                        self.all_events_raw[short] = add_data
                    if str(data["id"]) not in self.all_events_raw:
                        self.all_events_raw[str(data["id"])] = add_data

            # Songs
            print("Song mapping!")
            self._songs = {}
            self.all_musics_raw = musics[1].copy()  # jp raw first
            for i, songs in enumerate(musics):
                for data in songs:
                    data["exclusive"] = index_region_map[i]
                    if data["id"] not in self._songs:
                        self._songs[data["id"]] = data
                        if i != 1:  # exclusive, but not jp exclusive
                            self.all_musics_raw.append(data)
                    else:
                        self._songs[data["id"]]["exclusive"] = False

            for tag_data in music_tags:
                for tag in tag_data:
                    try:
                        self._songs[tag["musicId"]]["section"] = self._songs[
                            tag["musicId"]
                        ].get("section", [])
                        if self.unit_map[tag["musicTag"]]:
                            if (
                                self.unit_map[tag["musicTag"]]
                                not in self._songs[tag["musicId"]]["section"]
                            ):
                                self._songs[tag["musicId"]]["section"].append(
                                    self.unit_map[tag["musicTag"]]
                                )
                    except Exception as e:
                        print("".join(traceback.format_exception(e)))
                        continue

            # Difficulties
            print("Difficulty mapping!")
            self._difficulties = {}
            for i, songs_difficulties in enumerate(music_difficulties):
                for data in songs_difficulties:
                    if data["musicId"] not in self._difficulties:
                        self._difficulties[data["musicId"]] = {}
                    if (
                        data["musicDifficulty"]
                        not in self._difficulties[data["musicId"]]
                    ):
                        if i != 1:
                            self._difficulties[data["musicId"]][
                                data["musicDifficulty"]
                            ] = data
                    # special JP handling for rerates and appends
                    if i == 1:
                        if (
                            data["musicDifficulty"]
                            not in self._difficulties[data["musicId"]]
                        ):
                            self._difficulties[data["musicId"]][
                                data["musicDifficulty"]
                            ] = data
                            self._difficulties[data["musicId"]][
                                data["musicDifficulty"]
                            ]["jpOnly"] = True
                        elif (
                            self._difficulties[data["musicId"]][
                                data["musicDifficulty"]
                            ]["playLevel"]
                            != data["playLevel"]
                        ):
                            self._difficulties[data["musicId"]][
                                data["musicDifficulty"]
                            ]["playLevel"] = [
                                self._difficulties[data["musicId"]][
                                    data["musicDifficulty"]
                                ]["playLevel"],
                                data["playLevel"],
                            ]

            # Set Refresh Time
            self._refreshed_at = time.time()
        except Exception as e:
            raise e
        self.reload_song_aliases()
        print("Done!")
        self.refreshing.remove(thread_code)

    def _check_refresh(self):
        if self._refreshed_at < time.time() - 3600:  # 3600 seconds = 1 hour
            threading.Thread(target=self.refresh_data, daemon=True).start()

    @property
    def title_maps(self):
        self._check_refresh()
        return self._title_maps

    @property
    def event_maps(self):
        self._check_refresh()
        return self._event_maps

    @property
    def event_latest(self):
        self._check_refresh()
        return self._event_latest

    @property
    def event_next(self):
        self._check_refresh()
        return self._event_next

    @property
    def songs(self):
        self._check_refresh()
        return self._songs

    @property
    def events(self):
        self._check_refresh()
        return self._events

    @property
    def difficulties(self):
        self._check_refresh()
        return self._difficulties

    async def get_custom_title_defs(self):
        async with user_data.db.acquire() as conn:
            query = f"SELECT id, aliases FROM song_aliases;"
            rows = await conn.fetch(query)
            self._defs = json.loads(rows[0]["aliases"])

    @property
    def custom_title_definitions(self):
        defs_mapped = {}
        for id, data in self._defs.items():
            defs_mapped[int(id)] = data["aliases"]
        return defs_mapped

    async def add_song_alias(self, id: int, alias: str):
        if str(id) in self._defs:
            self._defs[str(id)]["aliases"].append(alias.lower())
            self._defs[str(id)]["aliases"] = list(set(self._defs[str(id)]["aliases"]))
        else:
            self._defs[str(id)] = {
                "name": [
                    data["title"]
                    for data in self._songs.values()
                    if int(data["id"]) == id
                ][0],
                "aliases": [alias.lower()],
            }

        async with user_data.db.acquire() as conn:
            # Check if there is at least one row in the table
            row_count = await conn.fetchval("SELECT COUNT(*) FROM song_aliases;")

            if row_count > 0:
                # If there is at least one row, update the existing row
                await conn.execute(
                    """
                    UPDATE song_aliases
                    SET aliases = $1
                    WHERE TRUE;  -- This condition ensures you update the single row
                    """,
                    json.dumps(self._defs),
                )
            else:
                # If no rows exist, insert the first row
                await conn.execute(
                    """
                    INSERT INTO song_aliases (aliases)
                    VALUES ($1);
                    """,
                    json.dumps(self._defs),
                )
        self.reload_song_aliases()

    async def remove_song_alias(self, id: int, alias: str):
        if str(id) in self._defs:
            if alias.lower() in self._defs[str(id)]["aliases"]:
                self._defs[str(id)]["aliases"].remove(alias.lower())
                self._defs[str(id)]["aliases"] = list(
                    set(self._defs[str(id)]["aliases"])
                )
            else:
                return
        else:
            return

        async with user_data.db.acquire() as conn:
            # Check if there is at least one row in the table
            row_count = await conn.fetchval("SELECT COUNT(*) FROM song_aliases;")

            if row_count > 0:
                # If there is at least one row, update the existing row
                await conn.execute(
                    """
                    UPDATE song_aliases
                    SET aliases = $1
                    WHERE TRUE;  -- This condition ensures you update the single row
                    """,
                    json.dumps(self._defs),
                )
            else:
                # If no rows exist, insert the first row
                await conn.execute(
                    """
                    INSERT INTO song_aliases (aliases)
                    VALUES ($1);
                    """,
                    json.dumps(self._defs),
                )
        self.reload_song_aliases()

    def reload_song_aliases(self):
        for data in self._songs.copy().values():
            # Check if there are custom titles defined for this data["id"]
            if int(data["id"]) in self.custom_title_definitions:
                custom_titles = self.custom_title_definitions[int(data["id"])]
                for custom_title in custom_titles:
                    self._title_maps[custom_title.lower().strip()] = int(data["id"])


pjsk = pjsk_data()


class Song:
    def __init__(self, data: dict, difficulties: dict):
        self.data = data
        self.difficulties = difficulties
        self.id = int(self.data["id"])
        self.title = self.data["title"]
        self.aliases = pjsk.custom_title_definitions.get(self.id, [])
        self.zfilled3_id = str(self.id).zfill(3)
        self.zfilled4_id = str(self.id).zfill(4)
        self.exclusive = data.get("exclusive")
        if self.exclusive:
            self.jacket_url = f"https://storage.sekai.best/sekai-{self.exclusive}-assets/music/jacket/jacket_s_{self.zfilled3_id}_rip/jacket_s_{self.zfilled3_id}.webp"
            self.chart_url = f"https://storage.sekai.best/sekai-music-charts/{self.exclusive}/{self.zfilled4_id}/master.png"
        else:
            self.jacket_url = f"https://storage.sekai.best/sekai-en-assets/music/jacket/jacket_s_{self.zfilled3_id}_rip/jacket_s_{self.zfilled3_id}.webp"
            self.chart_url = f"https://storage.sekai.best/sekai-music-charts/en/{self.zfilled4_id}/master.png"
        self.readable = (
            (f"({self.exclusive.upper()} SONG!) " if self.exclusive else "")
            + (
                f"{data.get('title', '')} |     | {', '.join(data.get('section', []))} |     | "
                f"By {' and '.join(', '.join(sorted(set(name.strip() for name in [data.get('composer', ''), data.get('arranger', ''), data.get('lyricist', '')] if name != '-'))).rsplit(', ', 1))} |     |"
            )
            + (
                f" Easy: Lvl {self.difficulties.get('easy', {}).get('playLevel') if not isinstance(self.difficulties.get('easy', {}).get('playLevel'), list) else str(self.difficulties.get('easy', {}).get('playLevel', [])[0]) + ' (JP RERATED ' + str(self.difficulties.get('easy', {}).get('playLevel', [])[1]) + ')'} ({self.difficulties.get('easy', {}).get('totalNoteCount', 0)} notes)"
            )
            + (
                f" - Normal: Lvl {self.difficulties.get('normal', {}).get('playLevel') if not isinstance(self.difficulties.get('normal', {}).get('playLevel'), list) else str(self.difficulties.get('normal', {}).get('playLevel', [])[0]) + ' (JP RERATED ' + str(self.difficulties.get('normal', {}).get('playLevel', [])[1]) + ')'} ({self.difficulties.get('normal', {}).get('totalNoteCount', 0)} notes)"
            )
            + (
                f" - Hard: Lvl {self.difficulties.get('hard', {}).get('playLevel') if not isinstance(self.difficulties.get('hard', {}).get('playLevel'), list) else str(self.difficulties.get('hard', {}).get('playLevel', [])[0]) + ' (JP RERATED ' + str(self.difficulties.get('hard', {}).get('playLevel', [])[1]) + ')'} ({self.difficulties.get('hard', {}).get('totalNoteCount', 0)} notes)"
            )
            + (
                f" - Expert: Lvl {self.difficulties.get('expert', {}).get('playLevel') if not isinstance(self.difficulties.get('expert', {}).get('playLevel'), list) else str(self.difficulties.get('expert', {}).get('playLevel', [])[0]) + ' (JP RERATED ' + str(self.difficulties.get('expert', {}).get('playLevel', [])[1]) + ')'} ({self.difficulties.get('expert', {}).get('totalNoteCount', 0)} notes)"
            )
            + (
                f" - Master: Lvl {self.difficulties.get('master', {}).get('playLevel') if not isinstance(self.difficulties.get('master', {}).get('playLevel'), list) else str(self.difficulties.get('master', {}).get('playLevel', [])[0]) + ' (JP RERATED ' + str(self.difficulties.get('master', {}).get('playLevel', [])[1]) + ')'} ({self.difficulties.get('master', {}).get('totalNoteCount', 0)} notes)"
            )
            + (
                (
                    f" - Append{' (JP ONLY)' if self.difficulties['append'].get('jpOnly') else ''}: Lvl {self.difficulties.get('append', {}).get('playLevel') if not isinstance(self.difficulties.get('append', {}).get('playLevel'), list) else str(self.difficulties.get('append', {}).get('playLevel', [])[0]) + ' (JP RERATED ' + str(self.difficulties.get('append', {}).get('playLevel', [])[1]) + ')'} ({self.difficulties.get('append', {}).get('totalNoteCount', 0)} notes)"
                )
                if self.difficulties.get("append")
                else ""
            )
            + f" |     | https://sekai.best/music/{self.id}"
        )
