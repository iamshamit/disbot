import discord
from typing import List


class PaginatedView(discord.ui.View):
    def __init__(self, embeds: List[discord.Embed], timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.current_page = 0
        self._update_buttons()

    def _update_buttons(self):
        self.first_page.disabled = self.current_page == 0
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page == len(self.embeds) - 1
        self.last_page.disabled = self.current_page == len(self.embeds) - 1

    @discord.ui.button(label="|<", style=discord.ButtonStyle.secondary)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(label="<", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(label=">", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.embeds) - 1:
            self.current_page += 1
            self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(label=">|", style=discord.ButtonStyle.secondary)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = len(self.embeds) - 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)


class ConfirmationView(discord.ui.View):
    def __init__(self, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.value = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        await interaction.response.edit_message(content="Confirmed.", view=None)

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.edit_message(content="Cancelled.", view=None)


class JumpModal(discord.ui.Modal, title="Jump to Page"):
    page_number: discord.ui.TextInput = discord.ui.TextInput(
        label="Page number",
        placeholder="Enter a page number",
        min_length=1,
        max_length=4,
    )

    def __init__(self, target_view: "DynamicPaginationView"):
        super().__init__()
        self.target_view = target_view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            p = int(self.page_number.value) - 1
            self.target_view.page = max(0, min(p, self.target_view.total_pages - 1))
            await interaction.response.edit_message(
                embed=self.target_view.build_embed(), view=self.target_view
            )
        except ValueError:
            await interaction.response.send_message(
                embed=_err_embed("Please enter a valid number."), ephemeral=True
            )


def _err_embed(msg: str):
    from utils.embeds import EmbedBuilder
    return EmbedBuilder.error("Invalid input", msg)


class DynamicPaginationView(discord.ui.View):
    """Base class for stateful list views. Subclass and implement build_embed()."""

    page: int = 0
    total_pages: int = 1
    message: discord.Message | None = None

    def __init__(self):
        super().__init__(timeout=300)

    def build_embed(self) -> discord.Embed:
        raise NotImplementedError

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Page  ?  / ?", style=discord.ButtonStyle.secondary, row=0)
    async def page_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(JumpModal(self))

    @discord.ui.button(label="▶ Next", style=discord.ButtonStyle.secondary, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.total_pages - 1:
            self.page += 1
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    def _refresh_page_btn(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button) and "Page" in item.label:
                item.label = f"Page  {self.page + 1}  /  {self.total_pages}"
                item.disabled = self.total_pages <= 1
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if item.label.startswith("◀"):
                    item.disabled = self.page == 0
                elif item.label.startswith("▶"):
                    item.disabled = self.page >= self.total_pages - 1
