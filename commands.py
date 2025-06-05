# commands.py - Bot commands
import discord
from discord import app_commands
import datetime
import logging
from database import (register_user, unregister_user, store_user_ratings,
				 	get_user_profile, get_leaderboard_data)
from chess_api import fetch_chess_data, calculate_average_rating

logger = logging.getLogger('chess_bot.commands')

def register_commands(bot):
	"""Register all commands with the bot"""
	
	@bot.tree.command(name="register", description="Register your Chess.com username")
	@app_commands.describe(username="Your Chess.com username")
	async def register(interaction: discord.Interaction, username: str):
		await interaction.response.defer(ephemeral=True)
		 
		# Check if username exists on Chess.com
		chess_data = await fetch_chess_data(username)
		if not chess_data:
			await interaction.followup.send(f"Could not find Chess.com user '{username}'. Please check the spelling.", ephemeral=True)
			return
		 
		# Register user
		result = register_user(interaction.user.id, username)
		 
		# Store ratings
		if store_user_ratings(interaction.user.id, chess_data):
			if result == "updated":
				await interaction.followup.send(f"Updated your Chess.com username to {username}!", ephemeral=True)
			else:
				await interaction.followup.send(f"Successfully registered with Chess.com username {username}!", ephemeral=True)
		else:
			await interaction.followup.send("Registration successful but there was an error storing your ratings. Please try refreshing later.", ephemeral=True)

	@bot.tree.command(name="admin_register", description="Register a Chess.com username")
	@app_commands.describe(username="Your Chess.com username")
	async def admin_register(interaction: discord.Interaction, username: str,discord_id: int):
		await interaction.response.defer(ephemeral=True)
		if interaction.user.id != 896650341561548801:
			interaction.followup.send(f"Only admins are allowed to execute this command",ephemeral=True)
		# Check if username exists on Chess.com
		chess_data = await fetch_chess_data(username)
		if not chess_data:
			await interaction.followup.send(f"Could not find Chess.com user '{username}'. Please check the spelling.", ephemeral=True)
			return
		 
		# Register user
		result = register_user(discord_id, username)
		 
		# Store ratings
		if store_user_ratings(discord_id, chess_data):
			if result == "updated":
				await interaction.followup.send(f"Updated Chess.com username to {username}!", ephemeral=True)
			else:
				await interaction.followup.send(f"Successfully registered Chess.com username {username}!", ephemeral=True)
		else:
			await interaction.followup.send("Registration successful but there was an error storing ratings. Please try refreshing later.", ephemeral=True)

	@bot.tree.command(name="admin_unregister", description="Remove yourself from the Chess.com leaderboard")
	async def admin_unregister(interaction: discord.Interaction, username: str):
		if unregister_user_chess_com(username):
			await interaction.response.send_message("You have been removed from the Chess.com leaderboard.", ephemeral=True)
		else:
			await interaction.response.send_message("You are not registered in the leaderboard.", ephemeral=True)

	@bot.tree.command(name="unregister", description="Remove yourself from the Chess.com leaderboard")
	async def unregister(interaction: discord.Interaction):
		if unregister_user(interaction.user.id):
			await interaction.response.send_message("You have been removed from the Chess.com leaderboard.", ephemeral=True)
		else:
			await interaction.response.send_message("You are not registered in the leaderboard.", ephemeral=True)
	
	@bot.tree.command(name="leaderboard", description="Show Chess.com ratings leaderboard")
	@app_commands.describe(category="Rating category to display")
	@app_commands.choices(category=[
		app_commands.Choice(name="Rapid", value="rapid"),
		app_commands.Choice(name="Blitz", value="blitz"),
		app_commands.Choice(name="Bullet", value="bullet"),
		app_commands.Choice(name="Puzzle", value="puzzle"),
		app_commands.Choice(name="Puzzle Rush", value="puzzle_rush"),
		app_commands.Choice(name="Overall", value="overall")
	])
	async def leaderboard(interaction: discord.Interaction, category: app_commands.Choice[str]):
		await interaction.response.defer()
		 
		category_value = category.value
		users = get_leaderboard_data(category_value)
		if category_value == "puzzle_rush":

			# Create embed
			embed = discord.Embed(
				title="Chess.com Puzzle Rush Leaderboard",
				description="Top puzzle rush survival scores",
				color=0x00BFFF,
				timestamp=datetime.datetime.now()
			)
			
			# Add trophy emoji for top 3
			trophies = ["🏆", "🥈", "🥉"]
			
			for index, user in enumerate(users, start=1):
				discord_id, chess_username, score = user
				
				# Add trophy emoji for top 3
				prefix = f"{trophies[index-1]} " if index <= 3 else f"{index}. "
				if index == 26:
					break
				embed.add_field(
					name=f"{prefix}{chess_username}",
					value=f"Score: **{score}**",
					inline=False
				)
			# Add footer
			embed.set_footer(text=f"Last updated • {datetime.datetime.now().strftime('%Y-%m-%d')}")
			
			# Add thumbnail
			embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/5987/5987898.png")
		
		elif category_value == "overall":
			# Process for overall ratings
			user_ratings = []
			for user in users:
				discord_id, chess_username, rapid, blitz, bullet, puzzle = user
				ratings = [r for r in [rapid, blitz, bullet] if r is not None]
				avg_rating = sum(ratings) / len(ratings) if ratings else 0
				user_ratings.append((discord_id, chess_username, rapid, blitz, bullet, avg_rating))
			 
			# Sort by average rating
			user_ratings.sort(key=lambda x: x[5], reverse=True)
			 
			# Create embed
			embed = discord.Embed(
				title="Overall Chess.com Ratings Leaderboard",
				description="Average of all available ratings",
				color=0x00BFFF,
				timestamp=datetime.datetime.now()
			)
			
			# Add trophy emoji for top 3
			trophies = ["🏆", "🥈", "🥉"]

			for index, user in enumerate(user_ratings, start=1):
				discord_id, chess_username, rapid, blitz, bullet, avg_rating = user
				 
				# Add trophy emoji for top 3
				prefix = f"{trophies[index-1]} " if index <= 3 else f"{index}. "
				if index == 26:
					break
				embed.add_field(
					name=f"{prefix}. {chess_username}",
					value=f"Average: **{int(avg_rating)}**\n"
					  	f"Rapid: {rapid or 'N/A'} | Blitz: {blitz or 'N/A'} | "
					  	f"Bullet: {bullet or 'N/A'}",
					inline=False
				)

			# Add thumbnail
			embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/5987/5987898.png")
		else:
			# Process for specific category
			# Filter out None values and sort
			filtered_users = [(u[0], u[1], u[2]) for u in users if u[2] is not None]
			filtered_users.sort(key=lambda x: x[2], reverse=True)
			 
			# Create embed
			embed = discord.Embed(
				title=f"Chess.com {category_value.capitalize()} Ratings Leaderboard",
				color=0x00BFFF,
				timestamp=datetime.datetime.now()
			)
			
			# Add trophy emoji for top 3
			trophies = ["🏆", "🥈", "🥉"]

			for index, user in enumerate(filtered_users, start=1):
				discord_id, chess_username, rating = user

				# Add trophy emoji for top 3
				prefix = f"{trophies[index-1]} " if index <= 3 else f"{index}. "
				if index == 26:
					break
				embed.add_field(
					name=f"{index}. {chess_username}",
					value=f"Rating: **{rating}**",
					inline=False
				)
		 	# Add thumbnail
			embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/5987/5987898.png")
		# Add footer
		embed.set_footer(text=f"Last updated • {datetime.datetime.now().strftime('%Y-%m-%d')}")
		 
		await interaction.followup.send(embed=embed)
	
	@bot.tree.command(name="profile", description="Show Chess.com profile details for a user")
	@app_commands.describe(user="Discord user to show profile for (leave empty for your own profile)")
	async def profile(interaction: discord.Interaction, user: discord.User = None):
		await interaction.response.defer()
		 
		target_user = user or interaction.user
		user_data = get_user_profile(target_user.id)
		 
		if not user_data:
			await interaction.followup.send(
				f"{'You are' if target_user == interaction.user else f'{target_user.display_name} is'} not registered. "
				f"Use `/register` to link your Chess.com account.",
				ephemeral=True
			)
			return
		 
		chess_username, rapid, blitz, bullet, puzzle, puzzle_rush, last_updated = user_data
		 
		# Create embed
		embed = discord.Embed(
			title=f"Chess.com Profile: {chess_username}",
			url=f"https://www.chess.com/member/{chess_username}",
			color=target_user.color or 0x00BFFF,
			timestamp=datetime.datetime.now()
		)
		 
		embed.set_author(name=target_user.display_name, icon_url=target_user.display_avatar.url)
		 
		# Add ratings
		ratings_value = (
			f"**Rapid:** {rapid or 'N/A'}\n"
			f"**Blitz:** {blitz or 'N/A'}\n"
			f"**Bullet:** {bullet or 'N/A'}\n"
			f"**Puzzle:** {puzzle or 'N/A'}\n"
			f"**Puzzle Rush Score:** {puzzle_rush or 'N/A'}"
		)
		 
		embed.add_field(name="Ratings", value=ratings_value, inline=True)
		 
		# Calculate and add average rating
		ratings = [r for r in [rapid, blitz, bullet, puzzle] if r is not None]
		avg_rating = int(sum(ratings) / len(ratings)) if ratings else 'N/A'
		 
		embed.add_field(name="Average Rating", value=f"**{avg_rating}**", inline=True)
		 
		# Add last updated timestamp
		last_updated_dt = datetime.datetime.fromisoformat(last_updated)
		embed.set_footer(text=f"Last updated • {last_updated_dt.strftime('%Y-%m-%d %H:%M')}")
		 
		await interaction.followup.send(embed=embed)
	
	@bot.tree.command(name="refresh", description="Manually refresh your Chess.com ratings")
	async def refresh(interaction: discord.Interaction):
		await interaction.response.defer(ephemeral=True)
		 
		from database import get_user
		chess_username = get_user(interaction.user.id)
		 
		if not chess_username:
			await interaction.followup.send("You are not registered. Use `/register` to link your Chess.com account.", ephemeral=True)
			return
		 
		# Fetch latest data
		chess_data = await fetch_chess_data(chess_username)
		if not chess_data:
			await interaction.followup.send(f"Error fetching data from Chess.com for user {chess_username}.", ephemeral=True)
			return
		 
		# Store updated ratings
		if store_user_ratings(interaction.user.id, chess_data):
			await interaction.followup.send(f"Successfully refreshed your Chess.com ratings!", ephemeral=True)
		else:
			await interaction.followup.send("Error updating your ratings. Please try again later.", ephemeral=True)
	
	@bot.tree.command(name="help", description="Show available commands and information")
	async def help_command(interaction: discord.Interaction):
		embed = discord.Embed(
			title="Chess.com Leaderboard Bot - Help",
			description="Track and compare Chess.com ratings with your Discord friends!",
			color=0x00BFFF
		)
		 
		commands_info = [
			{
				"name": "/register <username>",
				"value": "Link your Discord account to your Chess.com profile"
			},
			{
				"name": "/unregister",
				"value": "Remove yourself from the leaderboard system"
			},
			{
				"name": "/leaderboard <category>",
				"value": "Show the leaderboard for a specific rating category (Rapid, Blitz, Bullet, Puzzle, Overall)"
			},
			{
				"name": "/profile [user]",
				"value": "Display your Chess.com profile details or another user's profile"
			},
			{
				"name": "/refresh",
				"value": "Manually update your Chess.com ratings"
			},
			{
				"name": "/help",
				"value": "Show this help message"
			}
		]
		 
		for cmd in commands_info:
			embed.add_field(name=cmd["name"], value=cmd["value"], inline=False)
		 
		embed.set_footer(text="Ratings are automatically updated once every 24 hours")
		 
		await interaction.response.send_message(embed=embed)