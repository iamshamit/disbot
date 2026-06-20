from typing import List
import discord


class AutocompleteIndex:
    def __init__(self, client):
        self.client = client

    def fish_choices(self, current: str) -> List[discord.app_commands.Choice]:
        names = [item.name for item in self.client.fish_by_id.values()]
        matches = [n for n in names if current.lower() in n.lower()]
        return [discord.app_commands.Choice(name=n, value=n) for n in matches[:25]]

    def location_choices(self, current: str) -> List[discord.app_commands.Choice]:
        names = [loc.name for loc in self.client.location_by_id.values()]
        matches = [n for n in names if current.lower() in n.lower()]
        return [discord.app_commands.Choice(name=n, value=n) for n in matches[:25]]
