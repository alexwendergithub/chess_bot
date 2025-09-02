# tasks.py - Background tasks
from discord.ext import tasks
import asyncio
import logging
from database import get_all_users, store_user_ratings, get_leaderboard_data
from chess_api import fetch_chess_data
import token_bot
import discord

logger = logging.getLogger('chess_bot.tasks')

# Define the task but don't start it yet
@tasks.loop(hours=24)
async def update_ratings(bot):
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
	
	#get users ratings
	users = get_leaderboard_data("overall")
	# Process for overall ratings
	user_ratings = []
	for user in users:
		discord_id, chess_username, rapid, blitz, bullet, puzzle = user
		ratings = [r for r in [rapid, blitz, bullet] if r is not None]
		avg_rating = sum(ratings) / len(ratings) if ratings else 0
		user_ratings.append((discord_id, chess_username, rapid, blitz, bullet, avg_rating))
	
	# Get users sorted by average rating
	user_ratings.sort(key=lambda x: x[5], reverse=True)
	user_ratings = list(enumerate(user_ratings, start=1))
	
	#Setup the bot variables for roles
	logger.info(bot.user)
	guild = bot.get_guild(int(token_bot.MY_GUILD))
	#Loop through 25 first users and set the roles
	top_roles = [["Top 5"], ["Top 10"], ["Top 25"]]
	for role in top_roles:
		role.append(discord.utils.get(guild.roles, name=role[0]))
	print(top_roles)
	for role in top_roles:
		for member in role[1].members:
			try:
				logger.info("removing "+role[0] +" from:"+member.name)
				await member.remove_roles(role[1])
			except:
				continue
	for index, user in user_ratings[:25]:
		discord_id, chess_username, rapid, blitz, bullet, avg_rating = user
		member = guild.get_member(discord_id)
		if member == None:
			try:
				member = await guild.fetch_member(discord_id)  # fallback
			except:
				logger.info(str(index)+":"+chess_username+" not found")
				continue
		if index <= 5:
			try:
				await member.add_roles(top_roles[0][1])
			except:
				continue
			logger.info("top 5:"+chess_username)
		elif index <= 10:
			try:
				await member.add_roles(top_roles[1][1])
			except:
				continue
			logger.info("top 10:"+chess_username)
		elif index <= 25:
			try:
				await member.add_roles(top_roles[2][1])
			except:
				continue
			logger.info("top 25:"+chess_username)

	#logger.info(f"Ratings update complete! Updated {update_count}/{len(users)} users.")
	

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
			update_ratings.start(bot)
