import threading
import time
import os
import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler, CallbackContext
from telegram.constants import ParseMode
import datetime
import json
from bot_trickest import trigger_trickest_workflow, get_trickest_status, download_trickest_files
from database import init_db, authorize_user, is_authorized, store_run_id, get_last_run_id, get_user_runs, DATABASE

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Password for authorization
AUTH_PASSWORD = 'password'

# Define states for conversation handler
ANALYSIS_NAME, DOMAIN, SUBDOMAIN, INITIAL_URL, IP, IP_RANGE, CSEID, GITHUB_NAME, CONFIRM_DATA = range(9)

async def start(update: Update, context: CallbackContext) -> None:
    """Start command handler"""
    user_input = context.args
    if user_input and user_input[0] == AUTH_PASSWORD:
        user_id = update.message.chat_id
        authorize_user(user_id)
        await update.message.reply_text('Authorization successful!')
    else:
        await update.message.reply_text('Authorization failed.')

async def analyze(update: Update, context: CallbackContext) -> int:
    """Analyze command handler"""
    user_id = update.message.chat_id
    if is_authorized(user_id):
        await context.bot.send_message(chat_id=user_id, text='Please provide a name for this analysis:')
        return ANALYSIS_NAME
    await update.message.reply_text('You are not authorized to use this command.')
    return ConversationHandler.END

async def analysis_name(update: Update, context: CallbackContext) -> int:
    """Handler for receiving analysis name"""
    user_id = update.message.chat_id
    context.user_data['analysis_name'] = update.message.text 
    await context.bot.send_message(chat_id=user_id, text='Comma separated list of domains (n for none):')
    return DOMAIN

async def domain(update: Update, context: CallbackContext) -> int:
    """Handler for receiving domain"""
    user_id = update.message.chat_id
    context.user_data['domains'] = update.message.text if len(update.message.text) > 2 else ''
    await context.bot.send_message(chat_id=user_id, text='Comma separated list of subdomains (n for none):')
    return SUBDOMAIN

async def subdomain(update: Update, context: CallbackContext) -> int:
    """Handler for receiving subdomain"""
    user_id = update.message.chat_id
    context.user_data['subdomains'] = update.message.text if len(update.message.text) > 2 else ''
    await context.bot.send_message(chat_id=user_id, text='Comma separated list of initial URLs (n for none):')
    return INITIAL_URL

async def initial_url(update: Update, context: CallbackContext) -> int:
    """Handler for receiving initial URL"""
    user_id = update.message.chat_id
    context.user_data['initial_urls'] = update.message.text if len(update.message.text) > 2 else ''
    await context.bot.send_message(chat_id=user_id, text='Comma separated list of IPs (n for none):')
    return IP

async def ip(update: Update, context: CallbackContext) -> int:
    """Handler for receiving IP"""
    user_id = update.message.chat_id
    context.user_data['ips'] = update.message.text if len(update.message.text) > 2 else ''
    await context.bot.send_message(chat_id=user_id, text='Comma separated list of IP ranges (n for none):')
    return IP_RANGE

async def ip_range(update: Update, context: CallbackContext) -> int:
    """Handler for receiving IP range"""
    user_id = update.message.chat_id
    context.user_data['ip_ranges'] = update.message.text if len(update.message.text) > 2 else ''
    await context.bot.send_message(chat_id=user_id, text='Please provide the CSEID (n for none):')
    return CSEID

async def cseid(update: Update, context: CallbackContext) -> int:
    """Handler for receiving CSEID"""
    user_id = update.message.chat_id
    context.user_data['cseid'] = update.message.text if len(update.message.text) > 2 else ''
    await context.bot.send_message(chat_id=user_id, text='Comma separated list of Github names (n for none):')
    return GITHUB_NAME

async def github_name(update: Update, context: CallbackContext) -> int:
    """Handler for receiving Github name"""
    user_id = update.message.chat_id
    context.user_data['github_names'] = update.message.text if len(update.message.text) > 2 else ''
    if is_authorized(user_id):
        try:
            data = {
                "domains": context.user_data['domains'].replace(" ", "").strip(),
                "subdomains": context.user_data['subdomains'].replace(" ", "").strip(),
                "initial_urls": context.user_data['initial_urls'].replace(" ", "").strip(),
                "ips": context.user_data['ips'].replace(" ", "").strip(),
                "ip_ranges": context.user_data['ip_ranges'].replace(" ", "").strip(),
                "cseid": context.user_data['cseid'].replace(" ", "").strip(),
                "github_names": context.user_data['github_names'].replace(" ", "").strip(),
            }
            
            # Send the parsed data to the user for confirmation
            data_text = json.dumps(data, indent=4)
            await context.bot.send_message(
                chat_id=user_id, 
                text=f"Please confirm the following data:\n<pre>{data_text}</pre>\nType 'yes' to confirm or 'no' to cancel.", 
                parse_mode=ParseMode.HTML
            )
            context.user_data['parsed_data'] = data
            return CONFIRM_DATA
        except json.JSONDecodeError:
            await context.bot.send_message(chat_id=user_id, text='Invalid JSON format. Please provide correct JSON data.')
            return GITHUB_NAME
    else:
        await update.message.reply_text('You are not authorized to use this command.')
        return ConversationHandler.END

