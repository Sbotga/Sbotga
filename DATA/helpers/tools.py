import string, secrets

import discord


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
