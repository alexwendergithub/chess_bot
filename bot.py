# bot.py - Bot initialization and core setup
import discord
from discord.ext import commands
import logging

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
    
	# Create bot instance
	bot = commands.Bot(command_prefix="!", intents=intents)
    
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