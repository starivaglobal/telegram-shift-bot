import os
import json
import logging
from datetime import datetime, timedelta
import requests
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.error("NO TOKEN FOUND!")
    exit(1)

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
DATA_FILE = "shifts.json"

# Track processed updates to prevent duplicates
PROCESSED_UPDATES = set()
MAX_PROCESSED_SIZE = 1000

# --- Flask App for Webhook and Health Check ---
app = Flask(__name__)

def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"shifts": {}}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

def get_display_name(user):
    first_name = user.get("first_name", "")
    last_name = user.get("last_name", "")
    username = user.get("username", "")
    user_id = user.get("id", "")
    
    if first_name:
        return f"{first_name} {last_name}" if last_name else first_name
    elif username:
        return f"@{username}"
    else:
        return str(user_id)

def send_message(chat_id, text):
    url = f"{BASE_URL}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        logger.error(f"Error sending message: {e}")

def handle_start(chat_id, user_name):
    welcome = f"""👋 Здравствуйте, {user_name}!

Добро пожаловать в бот управления сменами.

📅 Доступные команды:
/week - Расписание на неделю
/shift ГГГГ-ММ-ДД 1 - Первая смена (9:30-16:30)
/shift ГГГГ-ММ-ДД 2 - Вторая смена (16:00-23:00)
/my_shifts - Мои смены
/cancel ГГГГ-ММ-ДД 1|2 - Отменить запись

Пример: /shift 2026-05-10 1"""
    send_message(chat_id, welcome)

def handle_week(chat_id):
    data = load_data()
    today = datetime.now().date()
    weekdays_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    msg = "📅 Расписание смен на следующую неделю:\n\n"
    
    for i in range(7):
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        weekday = weekdays_ru[date.weekday()]
        shifts = data["shifts"].get(date_str, {"first": [], "second": []})
        
        first = ', '.join(shifts['first']) if shifts['first'] else "— Никто не записан —"
        second = ', '.join(shifts['second']) if shifts['second'] else "— Никто не записан —"
        msg += f"{weekday} ({date_str})\n🌅 Первая смена: {first}\n🌙 Вторая смена: {second}\n\n"
    
    send_message(chat_id, msg)

def handle_shift(chat_id, args, user):
    if len(args) != 2:
        send_message(chat_id, "Использование: /shift ГГГГ-ММ-ДД 1|2")
        return
    
    date_str, shift_num = args[0], args[1]
    display_name = get_display_name(user)
    
    try:
        shift_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if shift_date < datetime.now().date():
            send_message(chat_id, "❌ Нельзя записаться на прошедшую дату!")
            return
        if shift_date > datetime.now().date() + timedelta(days=7):
            send_message(chat_id, "❌ Записывайтесь только на следующую неделю!")
            return
    except ValueError:
        send_message(chat_id, "❌ Неверный формат даты! Используйте ГГГГ-ММ-ДД")
        return
    
    if shift_num not in ["1", "2"]:
        send_message(chat_id, "❌ Смена должна быть 1 или 2")
        return
    
    data = load_data()
    if date_str not in data["shifts"]:
        data["shifts"][date_str] = {"first": [], "second": []}
    
    key = "first" if shift_num == "1" else "second"
    
    if display_name not in data["shifts"][date_str][key]:
        data["shifts"][date_str][key].append(display_name)
        save_data(data)
        shift_name = "первую смену (9:30-16:30)" if shift_num == "1" else "вторую смену (16:00-23:00)"
        send_message(chat_id, f"✅ {display_name}, вы записаны на {shift_name} на {date_str}")
    else:
        send_message(chat_id, f"❌ {display_name}, вы уже записаны на эту смену!")

def handle_my_shifts(chat_id, user):
    display_name = get_display_name(user)
    data = load_data()
    today = datetime.now().date()
    my_list = []
    
    for date_str, shifts in data["shifts"].items():
        try:
            shift_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if shift_date >= today:
                if display_name in shifts.get("first", []):
                    my_list.append(f"📅 {date_str}: Первая смена (9:30-16:30)")
                if display_name in shifts.get("second", []):
                    my_list.append(f"📅 {date_str}: Вторая смена (16:00-23:00)")
        except:
            pass
    
    if my_list:
        send_message(chat_id, "📋 Ваши смены:\n\n" + "\n".join(my_list))
    else:
        send_message(chat_id, "📋 У вас нет запланированных смен.")

def handle_cancel(chat_id, args, user):
    if len(args) != 2:
        send_message(chat_id, "Использование: /cancel ГГГГ-ММ-ДД 1|2")
        return
    
    date_str, shift_num = args[0], args[1]
    display_name = get_display_name(user)
    data = load_data()
    key = "first" if shift_num == "1" else "second"
    
    if date_str in data["shifts"] and display_name in data["shifts"][date_str][key]:
        data["shifts"][date_str][key].remove(display_name)
        save_data(data)
        shift_name = "первой смены" if shift_num == "1" else "второй смены"
        send_message(chat_id, f"✅ {display_name}, вы отменены от {shift_name} на {date_str}")
    else:
        send_message(chat_id, f"❌ {display_name}, вы не записаны на эту смену.")

def process_update(update):
    try:
        update_id = update.get("update_id")
        
        # Check for duplicate
        if update_id in PROCESSED_UPDATES:
            logger.info(f"Skipping duplicate update {update_id}")
            return
        
        PROCESSED_UPDATES.add(update_id)
        if len(PROCESSED_UPDATES) > MAX_PROCESSED_SIZE:
            to_remove = list(PROCESSED_UPDATES)[:200]
            for old_id in to_remove:
                PROCESSED_UPDATES.discard(old_id)
        
        message = update.get("message")
        if not message:
            return
        
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        user = message.get("from", {})
        user_name = user.get("first_name", "")
        
        if not text.startswith("/"):
            return
        
        parts = text.split()
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        if command == "/start":
            handle_start(chat_id, user_name)
        elif command == "/week":
            handle_week(chat_id)
        elif command == "/shift":
            handle_shift(chat_id, args, user)
        elif command == "/my_shifts":
            handle_my_shifts(chat_id, user)
        elif command == "/cancel":
            handle_cancel(chat_id, args, user)
        else:
            send_message(chat_id, "❌ Неизвестная команда.")
    except Exception as e:
        logger.error(f"Error processing update: {e}")

# --- Webhook Endpoint ---
@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming Telegram updates"""
    try:
        update = request.get_json()
        if update:
            process_update(update)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error"}), 500

# --- Health Check Endpoints ---
@app.route('/')
@app.route('/health')
@app.route('/healthcheck')
def health():
    return "OK", 200

# --- Set Webhook on Startup ---
def set_webhook():
    """Register webhook with Telegram"""
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not render_url:
        logger.error("RENDER_EXTERNAL_URL not set")
        return False
    
    webhook_url = f"{render_url}/webhook"
    url = f"{BASE_URL}/setWebhook"
    
    try:
        response = requests.post(url, json={"url": webhook_url})
        result = response.json()
        if result.get("ok"):
            logger.info(f"✅ Webhook set to {webhook_url}")
            return True
        else:
            logger.error(f"Failed to set webhook: {result}")
            return False
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return False

# --- Main ---
if __name__ == "__main__":
    logger.info("🚀 Starting Shift Bot with Webhook...")
    
    # Set webhook on startup
    set_webhook()
    
    # Start Flask server
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"✅ Server starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)