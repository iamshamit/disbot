import pytest
import discord
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# DynamicPaginationView
# ---------------------------------------------------------------------------

class ConcreteView(discord.ui.View):
    """Minimal concrete subclass for testing without needing full discord runtime."""
    pass


def make_dynamic_view(page=0, total_pages=3):
    from utils.views import DynamicPaginationView

    class TestView(DynamicPaginationView):
        def build_embed(self):
            e = discord.Embed(title=f"Page {self.page + 1}")
            return e

    v = TestView()
    v.page = page
    v.total_pages = total_pages
    return v


# --- Class attributes ---

def test_dynamic_view_defaults():
    from utils.views import DynamicPaginationView
    v = make_dynamic_view()
    assert v.timeout == 300
    assert v.message is None


def test_dynamic_view_page_attribute():
    v = make_dynamic_view(page=1, total_pages=5)
    assert v.page == 1
    assert v.total_pages == 5


def test_build_embed_not_implemented_on_base():
    from utils.views import DynamicPaginationView
    v = DynamicPaginationView()
    with pytest.raises(NotImplementedError):
        v.build_embed()


# --- _refresh_page_btn ---

def test_refresh_page_btn_updates_label():
    v = make_dynamic_view(page=1, total_pages=3)
    v._refresh_page_btn()
    page_labels = [
        item.label for item in v.children
        if isinstance(item, discord.ui.Button) and "Page" in item.label
    ]
    assert len(page_labels) == 1
    assert "2" in page_labels[0]
    assert "3" in page_labels[0]


def test_refresh_page_btn_disables_page_btn_when_single_page():
    v = make_dynamic_view(page=0, total_pages=1)
    v._refresh_page_btn()
    page_btn = next(
        item for item in v.children
        if isinstance(item, discord.ui.Button) and "Page" in item.label
    )
    assert page_btn.disabled is True


def test_refresh_page_btn_enables_page_btn_when_multiple_pages():
    v = make_dynamic_view(page=0, total_pages=3)
    v._refresh_page_btn()
    page_btn = next(
        item for item in v.children
        if isinstance(item, discord.ui.Button) and "Page" in item.label
    )
    assert page_btn.disabled is False


def test_refresh_page_btn_disables_prev_on_first_page():
    v = make_dynamic_view(page=0, total_pages=3)
    v._refresh_page_btn()
    prev_btn = next(
        item for item in v.children
        if isinstance(item, discord.ui.Button) and item.label.startswith("◀")
    )
    assert prev_btn.disabled is True


def test_refresh_page_btn_enables_prev_on_later_page():
    v = make_dynamic_view(page=1, total_pages=3)
    v._refresh_page_btn()
    prev_btn = next(
        item for item in v.children
        if isinstance(item, discord.ui.Button) and item.label.startswith("◀")
    )
    assert prev_btn.disabled is False


def test_refresh_page_btn_disables_next_on_last_page():
    v = make_dynamic_view(page=2, total_pages=3)
    v._refresh_page_btn()
    next_btn = next(
        item for item in v.children
        if isinstance(item, discord.ui.Button) and item.label.startswith("▶")
    )
    assert next_btn.disabled is True


def test_refresh_page_btn_enables_next_when_not_last():
    v = make_dynamic_view(page=0, total_pages=3)
    v._refresh_page_btn()
    next_btn = next(
        item for item in v.children
        if isinstance(item, discord.ui.Button) and item.label.startswith("▶")
    )
    assert next_btn.disabled is False


# --- on_timeout ---

@pytest.mark.asyncio
async def test_on_timeout_disables_children():
    v = make_dynamic_view()
    v.message = None
    await v.on_timeout()
    for item in v.children:
        assert item.disabled is True  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_on_timeout_edits_message_if_set():
    v = make_dynamic_view()
    mock_msg = AsyncMock()
    v.message = mock_msg
    await v.on_timeout()
    mock_msg.edit.assert_called_once_with(view=v)


@pytest.mark.asyncio
async def test_on_timeout_ignores_edit_error():
    v = make_dynamic_view()
    mock_msg = AsyncMock()
    mock_msg.edit.side_effect = Exception("Network error")
    v.message = mock_msg
    # Should not raise
    await v.on_timeout()


# ---------------------------------------------------------------------------
# JumpModal
# ---------------------------------------------------------------------------

def make_jump_modal(page=0, total_pages=5):
    from utils.views import JumpModal
    v = make_dynamic_view(page=page, total_pages=total_pages)
    return JumpModal(v), v


def test_jump_modal_stores_target_view():
    modal, v = make_jump_modal()
    assert modal.target_view is v


def test_jump_modal_has_page_number_input():
    from utils.views import JumpModal
    modal, _ = make_jump_modal()
    assert hasattr(modal, "page_number")
    assert isinstance(modal.page_number, discord.ui.TextInput)


@pytest.mark.asyncio
async def test_jump_modal_on_submit_valid_page():
    modal, v = make_jump_modal(page=0, total_pages=5)
    modal.page_number._value = "3"

    interaction = MagicMock()
    interaction.response = AsyncMock()
    interaction.response.edit_message = AsyncMock()

    await modal.on_submit(interaction)

    assert v.page == 2  # "3" -> index 2
    interaction.response.edit_message.assert_called_once()


@pytest.mark.asyncio
async def test_jump_modal_on_submit_clamps_below_zero():
    modal, v = make_jump_modal(page=2, total_pages=5)
    modal.page_number._value = "-5"

    interaction = MagicMock()
    interaction.response = AsyncMock()
    interaction.response.edit_message = AsyncMock()

    await modal.on_submit(interaction)

    assert v.page == 0


@pytest.mark.asyncio
async def test_jump_modal_on_submit_clamps_above_max():
    modal, v = make_jump_modal(page=0, total_pages=5)
    modal.page_number._value = "999"

    interaction = MagicMock()
    interaction.response = AsyncMock()
    interaction.response.edit_message = AsyncMock()

    await modal.on_submit(interaction)

    assert v.page == 4  # total_pages - 1


@pytest.mark.asyncio
async def test_jump_modal_on_submit_invalid_sends_ephemeral():
    modal, v = make_jump_modal()
    modal.page_number._value = "not_a_number"

    interaction = MagicMock()
    interaction.response = AsyncMock()
    interaction.response.send_message = AsyncMock()

    await modal.on_submit(interaction)

    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_jump_modal_on_submit_page_1_is_index_0():
    modal, v = make_jump_modal(page=2, total_pages=5)
    modal.page_number._value = "1"

    interaction = MagicMock()
    interaction.response = AsyncMock()
    interaction.response.edit_message = AsyncMock()

    await modal.on_submit(interaction)

    assert v.page == 0
