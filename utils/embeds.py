import discord


class EmbedBuilder:
    DEFAULT_COLOR = 0x2F3136
    ERROR_COLOR = 0xED4245
    SUCCESS_COLOR = 0x57F287
    WARNING_COLOR = 0xFEE75C
    INFO_COLOR = 0x5865F2

    @staticmethod
    def _base(title: str = None, description: str = None, color: int = DEFAULT_COLOR):
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text="DankFishingBot")
        return embed

    @classmethod
    def info(cls, title: str, description: str = None):
        return cls._base(title=title, description=description, color=cls.INFO_COLOR)

    @classmethod
    def error(cls, title: str = "Something went wrong", description: str = None):
        embed = cls._base(title=f"\u274c {title}", description=description, color=cls.ERROR_COLOR)
        return embed

    @classmethod
    def success(cls, title: str, description: str = None):
        return cls._base(title=f"\u2705 {title}", description=description, color=cls.SUCCESS_COLOR)

    @classmethod
    def warning(cls, title: str, description: str = None):
        return cls._base(title=f"\u26a0\ufe0f {title}", description=description, color=cls.WARNING_COLOR)
