# chess_api.py - Chess.com API interaction
import requests
import asyncio
import logging

logger = logging.getLogger('chess_bot.chess_api')

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
			logger.warning(f"Rate limited! Waiting {retry_after} seconds")
			await asyncio.sleep(retry_after)
			return await fetch_chess_data(username)
		elif e.response.status_code == 404:
			logger.warning(f"User {username} not found on Chess.com")
			return None
		else:
			logger.error(f"HTTP error: {e}")
			return None
	except requests.exceptions.RequestException as e:
		logger.error(f"Request error: {e}")
		return None

def calculate_average_rating(ratings):
	"""Calculate average rating from non-NULL values"""
	valid_ratings = [r for r in ratings if r is not None]
	if not valid_ratings:
		return 0
	return sum(valid_ratings) / len(valid_ratings)