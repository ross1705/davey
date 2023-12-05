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
    user_input = update.message.text
    user_id = update.message.from_user.id

    # Check if the user already has an active thread
    if user_id not in user_threads:
        # Create a new thread with the initial message
        thread = openai.beta.threads.create(
            messages=[{
                "role": "user",
                "content": user_input
            }]
        )
        user_threads[user_id] = thread.id

    thread_id = user_threads[user_id]

    # Add the user's message to the thread
    openai.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_input
    )

    # Run the thread with the assistant
    run = openai.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id
    )

    # Check the status of the run
    while True:
        run_status = openai.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id
        ).status
        if run_status == "completed":
            break
        time.sleep(2)

    # Get the last message from the thread
    response = openai.beta.threads.messages.list(thread_id=thread_id)
    if response.data:
        # Assuming the last message is the bot's response
        bot_response = response.data[-1].content[0].text.value
        update.message.reply_text(bot_response)


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