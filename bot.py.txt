import os
import asyncio
import json
import logging
from datetime import datetime, timedelta
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
URL = os.environ.get("RENDER_EXTERNAL_URL")  # Render provides this automatically
PORT = int(os.getenv("PORT", 8000))

# Shift definitions
SHIFTS = {
    1: {"name": "First Shift", "start": "09:30", "end": "16:30"},
    2: {"name": "Second Shift", "start": "16:00", "end": "23:00"}
}

DATA_FILE = "shifts.json"

def load_data():
    """Load shift data from JSON file"""
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"shifts": {}, "users": {}}

def save_data(data):
    """Save shift data to JSON file"""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ----- Telegram Command Handlers -----

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register a new user"""
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.full_name
    
    data = load_data()
    if username not in data["users"]:
        data["users"][username] = {
            "telegram_id": user.id,
            "name": user.full_name
        }
        save_data(data)
        await update.message.reply_text(
            f"✅ Welcome {user.full_name}! You're now registered.\n\n"
            f"📅 **Commands:**\n"
            f"/week - View next 7 days schedule\n"
            f"/shift YYYY-MM-DD 1 - Sign up for First Shift (9:30-16:30)\n"
            f"/shift YYYY-MM-DD 2 - Sign up for Second Shift (16:00-23:00)\n"
            f"/my_shifts - View your upcoming shifts\n"
            f"/cancel YYYY-MM-DD 1|2 - Cancel a shift"
        )
    else:
        await update.message.reply_text(f"Welcome back {user.full_name}! Use /week to see the schedule.")

async def add_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add employee to a shift: /shift 2026-04-06 1"""
    if len(context.args) != 2:
        await update.message.reply_text(
            "Usage: /shift YYYY-MM-DD 1|2\n"
            "Example: /shift 2026-04-06 1 (for First Shift)\n"
            "         /shift 2026-04-06 2 (for Second Shift)"
        )
        return
    
    date_str, shift_num = context.args[0], context.args[1]
    username = f"@{update.effective_user.username}" if update.effective_user.username else update.effective_user.full_name
    
    # Validate date
    try:
        shift_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if shift_date < datetime.now().date():
            await update.message.reply_text("❌ Cannot sign up for past dates!")
            return
        if shift_date > datetime.now().date() + timedelta(days=7):
            await update.message.reply_text("❌ Please sign up only for the upcoming week!")
            return
    except ValueError:
        await update.message.reply_text("❌ Invalid date format! Use YYYY-MM-DD")
        return
    
    # Validate shift number
    if shift_num not in ["1", "2"]:
        await update.message.reply_text("❌ Shift must be 1 (First) or 2 (Second)")
        return
    
    data = load_data()
    date_key = date_str
    
    if date_key not in data["shifts"]:
        data["shifts"][date_key] = {"first": [], "second": []}
    
    shift_key = "first" if shift_num == "1" else "second"
    
    if username in data["shifts"][date_key][shift_key]:
        await update.message.reply_text(f"❌ You're already signed up for {SHIFTS[int(shift_num)]['name']} on {date_str}!")
        return
    
    data["shifts"][date_key][shift_key].append(username)
    save_data(data)
    
    shift_name = SHIFTS[int(shift_num)]["name"]
    await update.message.reply_text(
        f"✅ You've been added to {shift_name} on {date_str} ({SHIFTS[int(shift_num)]['start']} - {SHIFTS[int(shift_num)]['end']})"
    )

