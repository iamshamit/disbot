from typing import List
import discord


class EmbedPaginator:
    def __init__(self, base_embed: discord.Embed, items: List[str], per_page: int = 10):
        self.base_embed = base_embed
        self.items = items
        self.per_page = per_page

    def build_embeds(self) -> List[discord.Embed]:
        pages = []
        for i in range(0, len(self.items), self.per_page):
            embed = self.base_embed.copy()
            chunk = self.items[i : i + self.per_page]
            embed.description = "\n".join(chunk) or "No items."
            embed.set_footer(text=f"Page {len(pages) + 1}/{(len(self.items) + self.per_page - 1) // self.per_page}")
            pages.append(embed)
        return pages or [self.base_embed.copy()]
