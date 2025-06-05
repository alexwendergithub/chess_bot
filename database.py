# database.py - Database functions
import sqlite3
import datetime
import logging

logger = logging.getLogger('chess_bot.database')

DB_PATH = 'chess_leaderboard.db'

def setup_database():
	"""Initialize database tables if they don't exist"""
	conn = sqlite3.connect(DB_PATH)
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
	logger.info("Database setup complete!")

def get_connection():
	"""Get a database connection"""
	return sqlite3.connect(DB_PATH)

def get_user(discord_id):
	"""Get a user's Chess.com username"""
	conn = get_connection()
	cursor = conn.cursor()
	cursor.execute("SELECT chess_username FROM users WHERE discord_id = ?", (discord_id,))
	result = cursor.fetchone()
	conn.close()
	return result[0] if result else None

def register_user(discord_id, chess_username):
	"""Register or update a user"""
	conn = get_connection()
	cursor = conn.cursor()
	
	# Check if user exists
	cursor.execute("SELECT chess_username FROM users WHERE discord_id = ?", (discord_id,))
	existing_user = cursor.fetchone()
	
	if existing_user:
		cursor.execute("UPDATE users SET chess_username = ? WHERE discord_id = ?",
				  	(chess_username, discord_id))
		result = "updated"
	else:
		cursor.execute("INSERT INTO users (discord_id, chess_username, join_date) VALUES (?, ?, ?)",
				  	(discord_id, chess_username, datetime.datetime.now().isoformat()))
		result = "registered"
	
	conn.commit()
	conn.close()
	return result

def unregister_user_chess_com(chess_user):
	"""Remove a user from the system"""
	conn = get_connection()
	cursor = conn.cursor()
	
	# Check if user exists
	cursor.execute("SELECT discord_id FROM users WHERE chess_username = ?", (chess_user,))
	existing_user = cursor.fetchone()
	
	if not existing_user:
		conn.close()
		return False
	discord_id = existing_user[0]
	# Delete user data
	cursor.execute("DELETE FROM ratings WHERE discord_id = ?", (discord_id,))
	cursor.execute("DELETE FROM users WHERE discord_id = ?", (discord_id,))
	
	conn.commit()
	conn.close()
	return True

def unregister_user(discord_id):
	"""Remove a user from the system"""
	conn = get_connection()
	cursor = conn.cursor()
	
	# Check if user exists
	cursor.execute("SELECT chess_username FROM users WHERE discord_id = ?", (discord_id,))
	existing_user = cursor.fetchone()
	
	if not existing_user:
		conn.close()
		return False
	
	# Delete user data
	cursor.execute("DELETE FROM ratings WHERE discord_id = ?", (discord_id,))
	cursor.execute("DELETE FROM users WHERE discord_id = ?", (discord_id,))
	
	conn.commit()
	conn.close()
	return True

def store_user_ratings(discord_id, chess_data):
	"""Store a user's ratings"""
	try:
		# Extract ratings with error handling for missing data
		rapid = chess_data.get('chess_rapid', {}).get('last', {}).get('rating', None)
		blitz = chess_data.get('chess_blitz', {}).get('last', {}).get('rating', None)
		bullet = chess_data.get('chess_bullet', {}).get('last', {}).get('rating', None)
		puzzle = chess_data.get('tactics', {}).get('highest', {}).get('rating', None)
		puzzle_rush = chess_data.get('puzzle_rush', {}).get('best', {}).get('score', None)
   	 
		conn = get_connection()
		cursor = conn.cursor()
   	 
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
   	 
		conn.commit()
		conn.close()
		return True
	except Exception as e:
		logger.error(f"Error storing ratings: {e}")
		return False

def get_user_profile(discord_id):
	"""Get a user's profile data"""
	conn = get_connection()
	cursor = conn.cursor()
	
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
	''', (discord_id,))
	
	result = cursor.fetchone()
	conn.close()
	return result

def get_leaderboard_data(category):
	"""Get leaderboard data for a specific category"""
	conn = get_connection()
	cursor = conn.cursor()
	if category == "puzzle_rush":
		conn = sqlite3.connect('chess_leaderboard.db')
		cursor = conn.cursor()
		
		# Fetch puzzle rush scores
		cursor.execute('''
		SELECT u.discord_id, u.chess_username, r.puzzle_rush_score
		FROM users u
		JOIN (
			SELECT discord_id, MAX(last_updated) as max_date
			FROM ratings
			GROUP BY discord_id
		) latest ON u.discord_id = latest.discord_id
		JOIN ratings r ON latest.discord_id = r.discord_id AND latest.max_date = r.last_updated
		WHERE r.puzzle_rush_score IS NOT NULL
		ORDER BY r.puzzle_rush_score DESC
		''')
	elif category == "overall":
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
	else:
		rating_column = f"{category}_rating"
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
		''')
	
	results = cursor.fetchall()
	conn.close()
	return results

def get_all_users():
	"""Get all registered users"""
	conn = get_connection()
	cursor = conn.cursor()
	
	cursor.execute("SELECT discord_id, chess_username FROM users")
	results = cursor.fetchall()
	
	conn.close()
	return results