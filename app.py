import os
import openai
import time
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# Set API keys
openai.api_key = os.getenv('OPENAI_API_KEY')
assistant_id = os.getenv('ASSISTANT_ID')
telegram_token = os.getenv('TELEGRAM_TOKEN')

# Dictionary to store user threads
user_threads = {}

def get_or_create_thread(user_id, initial_prompt):
    if user_id in user_threads:
        return user_threads[user_id]
    else:
        # Create a new thread with the initial message
        thread = openai.beta.threads.create(
            messages=[{
                "role": "user",
                "content": initial_prompt
            }]
        )
        thread_id = thread.id
        user_threads[user_id] = thread_id
        return thread_id

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
        update.message.reply_text(bot_response)

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
    updater = Updater(telegram_token, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()