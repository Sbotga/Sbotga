import json


class _CONFIGS:
    """
    Configs to start the bot.
    """

    def __init__(self, errors_dir, cogspath):
        self.error_logs_dir = errors_dir
        self.cogs_dir = cogspath
        self.load()

    def load(self):
        with open(f"config.json", "r", encoding="utf-8") as config:
            configdata = json.load(config)
        self.database_url: str = configdata["database"]
        self.support: str = configdata["support"]
        self.support_id: int = configdata["support_id"]
        self.tokens: dict = configdata["tokens"]
        self.defaultprefix: str = configdata["default_prefix"]
        self.owners: list = configdata["owners"]
        self.discord_owners: list = configdata["discord_owners"]

        with open(f"cheaters.json", "r", encoding="utf-8") as cheaters:
            cheaterdata = json.load(cheaters)
        self.cheaters = cheaterdata

        class api:
            def __init__(self, configdata):
                self._data: dict = configdata["api"]
                self.port: int = self._data["port"]
                self.protected_auth: str = self._data["protected_auth"]
                self.guest_auths: dict = self._data["guest_auths"]

        self.API = api(configdata)

        with open(f"ACHIEVEMENTS/achievements.json", "r", encoding="utf-8") as f:
            self.achievements: dict = json.load(f)


CONFIGS = _CONFIGS(None, None)
