import openai
import time
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

openai.api_key = " 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"  # Replace with your OpenAI API key
assistant_id = "asst_cTD2OYIOUxXS0sWleZy57Z4v"      # Replace with your Assistant ID

def create_thread(ass_id, prompt):
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

def check_status(run_id, thread_id):
    run = openai.beta.threads.runs.retrieve(
        thread_id=thread_id,
        run_id=run_id,
    )
    return run.status

user_threads = {}

def handle_message(update, context):
    user_input = update.message.text
    my_run_id, my_thread_id = create_thread(assistant_id, user_input)

    status = check_status(my_run_id, my_thread_id)
    while status != "completed":
        status = check_status(my_run_id, my_thread_id)
        time.sleep(2)

    response = openai.beta.threads.messages.list(thread_id=my_thread_id)
    if response.data:
        bot_response = response.data[0].content[0].text.value
        update.message.reply_text(bot_response)



def start(update, context):
    update.message.reply_text('Hello! Lets figure out what you want to cook this week, and what you will need to do so!')

def main():
    updater = Updater("6878254005:AAFMd3HS9KMKW6lzvYSNMSV3lh27jgBFuOs", use_context=True)

    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
