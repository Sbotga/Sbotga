from discord import app_commands
import discord
from discord.ext import commands

import os, json, re, traceback

from typing import Optional

# CURRENTLY IN PROGRESS (TODO)
# - Translating command names (and groups!)
"""DONE LIST
calculation_service.py
comics.py
gacha.py
dataanalysis.py
achievements.py
events.py
ranked.py
"""
"""TODO LIST
character.py
guessing.py
information.py
song.py
user.py
"""
# - Translating all errors (TODO!!)
# - Translating all responses (MAJOR TODO!! LOW PRIORITY, DO THE FIRST TWO.)


def replace(source: str, rep: dict) -> str:
    """
    A proper way to replace multiple replacements, without making bad replacements.

    EG.
    - abc -> ababc (c -> abc)
    - abc -> abbc (bab -> bb)

    SHOULD BE ababc BECAUSE the original string did NOT have bab in it.
    """
    rep = dict((re.escape(k), v) for k, v in rep.items())
    pattern = re.compile("|".join(rep.keys()))
    source = pattern.sub(lambda m: rep[re.escape(m.group(0))], str(source))
    return source


class SbotgaTranslator(app_commands.Translator):
    async def load(self):
        pass

    async def unload(self):
        pass

    async def translate(
        self,
        string: app_commands.locale_str,
        locale: discord.Locale,
        context: app_commands.TranslationContext,
    ) -> Optional[str]:
        """
        `string` is the string that is requesting to be translated
        `locale` is the target language to translate to
        `context` is the origin of this string, eg TranslationContext.command_name, etc
        This function must return a string (that's been translated), or `None` to signal no available translation available, and will default to the original.
        """
        translated = await translations.translate(
            str(string.message), string.extras, locale.value, context
        )
        return translated


class Translations:
    def __init__(self):
        self.load()

    def reload(self):
        self.load()

    def load(self):
        DIR = "TRANSLATIONS"
        self.translations = {}
        for locale in os.listdir(DIR):
            if not os.path.isdir(locale):
                continue
            with open(f"{DIR}/{locale}/translations.json", "r") as f:
                data = json.load(f)
                # TODO: validation checks
                self.translations[locale] = data

    async def other_context_translate(
        self,
        string: str | app_commands.locale_str,
        message: discord.Message,
        locale: str,
        bot: commands.Bot,
    ) -> str:
        """|coro|

        Translates a string using the set :class:`~discord.app_commands.Translator`.

        .. versionadded:: 2.1

        Parameters
        ----------
        string: Union[:class:`str`, :class:`~discord.app_commands.locale_str`]
            The string to translate.
            :class:`~discord.app_commands.locale_str` can be used to add more context,
            information, or any metadata necessary.
        locale: :class:`Locale`
            The locale to use, this is handy if you want the translation
            for a specific locale.
            Defaults to the user's :attr:`.locale`.
        data: Any
            The extraneous data that is being translated.
            If not specified, either :attr:`.command` or :attr:`.message` will be passed,
            depending on which is available in the context.

        Returns
        --------
        Optional[:class:`str`]
            The translated string, or ``None`` if a translator was not set.
        """
        translator = message
        if not translator:
            return None

        if not isinstance(string, app_commands.locale_str):
            string = app_commands.locale_str(string)

        if isinstance(str, discord.Locale):
            pass
        else:
            locale = discord.Locale(locale)

        context = app_commands.TranslationContext(
            location=app_commands.TranslationContextLocation.other, data=message
        )
        return await bot.tree.translator.translate(
            string, locale=locale, context=context
        )

    async def translate(
        self,
        keys: str,
        extras: dict,
        locale: str,
        context: app_commands.TranslationContext,
    ):
        keys = re.split("\\.|\\-", keys)
        replacements = extras.get("replacements", {})
        try:
            value = self.translations[locale]
            for key in keys:
                value = value[key]
        except KeyError:
            try:
                value = self.translations["en-US"]
                for key in keys:
                    value = value[key]
            except KeyError:
                return None
            except Exception as e:
                traceback.print_exc()
                return "err_tranlation"

        # replace values in value
        if replacements:
            value = replace(value, replacements)

        return value


translations = Translations()
