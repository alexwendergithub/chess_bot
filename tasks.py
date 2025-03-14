# tasks.py - Background tasks
from discord.ext import tasks
import asyncio
import logging
from database import get_all_users, store_user_ratings
from chess_api import fetch_chess_data

logger = logging.getLogger('chess_bot.tasks')

# Define the task but don't start it yet
@tasks.loop(hours=24)
async def update_ratings():
	"""Update ratings for all registered users once per day"""
	logger.info("Starting ratings update...")
	
	users = get_all_users()
	
	update_count = 0
	for discord_id, chess_username in users:
		# Add delay to avoid rate limiting
		await asyncio.sleep(2)
		
		# Fetch new ratings
		chess_data = await fetch_chess_data(chess_username)
		if chess_data:
			if store_user_ratings(discord_id, chess_data):
				update_count += 1
	
	logger.info(f"Ratings update complete! Updated {update_count}/{len(users)} users.")

@update_ratings.before_loop
async def before_update_ratings():
	"""Wait until the bot is ready before starting the task"""
	pass  # This will be replaced in register_tasks

def register_tasks(bot):
	"""Register tasks with the bot"""
	
	# Set the proper before_loop handler with the bot reference
	@update_ratings.before_loop
	async def before_update_ratings():
		await bot.wait_until_ready()
	
	# Add an on_ready event to start the task when the bot is ready
	@bot.event
	async def on_ready():
		logger.info(f'Logged in as {bot.user}')
		try:
			synced = await bot.tree.sync()
			logger.info(f"Synced {len(synced)} command(s)")
		except Exception as e:
			logger.error(f"Failed to sync commands: {e}")
		
		# Start the task here, in the async context
		if not update_ratings.is_running():
			update_ratings.start()
