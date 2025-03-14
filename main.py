# main.py - Main entry point for the bot
import token_bot
from dotenv import load_dotenv
from bot import setup_bot
from database import setup_database
from tasks import register_tasks  # Changed from start_tasks
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
	# Load environment variables
	load_dotenv()
	
	# Setup database
	setup_database()
	
	# Setup bot
	bot = setup_bot()
	
	# Register tasks (but don't start them yet)
	register_tasks(bot)
	
	# Run the bot
	bot.run(token_bot.BOT_TOKEN)
