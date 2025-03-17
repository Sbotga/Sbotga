import discord
from discord.ext import commands, tasks
from discord import app_commands

from discord.app_commands import locale_str
from COGS.discord_translations import translations

from main import DiscordBot

import time, os, random
from io import BytesIO

from PIL import Image

from DATA.helpers import discord_autocompletes as autocompletes
from DATA.helpers import embeds

from DATA.game_api import methods


class GachaCog(commands.Cog):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

        self.cooldown = {}

        self.cog_tasks.start()

    def cog_unload(self):
        """Cancel the task to prevent orphaned tasks."""
        self.cog_tasks.cancel()

    @tasks.loop(seconds=60)
    async def cog_tasks(self):
        for uid, last_ran in list(self.cooldown.items()):
            if time.time() - last_ran > 120:  # 2 minutes
                self.cooldown.pop(uid, None)

    def gachacardthumnail(
        self, card_id: int, trained: bool = False, cards: dict = None
    ) -> Image:
        if cards is None:
            cards = methods.pjsk_game_api_jp.get_master_data("cards.json")
        if trained:
            suffix = "after_training"
        else:
            suffix = "normal"
        for card in cards:
            if card["id"] == card_id:
                if (
                    card["cardRarityType"] != "rarity_3"
                    and card["cardRarityType"] != "rarity_4"
                ):
                    suffix = "normal"
                pic = Image.new("RGBA", (338, 338), (0, 0, 0, 0))
                card_pic_path = os.path.join(
                    methods.pjsk_game_api_jp.game_files_path,
                    "jp",
                    "character",
                    "member_cutout",
                    card["assetbundleName"] + "_ex",
                    f"{suffix}.png",
                )
                cardpic = Image.open(card_pic_path)
                picmask = Image.open(f"DATA/data/ASSETS/gachacardmask.png")
                r, g, b, mask = picmask.split()
                cardpic = cardpic.resize(mask.size, Image.Resampling.LANCZOS)
                pic.paste(cardpic, (0, 0), mask)
                cardFrame = Image.open(
                    f'DATA/data/ASSETS/chara/cardFrame_{card["cardRarityType"]}.png'
                )
                cardFrame = cardFrame.resize((338, 338))
                r, g, b, mask = cardFrame.split()

                pic.paste(cardFrame, (0, 0), mask)
                if card["cardRarityType"] == "rarity_1":
                    star = Image.open(f"DATA/data/ASSETS/chara/rarity_star_normal.png")
                    star = star.resize((61, 61))
                    r, g, b, mask = star.split()
                    pic.paste(star, (21, 256), mask)
                if card["cardRarityType"] == "rarity_2":
                    star = Image.open(f"DATA/data/ASSETS/chara/rarity_star_normal.png")
                    star = star.resize((60, 60))
                    r, g, b, mask = star.split()
                    pic.paste(star, (21, 256), mask)
                    pic.paste(star, (78, 256), mask)
                if card["cardRarityType"] == "rarity_3":
                    if trained:
                        star = Image.open(
                            f"DATA/data/ASSETS/chara/rarity_star_afterTraining.png"
                        )
                    else:
                        star = Image.open(
                            f"DATA/data/ASSETS/chara/rarity_star_normal.png"
                        )
                    star = star.resize((60, 60))
                    r, g, b, mask = star.split()
                    pic.paste(star, (21, 256), mask)
                    pic.paste(star, (78, 256), mask)
                    pic.paste(star, (134, 256), mask)
                if card["cardRarityType"] == "rarity_4":
                    if trained:
                        star = Image.open(
                            f"DATA/data/ASSETS/chara/rarity_star_afterTraining.png"
                        )
                    else:
                        star = Image.open(
                            f"DATA/data/ASSETS/chara/rarity_star_normal.png"
                        )
                    star = star.resize((60, 60))
                    r, g, b, mask = star.split()
                    pic.paste(star, (21, 256), mask)
                    pic.paste(star, (78, 256), mask)
                    pic.paste(star, (134, 256), mask)
                    pic.paste(star, (190, 256), mask)
                if card["cardRarityType"] == "rarity_birthday":
                    star = Image.open(f"DATA/data/ASSETS/chara/rarity_birthday.png")
                    star = star.resize((60, 60))
                    r, g, b, mask = star.split()
                    pic.paste(star, (21, 256), mask)
                attr = Image.open(
                    f'DATA/data/ASSETS/chara/icon_attribute_{card["attr"]}.png'
                )
                attr = attr.resize((76, 76))
                r, g, b, mask = attr.split()
                pic.paste(attr, (1, 1), mask)
                return pic

    def gachapic(self, charas) -> BytesIO:
        pic = Image.open(f"DATA/data/ASSETS/gacha.png")
        cards = methods.pjsk_game_api_jp.get_master_data("cards.json")
        cover = Image.new("RGB", (1550, 600), (255, 255, 255))
        pic.paste(cover, (314, 500))
        for i in range(0, 5):
            cardpic = self.gachacardthumnail(charas[i], False, cards)
            cardpic = cardpic.resize((263, 263))
            r, g, b, mask = cardpic.split()
            pic.paste(cardpic, (336 + 304 * i, 520), mask)
        for i in range(0, 5):
            cardpic = self.gachacardthumnail(charas[i + 5], False, cards)
            cardpic = cardpic.resize((263, 263))
            r, g, b, mask = cardpic.split()
            pic.paste(cardpic, (336 + 304 * i, 825), mask)
        pic = pic.convert("RGB")
        obj = BytesIO()
        pic.save(obj, "JPEG")
        obj.seek(0)
        return obj

    def getcharaname(self, region: str, character_id: int):
        api = methods.Tools.get_api(region)
        data = api.get_master_data("gameCharacters.json")
        for i in data:
            if i["id"] == character_id:
                try:
                    if region == "jp":
                        return i["firstName"] + i["givenName"]
                    else:
                        return i["givenName"] + i["firstName"]
                except KeyError:
                    return i["givenName"]

    def fakegacha(
        self, region: str, gacha_id: int, reverse: bool = False
    ) -> None | BytesIO:
        api = methods.Tools.get_api(region)
        data = api.get_master_data("gachas.json")
        gacha = None
        birthday = False
        for i in range(0, len(data)):
            if data[i]["id"] == gacha_id:
                gacha = data[i]
        if gacha is None:
            return None
        rate4 = 0
        rate3 = 0
        for i in range(0, len(gacha["gachaCardRarityRates"])):
            if gacha["gachaCardRarityRates"][i]["cardRarityType"] == "rarity_4":
                rate4 = gacha["gachaCardRarityRates"][i]["rate"]
                break
            if gacha["gachaCardRarityRates"][i]["cardRarityType"] == "rarity_birthday":
                rate4 = gacha["gachaCardRarityRates"][i]["rate"]
                birthday = True
                break
        for i in range(0, len(gacha["gachaCardRarityRates"])):
            if gacha["gachaCardRarityRates"][i]["cardRarityType"] == "rarity_3":
                rate3 = gacha["gachaCardRarityRates"][i]["rate"]
        if reverse:
            rate4 = 100 - rate4 - rate3
        cards = api.get_master_data("cards.json")
        reality2 = []
        reality3 = []
        reality4 = []
        allweight = 0
        for detail in gacha["gachaDetails"]:
            for card in cards:
                if card["id"] == detail["cardId"]:
                    if card["cardRarityType"] == "rarity_2":
                        reality2.append(
                            {
                                "id": card["id"],
                                "prefix": card["prefix"],
                                "charaid": card["characterId"],
                            }
                        )
                    elif card["cardRarityType"] == "rarity_3":
                        reality3.append(
                            {
                                "id": card["id"],
                                "prefix": card["prefix"],
                                "charaid": card["characterId"],
                            }
                        )
                    else:
                        allweight = allweight + detail["weight"]
                        reality4.append(
                            {
                                "id": card["id"],
                                "prefix": card["prefix"],
                                "charaid": card["characterId"],
                                "weight": detail["weight"],
                            }
                        )
        alltext = ""
        keytext = ""
        baodi = True
        count4 = 0
        count3 = 0
        count2 = 0
        result = []
        for i in range(1, 11):
            if i % 10 == 0 and baodi and reverse is not True:
                baodi = False
                rannum = random.randint(0, int(rate4 + rate3) * 2) / 2
            else:
                rannum = random.randint(0, 100)
            if rannum < rate4:
                count4 += 1
                baodi = False
                nowweight = 0
                rannum2 = random.randint(0, allweight - 1)
                for j in range(0, len(reality4)):
                    nowweight = nowweight + reality4[j]["weight"]
                    if nowweight >= rannum2:
                        if birthday:
                            alltext = alltext + "🎀"
                            keytext = keytext + "🎀"
                        else:
                            alltext = alltext + "★★★★"
                            keytext = keytext + "★★★★"
                        if reality4[j]["weight"] == 400000:
                            alltext = alltext + "[当期]"
                            keytext = keytext + "[当期]"
                        alltext = (
                            alltext
                            + f"{reality4[j]['prefix']} - {self.getcharaname(region, reality4[j]['charaid'])}\n"
                        )
                        keytext = (
                            keytext
                            + f"{reality4[j]['prefix']} - {self.getcharaname(region, reality4[j]['charaid'])}(第{i}抽)\n"
                        )
                        result.append(reality4[j]["id"])
                        break
            elif rannum < rate4 + rate3:
                count3 += 1
                rannum2 = random.randint(0, len(reality3) - 1)
                alltext = (
                    alltext
                    + f"★★★{reality3[rannum2]['prefix']} - {self.getcharaname(region, reality3[rannum2]['charaid'])}\n"
                )
                result.append(reality3[rannum2]["id"])
            else:
                count2 += 1
                rannum2 = random.randint(0, len(reality3) - 1)
                alltext = (
                    alltext
                    + f"★★{reality2[rannum2]['prefix']} - {self.getcharaname(region, reality2[rannum2]['charaid'])}\n"
                )
                result.append(reality2[rannum2]["id"])

        return self.gachapic(result)

    @app_commands.command(
        auto_locale_strings=False,
        name=locale_str("gacha", key="gacha.name", file="commands"),
        description=locale_str("gacha.desc", file="commands"),
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.autocomplete(
        region=autocompletes.autocompletes.pjsk_region(["en", "jp", "tw", "kr", "cn"])
    )
    @app_commands.describe(
        region=locale_str("general.region"),
        reverse_odds=locale_str("gacha.describes.reverse_odds", file="commands"),
    )
    async def gacha(
        self,
        interaction: discord.Interaction,
        region: str = "default",
        reverse_odds: bool = False,
    ):
        region = region.lower().strip()
        if region not in ["en", "jp", "tw", "kr", "cn", "default"]:
            return await interaction.response.send_message(
                embed=embeds.error_embed("Unsupported region."), ephemeral=True
            )
        sub_level = await self.bot.subscribed(interaction.user)
        current_time = time.time()
        if sub_level < 2:
            cooldown_end = self.cooldown.get(interaction.user.id, 0) + 20  # 20 seconds
            if cooldown_end > current_time:
                embed = embeds.error_embed(
                    (
                        f"You recently ran a gacha. Try again <t:{int(cooldown_end)}:R>.\n"
                        f"-# 20 second cooldown. Donate to remove the cooldown. See </donate:1326321351417528442>"
                    )
                )
                return await interaction.response.send_message(
                    embed=embed, ephemeral=True
                )
        else:
            pass
        self.cooldown[interaction.user.id] = time.time()
        await interaction.response.defer(ephemeral=False, thinking=True)
        if region == "default":
            region = await self.bot.user_data.discord.get_settings(
                interaction.user.id, "default_region"
            )
        api = methods.Tools.get_api(region)
        gacha_data = api.get_current_gacha()

        img = self.fakegacha(region, int(gacha_data["id"]), reverse_odds)

        embed = embeds.embed(title=f"Ten Pull - {gacha_data['name']}")

        file = discord.File(img, "image.png")
        embed.set_image(url="attachment://image.png")
        embed.set_footer(text=f"{region.upper()} Current Event Gacha Pull")
        await interaction.followup.send(embed=embed, file=file)
        self.cooldown[interaction.user.id] = time.time()


async def setup(bot: DiscordBot):
    await bot.add_cog(GachaCog(bot))