async def confirm_data(update: Update, context: CallbackContext) -> int:
    """Handler for confirming data"""
    user_id = update.message.chat_id
    text = update.message.text.strip().lower()

    if text.lower() == 'yes':
        data = context.user_data['parsed_data']
        analysis_name = context.user_data['analysis_name']
        analysis_time = datetime.datetime.now().isoformat()

        run_id = trigger_trickest_workflow(data)
        parameters = json.dumps(data)
        if not run_id:
            await context.bot.send_message(chat_id=user_id, text='Failed to trigger workflow.')
            return ConversationHandler.END
        
        store_run_id(user_id, run_id, analysis_name, analysis_time, parameters)
        await context.bot.send_message(chat_id=user_id, text=f'Workflow triggered. Run ID: {run_id}')
        return ConversationHandler.END
    else:
        await context.bot.send_message(chat_id=user_id, text='Operation cancelled.')
        return ConversationHandler.END

async def last_status(update: Update, context: CallbackContext) -> None:
    """Last status command handler"""
    user_id = update.message.chat_id
    if is_authorized(user_id):
        run_id = get_last_run_id(user_id)
        if run_id:
            status_info = get_trickest_status(run_id)
            status_message = (
                f"Run ID: {status_info['run_id']}\n"
                f"Status: {status_info['status']}\n"
                f"Workflow Name: {status_info['workflow_name']}\n"
                f"Started Date: {status_info['started_date']}\n"
                f"IP Addresses: {', '.join(status_info['ip_addresses'])}"
            )
            await context.bot.send_message(chat_id=user_id, text=status_message)
        else:
            await context.bot.send_message(chat_id=user_id, text='No runs found for your user ID.')
    else:
        await update.message.reply_text('You are not authorized to use this command.')

async def history(update: Update, context: CallbackContext) -> None:
    """History command handler"""
    user_id = update.message.chat_id
    if is_authorized(user_id):
        runs = get_user_runs(user_id)
        if runs:
            keyboard = []
            for run in runs:
                run_id, status, name, date = run
                keyboard.append([InlineKeyboardButton(f"{name} - {date}", callback_data=run_id)])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text('Select a run to view details:', reply_markup=reply_markup)
        else:
            await context.bot.send_message(chat_id=user_id, text='No runs found for your user ID.')
    else:
        await update.message.reply_text('You are not authorized to use this command.')

async def run_details_callback(update: Update, context: CallbackContext) -> None:
    """Callback handler for run details"""
    query = update.callback_query
    query.answer()
    run_id = query.data
    user_id = query.message.chat_id
    if is_authorized(user_id):
        status_info = get_trickest_status(run_id)
        status_message = (
            f"Run ID: {status_info['run_id']}\n"
            f"Status: {status_info['status']}\n"
            f"Workflow Name: {status_info['workflow_name']}\n"
            f"Started Date: {status_info['started_date']}\n"
            f"IP Addresses: {', '.join(status_info['ip_addresses'])}"
        )
        query.edit_message_text(text=status_message)

        if status_info['status'] == 'Completed':
            output_dir = f'outputs/{run_id}'
            download_trickest_files(run_id, output_dir)
            for file_name in os.listdir(output_dir):
                file_path = os.path.join(output_dir, file_name)
                await context.bot.send_document(chat_id=user_id, document=open(file_path, 'rb'), filename=file_name)
    else:
        query.edit_message_text(text='You are not authorized to view this run.')

def check_workflows(bot):
    """Check the status of running workflows every 5 minutes."""
    while True:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, run_id FROM user_runs WHERE status = 'Pending'")
            running_workflows = cursor.fetchall()

        for user_id, run_id in running_workflows:
            status_info = get_trickest_status(run_id)
            if status_info['status'].upper() == 'COMPLETED':
                # Mark as completed in the database
                with sqlite3.connect(DATABASE) as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE user_runs SET status = 'Completed' WHERE run_id = ?", (run_id,))
                    conn.commit()

                # Notify the user
                bot.send_message(chat_id=user_id, text=f'Workflow {run_id} has completed.')
            
            elif status_info['status'] == 'Unknown':
                # Mark as failed in the database
                with sqlite3.connect(DATABASE) as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE user_runs SET status = 'Failed' WHERE run_id = ?", (run_id,))
                    conn.commit()

                # Notify the user
                bot.send_message(chat_id=user_id, text=f'Workflow {run_id} has failed.')

        time.sleep(300)  # Check every 5 minutes

def main():
    """Start the bot."""
    init_db()

    # Create the Application and pass it your bot's token.
    application = Application.builder().token("7083395381:AAHatLWCceqQkyu7c4nPlIHRdznTN64nWJ0").build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("last_status", last_status))
    application.add_handler(CommandHandler("history", history))

    # Conversation handler for the analyze command
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('analyze', analyze)],
        states={
            ANALYSIS_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, analysis_name)],
            DOMAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, domain)],
            SUBDOMAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, subdomain)],
            INITIAL_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, initial_url)],
            IP: [MessageHandler(filters.TEXT & ~filters.COMMAND, ip)],
            IP_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ip_range)],
            CSEID: [MessageHandler(filters.TEXT & ~filters.COMMAND, cseid)],
            GITHUB_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, github_name)],
            CONFIRM_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_data)],
        },
        fallbacks=[]
    )

    application.add_handler(conv_handler)
    
    # CallbackQuery handler for inline button presses
    application.add_handler(CallbackQueryHandler(run_details_callback))

    # Start the background thread to check workflows
    workflow_thread = threading.Thread(target=check_workflows, args=(application.bot,))
    workflow_thread.daemon = True
    workflow_thread.start()

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()