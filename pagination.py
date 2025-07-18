import discord
from typing import Callable, Optional


class Pagination(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, get_page: Callable,users,category_value=None):
        self.interaction = interaction
        self.get_page = get_page
        self.users = users
        self.total_pages: Optional[int] = None
        self.index = 1
        self.msg = None
        self.category_value = category_value
        super().__init__(timeout=100)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.interaction.user:
            return True
        else:
            emb = discord.Embed(
                description=f"Only the author of the command can perform this action.",
                color=16711680
            )
            await interaction.response.send_message(embed=emb, ephemeral=True)
            return False

    async def navegate(self):
        if self.category_value != None:
            emb, self.total_pages = await self.get_page(self.index,self.users,self.category_value)
        else:
            emb, self.total_pages = await self.get_page(self.index,self.users)
        if self.total_pages == 1:
            self.msg = await self.interaction.followup.send(embed=emb)
        elif self.total_pages > 1:
            self.update_buttons()
            self.msg = await self.interaction.followup.send(embed=emb, view=self)

    async def edit_page(self, interaction: discord.Interaction):
        if self.category_value != None:
            emb, self.total_pages = await self.get_page(self.index,self.users,self.category_value)
        else:
            emb, self.total_pages = await self.get_page(self.index,self.users)
        self.update_buttons()
        await self.msg.edit(embed=emb, view=self)

    def update_buttons(self):
        if self.index > self.total_pages // 2:
            self.children[2].emoji = "⏮️"
        else:
            self.children[2].emoji = "⏭️"
        self.children[0].disabled = self.index == 1
        self.children[1].disabled = self.index == self.total_pages

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.blurple)
    async def previous(self, interaction: discord.Interaction, button: discord.Button):
        self.index -= 1
        await self.edit_page(interaction)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: discord.Interaction, button: discord.Button):
        self.index += 1
        await self.edit_page(interaction)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.blurple)
    async def end(self, interaction: discord.Interaction, button: discord.Button):
        if self.index <= self.total_pages//2:
            self.index = self.total_pages
        else:
            self.index = 1
        await self.edit_page(interaction)

    async def on_timeout(self):
        # remove buttons on timeout
        message = await self.interaction.original_response()
        await message.edit(view=None)

    @staticmethod
    def compute_total_pages(total_results: int, results_per_page: int) -> int:
        return ((total_results - 1) // results_per_page) + 1
