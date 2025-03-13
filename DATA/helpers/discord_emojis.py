class Emojis:
    def __init__(self):
        self.append_ap = "<:append_ap:1330681921256292403>"
        self.append_fc = "<:append_fc:1330682017318178909>"
        self.append_clear = "<:append_clear:1330681981003894894>"
        self.append_none = "<:append_fail:1330682002961076297>"

        self.ap = "<:normal_ap:1330682054525976608>"
        self.fc = "<:normal_fc:1330682098121707540>"
        self.clear = "<:normal_clear:1330682068870627379>"
        self.none = "<:normal_fail:1330682082959032526>"

        self.difficulty_colors = {
            "easy": "<:easy_color:1330682120007319645>",
            "normal": "<:normal_color:1330682194221334619>",
            "hard": "<:hard_color:1330682155541463163>",
            "expert": "<:expert_color:1330682135069327381>",
            "master": "<:master_color:1330682175804149760>",
            "append": "<:append_color:1330682218367942666>",
        }

        self.attributes = {
            "cool": "<:attribute_cool:1330682317773209660>",
            "cute": "<:attribute_cute:1330682341785600092>",
            "happy": "<:attribute_happy:1330682363864416307>",
            "mysterious": "<:attribute_mysterious:1330682381488885892>",
            "pure": "<:attribute_pure:1330682403479621753>",
        }

        self.rarities = {
            "trained": "<:rarity_star_trained:1330682266573078668>",
            "untrained": "<:rarity_star_normal:1330682282977005641>",
            "birthday": "<:rarity_birthday:1330682299234254848>",
        }

        self.sbugacoin = "<a:sbugacoin:1335818074196152393>"


emojis = Emojis()
