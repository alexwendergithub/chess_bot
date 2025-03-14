import discord
from discord.ext import commands, tasks
from discord import app_commands
import requests
import sqlite3
import json
import datetime
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables (create a .env file with BOT_TOKEN=your_token)
load_dotenv()

# Bot setup with intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Database functions
def setup_database():
    """Initialize database tables if they don't exist"""
    conn = sqlite3.connect('chess_leaderboard.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        discord_id INTEGER PRIMARY KEY,
        chess_username TEXT NOT NULL,
        join_date TEXT NOT NULL
    )
    ''')
    
    # Create ratings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discord_id INTEGER NOT NULL,
        rapid_rating INTEGER,
        blitz_rating INTEGER,
        bullet_rating INTEGER,
        puzzle_rating INTEGER,
        puzzle_rush_score INTEGER,
        last_updated TEXT NOT NULL,
        FOREIGN KEY (discord_id) REFERENCES users (discord_id)
    )
    ''')
    
    conn.commit()
    conn.close()
    print("Database setup complete!")

# Chess.com API functions
async def fetch_chess_data(username):
    """Fetch player data from Chess.com API"""
    headers = {
        'User-Agent': 'Discord Chess Leaderboard Bot (your@email.com)'
    }
    
    try:
        # Verify user exists
        user_response = requests.get(f'https://api.chess.com/pub/player/{username}', headers=headers)
        user_response.raise_for_status()
        
        # Get player stats
        stats_response = requests.get(f'https://api.chess.com/pub/player/{username}/stats', headers=headers)
        stats_response.raise_for_status()
        
        return stats_response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:  # Rate limited
            retry_after = int(e.response.headers.get('Retry-After', 60))
            print(f"Rate limited! Waiting {retry_after} seconds")
            await asyncio.sleep(retry_after)
            return await fetch_chess_data(username)
        elif e.response.status_code == 404:
            print(f"User {username} not found on Chess.com")
            return None
        else:
            print(f"HTTP error: {e}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return None

def store_user_ratings(discord_id, chess_data, cursor):
    """Extract and store ratings from Chess.com data"""
    try:
        # Extract ratings with error handling for missing data
        rapid = chess_data.get('chess_rapid', {}).get('last', {}).get('rating', None)
        blitz = chess_data.get('chess_blitz', {}).get('last', {}).get('rating', None)
        bullet = chess_data.get('chess_bullet', {}).get('last', {}).get('rating', None)
        puzzle = chess_data.get('tactics', {}).get('highest', {}).get('rating', None)
        puzzle_rush = chess_data.get('puzzle_rush', {}).get('best', {}).get('score', None)
        
        # Check for existing ratings to update
        cursor.execute('''
        SELECT id FROM ratings WHERE discord_id = ?
        ORDER BY last_updated DESC LIMIT 1
        ''', (discord_id,))
        
        existing_rating = cursor.fetchone()
        
        if existing_rating:
            cursor.execute('''
            UPDATE ratings 
            SET rapid_rating = ?, blitz_rating = ?, bullet_rating = ?, 
                puzzle_rating = ?, puzzle_rush_score = ?, last_updated = ?
            WHERE id = ?
            ''', (rapid, blitz, bullet, puzzle, puzzle_rush, 
                datetime.datetime.now().isoformat(), existing_rating[0]))
        else:
            # Insert new ratings
            cursor.execute('''
            INSERT INTO ratings (discord_id, rapid_rating, blitz_rating, bullet_rating, 
                              puzzle_rating, puzzle_rush_score, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (discord_id, rapid, blitz, bullet, puzzle, puzzle_rush, 
                datetime.datetime.now().isoformat()))
        
        return True
    except Exception as e:
        print(f"Error storing ratings: {e}")
        return False

def calculate_average_rating(ratings):
    """Calculate average rating from non-NULL values"""
    valid_ratings = [r for r in ratings if r is not None]
    if not valid_ratings:
        return 0
    return sum(valid_ratings) / len(valid_ratings)

# Bot events
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    update_ratings.start()

# Background tasks
@tasks.loop(hours=24)
async def update_ratings():
    """Update ratings for all registered users once per day"""
    print("Updating user ratings...")
    
    conn = sqlite3.connect('chess_leaderboard.db')
    cursor = conn.cursor()
    
    # Get all registered users
    cursor.execute("SELECT discord_id, chess_username FROM users")
    users = cursor.fetchall()
    
    update_count = 0
    for discord_id, chess_username in users:
        # Add delay to avoid rate limiting
        await asyncio.sleep(2)
        
        # Fetch new ratings
        chess_data = await fetch_chess_data(chess_username)
        if chess_data:
            if store_user_ratings(discord_id, chess_data, cursor):
                update_count += 1
    
    conn.commit()
    conn.close()
    print(f"Ratings update complete! Updated {update_count}/{len(users)} users.")

@update_ratings.before_loop
async def before_update_ratings():
    await bot.wait_until_ready()

# Commands
@bot.tree.command(name="register", description="Register your Chess.com username")
@app_commands.describe(username="Your Chess.com username")
async def register(interaction: discord.Interaction, username: str):
    # Send deferred response for operations that might take time
    await interaction.response.defer(ephemeral=True)
    
    # Check if username exists on Chess.com
    chess_data = await fetch_chess_data(username)
    if not chess_data:
        await interaction.followup.send(f"Could not find Chess.com user '{username}'. Please check the spelling.", ephemeral=True)
        return
    
    # Store user in database
    conn = sqlite3.connect('chess_leaderboard.db')
    cursor = conn.cursor()
    
    # Check if user is already registered
    cursor.execute("SELECT chess_username FROM users WHERE discord_id = ?", (interaction.user.id,))
    existing_user = cursor.fetchone()
    
    if existing_user:
        cursor.execute("UPDATE users SET chess_username = ? WHERE discord_id = ?", (username, interaction.user.id))
        await interaction.followup.send(f"Updated your Chess.com username to {username}!", ephemeral=True)
    else:
        cursor.execute("INSERT INTO users (discord_id, chess_username, join_date) VALUES (?, ?, ?)", 
                    (interaction.user.id, username, datetime.datetime.now().isoformat()))
        await interaction.followup.send(f"Successfully registered with Chess.com username {username}!", ephemeral=True)
    
    # Store initial ratings
    store_user_ratings(interaction.user.id, chess_data, cursor)
    
    conn.commit()
    conn.close()

@bot.tree.command(name="unregister", description="Remove yourself from the Chess.com leaderboard")
async def unregister(interaction: discord.Interaction):
    conn = sqlite3.connect('chess_leaderboard.db')
    cursor = conn.cursor()
    
    # Check if user is registered
    cursor.execute("SELECT chess_username FROM users WHERE discord_id = ?", (interaction.user.id,))
    existing_user = cursor.fetchone()
    
    if not existing_user:
        await interaction.response.send_message("You are not registered in the leaderboard.", ephemeral=True)
        return
    
    # Delete user from database
    cursor.execute("DELETE FROM ratings WHERE discord_id = ?", (interaction.user.id,))
    cursor.execute("DELETE FROM users WHERE discord_id = ?", (interaction.user.id,))
    
    conn.commit()
    conn.close()
    
    await interaction.response.send_message("You have been removed from the Chess.com leaderboard.", ephemeral=True)

@bot.tree.command(name="leaderboard", description="Show Chess.com ratings leaderboard")
@app_commands.describe(category="Rating category to display")
@app_commands.choices(category=[
    app_commands.Choice(name="Rapid", value="rapid"),
    app_commands.Choice(name="Blitz", value="blitz"),
    app_commands.Choice(name="Bullet", value="bullet"),
    app_commands.Choice(name="Puzzle", value="puzzle"),
    app_commands.Choice(name="Overall", value="overall")
])
async def leaderboard(interaction: discord.Interaction, category: app_commands.Choice[str]):
    await interaction.response.defer()
    
    conn = sqlite3.connect('chess_leaderboard.db')
    cursor = conn.cursor()
    
    category_value = category.value
    
    if category_value == "overall":
        # Fetch data for overall ratings
        cursor.execute('''
        SELECT u.discord_id, u.chess_username, 
               r.rapid_rating, r.blitz_rating, r.bullet_rating, r.puzzle_rating
        FROM users u
        JOIN (
            SELECT discord_id, MAX(last_updated) as max_date
            FROM ratings
            GROUP BY discord_id
        ) latest ON u.discord_id = latest.discord_id
        JOIN ratings r ON latest.discord_id = r.discord_id AND latest.max_date = r.last_updated
        ''')
        
        users = cursor.fetchall()
        
        # Sort users by average rating
        user_ratings = []
        for user in users:
            discord_id, chess_username, rapid, blitz, bullet, puzzle = user
            ratings = [r for r in [rapid, blitz, bullet, puzzle] if r is not None]
            avg_rating = sum(ratings) / len(ratings) if ratings else 0
            user_ratings.append((discord_id, chess_username, rapid, blitz, bullet, puzzle, avg_rating))
        
        # Sort by average rating
        user_ratings.sort(key=lambda x: x[6], reverse=True)
        
        # Create embed
        embed = discord.Embed(
            title="Overall Chess.com Ratings Leaderboard",
            description="Average of all available ratings",
            color=0x00BFFF,
            timestamp=datetime.datetime.now()
        )
        
        for index, user in enumerate(user_ratings, start=1):
            discord_id, chess_username, rapid, blitz, bullet, puzzle, avg_rating = user
            
            embed.add_field(
                name=f"{index}. {chess_username}",
                value=f"Average: **{int(avg_rating)}**\n"
                      f"Rapid: {rapid or 'N/A'} | Blitz: {blitz or 'N/A'} | "
                      f"Bullet: {bullet or 'N/A'} | Puzzle: {puzzle or 'N/A'}",
                inline=False
            )
    else:
        # Fetch specific category ratings
        rating_column = f"{category_value}_rating"
        cursor.execute(f'''
        SELECT u.discord_id, u.chess_username, r.{rating_column}
        FROM users u
        JOIN (
            SELECT discord_id, MAX(last_updated) as max_date
            FROM ratings
            GROUP BY discord_id
        ) latest ON u.discord_id = latest.discord_id
        JOIN ratings r ON latest.discord_id = r.discord_id AND latest.max_date = r.last_updated
        WHERE r.{rating_column} IS NOT NULL
        ORDER BY r.{rating_column} DESC
        ''')
        
        users = cursor.fetchall()
        
        # Create embed
        embed = discord.Embed(
            title=f"Chess.com {category_value.capitalize()} Ratings Leaderboard",
            color=0x00BFFF,
            timestamp=datetime.datetime.now()
        )
        
        for index, user in enumerate(users, start=1):
            discord_id, chess_username, rating = user
            embed.add_field(
                name=f"{index}. {chess_username}",
                value=f"Rating: **{rating}**",
                inline=False
            )
    
    # Add footer
    embed.set_footer(text=f"Last updated • {datetime.datetime.now().strftime('%Y-%m-%d')}")
    
    conn.close()
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="profile", description="Show Chess.com profile details for a user")
@app_commands.describe(user="Discord user to show profile for (leave empty for your own profile)")
async def profile(interaction: discord.Interaction, user: discord.User = None):
    await interaction.response.defer()
    
    target_user = user or interaction.user
    
    conn = sqlite3.connect('chess_leaderboard.db')
    cursor = conn.cursor()
    
    # Check if user is registered
    cursor.execute('''
    SELECT u.chess_username, 
           r.rapid_rating, r.blitz_rating, r.bullet_rating, 
           r.puzzle_rating, r.puzzle_rush_score, r.last_updated
    FROM users u
    JOIN (
        SELECT discord_id, MAX(last_updated) as max_date
        FROM ratings
        GROUP BY discord_id
    ) latest ON u.discord_id = latest.discord_id
    JOIN ratings r ON latest.discord_id = r.discord_id AND latest.max_date = r.last_updated
    WHERE u.discord_id = ?
    ''', (target_user.id,))
    
    user_data = cursor.fetchone()
    conn.close()
    
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
    
    conn = sqlite3.connect('chess_leaderboard.db')
    cursor = conn.cursor()
    
    # Check if user is registered
    cursor.execute("SELECT chess_username FROM users WHERE discord_id = ?", (interaction.user.id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        await interaction.followup.send("You are not registered. Use `/register` to link your Chess.com account.", ephemeral=True)
        conn.close()
        return
    
    chess_username = user_data[0]
    
    # Fetch latest data
    chess_data = await fetch_chess_data(chess_username)
    if not chess_data:
        await interaction.followup.send(f"Error fetching data from Chess.com for user {chess_username}.", ephemeral=True)
        conn.close()
        return
    
    # Store updated ratings
    if store_user_ratings(interaction.user.id, chess_data, cursor):
        conn.commit()
        await interaction.followup.send(f"Successfully refreshed your Chess.com ratings!", ephemeral=True)
    else:
        await interaction.followup.send("Error updating your ratings. Please try again later.", ephemeral=True)
    
    conn.close()

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

# Run the bot
if __name__ == "__main__":
    setup_database()
    bot.run(os.getenv('BOT_TOKEN'))
