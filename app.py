import os
import openai
import time
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import json
import os
import psycopg2
from decouple import config

DATABASE_URL = config('DATABASE_URL', cast=str)
conn = psycopg2.connect(DATABASE_URL, sslmode='require')

# Set API keys
openai.api_key = config('OPENAI_API_KEY', cast=str)
assistant_id = config('ASSISTANT_ID', cast=str)
telegram_token = config('TELEGRAM_TOKEN', cast=str)

# Dictionary to store user threads
user_threads = {}

def save_conversation(user_id, user_input, bot_response, message_id, thread_id):
    with psycopg2.connect(DATABASE_URL, sslmode='require') as conn:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO conversations (user_id, user_input, bot_response, message_id, thread_id)
                VALUES (%s, %s, %s, %s, %s)
            ''', (user_id, user_input, bot_response, message_id, thread_id))
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
        save_conversation(user_id, user_input, bot_response, message_id, my_thread_id)


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
        "Hello and welcome! 👋 I'm your dedicated Gut Health Guide from the team at Happy Feet, here to support you in managing your gut health and IBS symptoms with nutritious and delicious meal planning. 🥗 While I might take a moment to respond (up to a minute), I'm continuously learning to be quicker and more helpful."
        "Think of me as your personal nutritional helper. You can ask me things like 'I'm trying to ease my IBS symptoms, what should I have for lunch?' or 'Can you suggest a gut-friendly snack that's easy to prepare?', or 'How much fibre was in that lentil bolognese'. I'm here to answer all your queries about gut health, low FODMAP diets, and IBS-friendly meals. 🍲"
        "To start, just share your dietary preferences, any specific gut health concerns, and what you're aiming for in your diet. Whether it's managing symptoms, trying new recipes, or seeking nutritional advice, I'm here to help. So, what can I help you with today?"
    ]
    for msg in messages:
        update.message.reply_text(msg)
        time.sleep(5)  # Optional: Add a short delay between messages



def main():
    # Initialize database tables if they don't exist.
    try:
        with psycopg2.connect(DATABASE_URL, sslmode='require') as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS conversations (
                        user_id INTEGER NOT NULL,
                        user_input TEXT,
                        bot_response TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        message_id INTEGER,
                        thread_id TEXT
                    );
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_threads (
                        user_id INTEGER PRIMARY KEY,
                        thread_id TEXT
                    );
                ''')
                conn.commit()
    except psycopg2.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

    # Set up Telegram bot handlers
    updater = Updater(telegram_token, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    # Start the bot
    updater.start_polling()
    updater.idle()
    print("Bot is running and database tables are initialized.")

if __name__ == '__main__':
    main()