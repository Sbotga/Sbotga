from discord.ext import commands


class Emojis:
    def __init__(self):
        self.append_ap = "append_ap"
        self.append_fc = "append_fc"
        self.append_clear = "append_clear"
        self.append_none = "append_fail"

        self.ap = "normal_ap"
        self.fc = "normal_fc"
        self.clear = "normal_clear"
        self.none = "normal_fail"

        self.difficulty_colors = {
            "easy": "easy_color",
            "normal": "normal_color",
            "hard": "hard_color",
            "expert": "expert_color",
            "master": "master_color",
            "append": "append_color",
        }

        self.attributes = {
            "cool": "icon_attribute_cool",
            "cute": "icon_attribute_cute",
            "happy": "icon_attribute_happy",
            "mysterious": "icon_attribute_mysterious",
            "pure": "icon_attribute_pure",
        }

        self.rarities = {
            "trained": "rarity_star_afterTraining",
            "untrained": "rarity_star_normal",
            "birthday": "rarity_birthday",
        }

        self.sbugacoin = "sbugacoin"

    async def load(self, bot: commands.Bot):
        emojis = await bot.fetch_application_emojis()

        # Load attribute emojis
        for key, emoji_name in self.attributes.copy().items():
            for emoji in emojis:
                if emoji.name == emoji_name:
                    self.attributes[key] = (
                        f"<{'a' if emoji.animated else ''}:{emoji.name}:{emoji.id}>"
                    )

        # Load rarity emojis
        for key, emoji_name in self.rarities.copy().items():
            for emoji in emojis:
                if emoji.name == emoji_name:
                    self.rarities[key] = (
                        f"<{'a' if emoji.animated else ''}:{emoji.name}:{emoji.id}>"
                    )

        # Load difficulty emojis
        for key, emoji_name in self.difficulty_colors.copy().items():
            for emoji in emojis:
                if emoji.name == emoji_name:
                    self.difficulty_colors[key] = (
                        f"<{'a' if emoji.animated else ''}:{emoji.name}:{emoji.id}>"
                    )

        # Load other emojis
        fields = [
            "append_ap",
            "append_fc",
            "append_clear",
            "append_none",
            "ap",
            "fc",
            "clear",
            "none",
            "sbugacoin",
        ]
        for field in fields:
            emoji_name = getattr(self, field)
            for emoji in emojis:
                if emoji.name == emoji_name:
                    setattr(
                        self,
                        field,
                        f"<{'a' if emoji.animated else ''}:{emoji.name}:{emoji.id}>",
                    )


emojis = Emojis()
