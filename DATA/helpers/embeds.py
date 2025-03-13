import discord


class SbotgaEmbed(discord.Embed):
    def __init__(
        self,
        *,
        colour=None,
        color=None,
        title=None,
        type="rich",
        url=None,
        description=None,
        timestamp=None,
    ):
        super().__init__(
            colour=colour,
            color=color,
            title=title,
            type=type,
            url=url,
            description=description,
            timestamp=timestamp,
        )

    def set_footer(self, *, text=None, icon_url=None):
        return super().set_footer(text="Sbotga!! " + text, icon_url=icon_url)


def embed(*args, **kwargs):
    if len(args) == 1:
        kwargs["description"] = args[0]
        args = []
    em = SbotgaEmbed(*args, **kwargs)
    em.timestamp = discord.utils.utcnow()
    em.set_footer(text="")
    return em


def error_embed(description: str, title: str = None, color: discord.Color = None):
    return embed(
        title="❌ Error" if not title else f"❌ {title}",
        description=description,
        color=color or discord.Color.red(),
    )


def success_embed(description: str, title: str = None, color: discord.Color = None):
    return embed(
        title="✅ Success" if not title else f"✅ {title}",
        description=description,
        color=color or discord.Color.green(),
    )


def warn_embed(description: str, title: str = None, color: discord.Color = None):
    return embed(
        title="⚠️ Warning" if not title else f"⚠️ {title}",
        description=description,
        color=color or discord.Color.orange(),
    )


def leak_embed():
    em = error_embed(f"Is that a leak? Have a leek instead.")
    em.set_image(
        url="https://cdn.loveandlemons.com/wp-content/uploads/opengraph/2020/11/leek-1.jpg"
    )
    return em
