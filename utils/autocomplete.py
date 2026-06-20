from typing import List
import discord


class AutocompleteIndex:
    def __init__(self, client):
        self.client = client

    def _choices(self, names: list[str], current: str) -> List[discord.app_commands.Choice]:
        matches = [n for n in names if current.lower() in n.lower()]
        return [discord.app_commands.Choice(name=n, value=n) for n in matches[:25]]

    def fish_choices(self, current: str) -> List[discord.app_commands.Choice]:
        return self._choices([c.name for c in self.client.fish_by_id.values()], current)

    def location_choices(self, current: str) -> List[discord.app_commands.Choice]:
        return self._choices([l.name for l in self.client.location_by_id.values()], current)

    def tool_choices(self, current: str) -> List[discord.app_commands.Choice]:
        return self._choices([t.name for t in self.client.tool_by_id.values()], current)

    def bait_choices(self, current: str) -> List[discord.app_commands.Choice]:
        return self._choices([b.name for b in self.client.bait_by_id.values()], current)

    def npc_choices(self, current: str) -> List[discord.app_commands.Choice]:
        return self._choices([n.name for n in self.client.npc_by_id.values()], current)
