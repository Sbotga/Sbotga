import string, secrets

import discord
from discord.ext import commands


def generate_secure_string(length):
    alphabet = string.ascii_letters + string.digits
    secure_string = "".join(secrets.choice(alphabet) for _ in range(length))
    return secure_string


def escape_md(text, markdown: bool = True, mentions: bool = True) -> str:
    if markdown:
        text = discord.utils.escape_markdown(text)
    if mentions:
        text = discord.utils.escape_mentions(text).replace("<#", "<#\u200b")
    return text


def command_mention(bot: commands.Bot, name: str) -> str | None:
    """
    Get a command mention from its name. Also will update ID cache
    """
    commands: list[discord.app_commands.AppCommand] = bot.app_commands
    for cmd in commands:
        if cmd.guild_id is None:  # it's a global slash command
            bot.tree._global_commands[cmd.name].id = cmd.id
        else:  # it's a guild specific command
            bot.tree._guild_commands[cmd.guild_id][cmd.name].id = cmd.id
    for cmd in bot.tree.get_commands():
        if cmd.qualified_name == name:
            return f"</{cmd.qualified_name}:{cmd.id}>"
    return None