async def view_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the schedule for the next 7 days"""
    data = load_data()
    today = datetime.now().date()
    message = "📅 **Shift Schedule (Next 7 Days)**\n\n"
    
    for i in range(7):
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        weekday = date.strftime("%A")
        
        message += f"**{weekday} ({date_str})**\n"
        
        # First shift
        first_shift = data["shifts"].get(date_str, {}).get("first", [])
        first_display = ", ".join(first_shift) if first_shift else "— No one signed up —"
        message += f"🌅 First Shift (9:30-16:30): {first_display}\n"
        
        # Second shift
        second_shift = data["shifts"].get(date_str, {}).get("second", [])
        second_display = ", ".join(second_shift) if second_shift else "— No one signed up —"
        message += f"🌙 Second Shift (16:00-23:00): {second_display}\n\n"
    
    await update.message.reply_text(message, parse_mode="Markdown")

async def my_shifts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's upcoming shifts"""
    username = f"@{update.effective_user.username}" if update.effective_user.username else update.effective_user.full_name
    data = load_data()
    today = datetime.now().date()
    
    my_upcoming = []
    for date_str, shifts in data["shifts"].items():
        shift_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if shift_date >= today:
            if username in shifts.get("first", []):
                my_upcoming.append(f"{date_str}: First Shift (9:30-16:30)")
            if username in shifts.get("second", []):
                my_upcoming.append(f"{date_str}: Second Shift (16:00-23:00)")
    
    if my_upcoming:
        message = "📋 **Your Upcoming Shifts:**\n\n" + "\n".join(my_upcoming)
    else:
        message = "📋 You have no upcoming shifts scheduled."
    
    await update.message.reply_text(message, parse_mode="Markdown")

async def cancel_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel user's shift: /cancel 2026-04-06 1"""
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /cancel YYYY-MM-DD 1|2")
        return
    
    date_str, shift_num = context.args[0], context.args[1]
    username = f"@{update.effective_user.username}" if update.effective_user.username else update.effective_user.full_name
    
    data = load_data()
    shift_key = "first" if shift_num == "1" else "second"
    
    if date_str not in data["shifts"]:
        await update.message.reply_text("❌ No shifts found for that date.")
        return
    
    if username not in data["shifts"][date_str][shift_key]:
        await update.message.reply_text("❌ You're not signed up for that shift.")
        return
    
    data["shifts"][date_str][shift_key].remove(username)
    save_data(data)
    
    await update.message.reply_text(f"✅ You've been removed from {SHIFTS[int(shift_num)]['name']} on {date_str}.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message"""
    await update.message.reply_text(
        "📋 **Shift Bot Commands**\n\n"
        "/start - Register with the bot\n"
        "/week - View schedule for next 7 days\n"
        "/shift YYYY-MM-DD 1 - Sign up for First Shift (9:30-16:30)\n"
        "/shift YYYY-MM-DD 2 - Sign up for Second Shift (16:00-23:00)\n"
        "/my_shifts - View your upcoming shifts\n"
        "/cancel YYYY-MM-DD 1|2 - Cancel your shift\n"
        "/help - Show this help message"
    )

# ----- Main Application with Webhook Support -----

async def main():
    """Main entry point - sets up webhook and runs the server"""
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        return
    
    # Create Telegram application
    app = Application.builder().token(TOKEN).updater(None).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("shift", add_shift))
    app.add_handler(CommandHandler("week", view_week))
    app.add_handler(CommandHandler("my_shifts", my_shifts))
    app.add_handler(CommandHandler("cancel", cancel_shift))
    app.add_handler(CommandHandler("help", help_command))
    
    # Set webhook URL (Render provides RENDER_EXTERNAL_URL automatically)
    webhook_url = f"{URL}/telegram"
    await app.bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)
    logger.info(f"Webhook set to {webhook_url}")
    
    # Create Starlette app for handling HTTP requests
    async def telegram_webhook(request: Request) -> Response:
        """Handle incoming Telegram updates via webhook"""
        try:
            data = await request.json()
            update = Update.de_json(data, app.bot)
            await app.process_update(update)
            return Response()
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return Response(status_code=500)
    
    async def health_check(request: Request) -> PlainTextResponse:
        """Health check endpoint for Render"""
        return PlainTextResponse("OK")
    
    starlette_app = Starlette(routes=[
        Route("/telegram", telegram_webhook, methods=["POST"]),
        Route("/healthcheck", health_check, methods=["GET"]),
        Route("/health", health_check, methods=["GET"]),  # Alternative endpoint
    ])
    
    # Run the web server
    import uvicorn
    config = uvicorn.Config(starlette_app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    
    async with app:
        await app.start()
        logger.info(f"Bot started! Webhook URL: {webhook_url}")
        await server.serve()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())