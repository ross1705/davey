import os
import openai
import time
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import json
import sqlite3

# Set API keys
openai.api_key = os.getenv('OPENAI_API_KEY')
assistant_id = os.getenv('ASSISTANT_ID')
telegram_token = os.getenv('TELEGRAM_TOKEN')

# Dictionary to store user threads
user_threads = {}

def save_conversation(user_id, user_input, bot_response):
    try:
        print(f"Saving conversation: user_id={user_id}, user_input={user_input}, bot_response={bot_response}")
        with sqlite3.connect('my_telegram_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO conversations (user_id, user_input, bot_response)
                VALUES (?, ?, ?)
            ''', (user_id, user_input, bot_response))
            conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Exception in save_conversation: {e}")

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

    if user_id not in user_threads:
        # If this user doesn't have a thread yet, create one
        my_run_id, my_thread_id = create_thread(assistant_id, user_input)
        user_threads[user_id] = my_thread_id  # Store the thread ID for this user
    else:
        # If the user already has a thread, use it
        my_thread_id = user_threads[user_id]
        my_run_id = add_to_thread(my_thread_id, user_input)  # Function to add message to existing thread

    # The rest of the function remains largely the same
    status = check_status(my_run_id, my_thread_id)
    while status != "completed":
        status = check_status(my_run_id, my_thread_id)
        time.sleep(2)

    response = openai.beta.threads.messages.list(thread_id=my_thread_id)
    if response.data:
        bot_response = response.data[0].content[0].text.value
        print(f"Bot response: {bot_response}")
        update.message.reply_text(bot_response)
        # Save the conversation after sending the response
        save_conversation(user_id, user_input, bot_response)

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
    update.message.reply_text('Hello! How can I assist you today?')

def main():
    with sqlite3.connect('my_telegram_bot.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                user_id INTEGER,
                user_input TEXT,
                bot_response TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
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