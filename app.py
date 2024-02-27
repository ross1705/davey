import os
import openai
import time
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import json
import os
import psycopg2

DATABASE_URL="postgres://davey_db_user:xHVilK1rpGdHC08W5jIS8l71eDckCZWE@dpg-cnf25ked3nmc73f0vrh0-a/davey_db"
conn = psycopg2.connect(DATABASE_URL, sslmode='require')

# Set API keys
openai.api_key = os.getenv('OPENAI_API_KEY')
assistant_id = os.getenv('ASSISTANT_ID')
telegram_token = os.getenv('TELEGRAM_TOKEN')

# Dictionary to store user threads
user_threads = {}

def save_conversation(user_id, user_input, bot_response, message_id):
    print("Database URL:", os.getenv('DATABASE_URL'))
    with psycopg2.connect(DATABASE_URL, sslmode='require') as conn:
        with conn.cursor() as cursor:
            # Check if the record already exists based on message_id
            cursor.execute('''
                SELECT 1 FROM conversations WHERE message_id = %s
            ''', (message_id,))
            if cursor.fetchone() is None:
                # Record does not exist, so insert it
                cursor.execute('''
                    INSERT INTO conversations (user_id, user_input, bot_response, message_id)
                    VALUES (%s, %s, %s, %s)
                ''', (user_id, user_input, bot_response, message_id))
                conn.commit()
def get_thread_id(user_id):
    with psycopg2.connect(DATABASE_URL, sslmode='require') as conn:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT thread_id FROM user_threads WHERE user_id = %s
            ''', (user_id,))
            result = cursor.fetchone()
            return result[0] if result else None

def save_thread_id(user_id, thread_id):
    with psycopg2.connect(DATABASE_URL, sslmode='require') as conn:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO user_threads (user_id, thread_id)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET thread_id = EXCLUDED.thread_id
            ''', (user_id, thread_id))
            conn.commit()


def check_status(run_id, thread_id):
    run = openai.beta.threads.runs.retrieve(
        thread_id=thread_id,
        run_id=run_id,
    )
    return run.status

def create_thread(ass_id, prompt):
    # Function implementation
    thread = openai.beta.threads.create()
    my_thread_id = thread.id

    openai.beta.threads.messages.create(
        thread_id=my_thread_id,
        role="user",
        content=prompt
    )

    run = openai.beta.threads.runs.create(
        thread_id=my_thread_id,
        assistant_id=ass_id,
    )
    return run.id, my_thread_id


def handle_message(update, context):
    user_id = update.message.from_user.id  # Get the unique user ID
    user_input = update.message.text
    message_id = update.message.message_id  # Get the unique message ID from the update

    my_thread_id = get_thread_id(user_id)
    if my_thread_id is None:
        # If this user doesn't have a thread yet, create one
        my_run_id, my_thread_id = create_thread(assistant_id, user_input)
        save_thread_id(user_id, my_thread_id)  # Save the new thread ID in the database
    else:
        # If the user already has a thread, use it
        my_run_id = add_to_thread(my_thread_id, user_input)  # Add message to existing thread

    status = check_status(my_run_id, my_thread_id)
    while status != "completed":
        status = check_status(my_run_id, my_thread_id)
        time.sleep(2)

    response = openai.beta.threads.messages.list(thread_id=my_thread_id)
    if response.data:
        bot_response = response.data[0].content[0].text.value
        print(f"Bot response: {bot_response}")
        update.message.reply_text(bot_response)
        save_conversation(user_id, user_input, bot_response, message_id)

# New function to add a message to an existing thread
def add_to_thread(thread_id, prompt):
    openai.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=prompt
    )
    run = openai.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
    )
    return run.id


def start(update, context):
    messages = [
        "Hello! My name is Remi, and I'm going to help you plan your dinners for the week🍽️",
        "Feel free to ask for recipes or suggestions. I'll also prepare a handy shopping list for you. 📝",
        "When it's cooking time, just tell me, and I'll guide you through each recipe step-by-step. 👩‍🍳",
        "Please be patient with me as I am not the fastest typer, and it can take me up to a minute to reply. I also might make some mistakes, so please let me know if I do!",
        "Most of my recipes come with a video, just ask me for it if I forget to give it to you.",
        "It's a good idea to watch these videos before cooking if you have a chance, so that you can get a better idea of what you are cooking!",
        "Again, please give me all of the feedback you can; good or bad (even better if it's bad). Hope I can be of some help!"
        "Now, ready to plan your dinners for next week?"
    ]
    for msg in messages:
        update.message.reply_text(msg)
        time.sleep(5)  # Optional: Add a short delay between messages



def main():
    # Connect to Render's PostgreSQL database
    database_url = os.getenv('DATABASE_URL')  # Ensure this environment variable is set in Render
    with psycopg2.connect(database_url, sslmode='require') as conn:
        with conn.cursor() as cursor:
            # Create conversations table (if not exists)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    user_id INTEGER,
                    thread_id TEXT,
                    user_input TEXT,
                    bot_response TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Create user_threads table (if not exists)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_threads (
                    user_id INTEGER PRIMARY KEY,
                    thread_id TEXT
                )
            ''')
            conn.commit()

    updater = Updater(telegram_token, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    updater.start_polling()
    updater.idle()
    print("Database and table initialized successfully.")

if __name__ == '__main__':
    main()