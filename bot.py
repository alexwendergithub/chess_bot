# bot.py - Bot initialization and core setup
import discord
from discord.ext import commands
import logging
import token_bot

# Configure logging
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('chess_bot')

def setup_bot():
	"""Initialize and configure the bot"""
	# Set up intents
	intents = discord.Intents.default()
	intents.message_content = True

	GUILD = discord.Object(id=token_bot.MY_GUILD)
	class MyClient(discord.Client):
		def __init__(self, *, intents: discord.Intents):
			super().__init__(intents=intents)
			# A CommandTree is a special type that holds all the application command
			# state required to make it work. This is a separate class because it
			# allows all the extra state to be opt-in.
			# Whenever you want to work with application commands, your tree is used
			# to store and work with them.
			# Note: When using commands.Bot instead of discord.Client, the bot will
			# maintain its own tree instead.
			self.tree = discord.app_commands.CommandTree(self)

		# In this basic example, we just synchronize the app commands to one guild.
		# Instead of specifying a guild to every command, we copy over our global commands instead.
		# By doing so, we don't have to wait up to an hour until they are shown to the end-user.
		async def setup_hook(self):
			# This copies the global commands over to your guild.
			self.tree.copy_global_to(guild=GUILD)
			await self.tree.sync(guild=GUILD)


	
	# Create bot instance
	bot = MyClient(intents=intents)

	# Register event handlers
	@bot.event
	async def on_ready():
		logger.info(f'Logged in as {bot.user}')
		try:
			synced = await bot.tree.sync()
			logger.info(f"Synced {len(synced)} command(s)")
		except Exception as e:
			logger.error(f"Failed to sync commands: {e}")
	
	# Import and add commands
	from commands import register_commands
	register_commands(bot)
	
	return bot