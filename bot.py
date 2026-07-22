#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json
import random
import logging
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS = [int(id.strip()) for id in os.environ.get("ADMIN_IDS", "123456789").split(",") if id.strip()]
CHANNEL = os.environ.get("CHANNEL", "@shartino")
SUPPORT = os.environ.get("SUPPORT", "@shartino_sup")
TRX_WALLET = os.environ.get("TRX_WALLET", "TEv9t55am7zcCi2Z7dUXtFfKQmofeN7e1r")
USDT_WALLET = os.environ.get("USDT_WALLET", "TEVuvWZ68UbDUdzpd6EqxncsqDVjwyY7cj")

MIN_BET = int(os.environ.get("MIN_BET", 10000))
GIFT_AMOUNT = int(os.environ.get("GIFT_AMOUNT", 50000))
MIN_WITHDRAW = int(os.environ.get("MIN_WITHDRAW", 500000))
COMMISSION_PERCENT = int(os.environ.get("COMMISSION_PERCENT", 30))
INITIAL_BALANCE = int(os.environ.get("INITIAL_BALANCE", 0))

DATA_FILE = "users.json"
ADMIN_CONFIG_FILE = "admin_config.json"

def load_json(file_path, default=None):
    if default is None:
        default = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

users = load_json(DATA_FILE)
admin_config = load_json(ADMIN_CONFIG_FILE, {
    "deposit_enable_date": "۳۰ مرداد‌ماه",
    "trx_wallet": TRX_WALLET,
    "usdt_wallet": USDT_WALLET,
    "channels": [{"link": CHANNEL, "enabled": True}],
    "min_bet": MIN_BET,
    "min_deposit": 500000,
    "min_withdraw": MIN_WITHDRAW,
    "gift_amount": GIFT_AMOUNT,
    "commission_percent": COMMISSION_PERCENT,
    "bot_enabled": True,
    "coin_coeff": 2,
    "dice_odd_coeff": 3,
    "dice_exact_coeff": 10,
    "games": {"dice": True, "coin": True, "slot": True, "football": True},
    "leaderboard_enabled": True,
    "slot_coeffs": {
        "💎💎💎": 100, "⭐⭐⭐": 50, "７７７": 20,
        "🍇🍇🍇": 15, "🍋🍋🍋": 10, "🍒🍒🍒": 5, "two_same": 2
    }
})

def get_user(user_id):
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "balance": INITIAL_BALANCE,
            "username": None,
            "free_gift_used": False,
            "referral_code": generate_referral_code(),
            "referred_by": None,
            "referral_count": 0,
            "referral_gift": 0,
            "referral_commission": 0,
            "commission_percent": COMMISSION_PERCENT,
            "banned": False,
            "total_bets": 0,
            "total_wins": 0,
            "total_losses": 0,
            "has_deposited": False,
            "transactions": [],
            "created_at": str(datetime.now()),
            "campaign_code": None
        }
        save_json(DATA_FILE, users)
    return users[uid]

def save_user(user_id, data):
    users[str(user_id)] = data
    save_json(DATA_FILE, users)

def generate_referral_code():
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=8))

def add_transaction(user_id, amount, trans_type, description=""):
    user = get_user(user_id)
    user["transactions"].append({
        "date": datetime.now().strftime("%Y/%m/%d - %H:%M"),
        "type": trans_type,
        "amount": amount,
        "balance_after": user["balance"],
        "description": description
    })
    if len(user["transactions"]) > 100:
        user["transactions"] = user["transactions"][-100:]
    save_user(user_id, user)

withdrawals_history = []
scheduler = AsyncIOScheduler()

def generate_random_user_id():
    return f"#{random.randint(10000, 99999)}"

def generate_random_amount():
    rand = random.random()
    if rand < 0.70:
        return random.randint(500000, 1000000)
    elif rand < 0.90:
        return random.randint(1000000, 5000000)
    elif rand < 0.98:
        return random.randint(5000000, 10000000)
    else:
        return random.randint(10000000, 15000000)

def add_withdrawal():
    global withdrawals_history
    now = datetime.now()
    new_withdrawal = {
        "time": now.strftime("%H:%M"),
        "user_id": generate_random_user_id(),
        "amount": generate_random_amount(),
        "status": "✅ پرداخت شد"
    }
    withdrawals_history.insert(0, new_withdrawal)
    if len(withdrawals_history) > 50:
        withdrawals_history = withdrawals_history[:50]

def schedule_withdrawals():
    def job():
        add_withdrawal()
        next_interval = random.randint(2, 10)
        scheduler.add_job(job, 'interval', minutes=next_interval, id='withdrawal_job')
    scheduler.add_job(job, 'interval', minutes=1, id='start_withdrawal')

def get_withdrawals():
    return withdrawals_history[:5]

def add_commission_to_referrer(referred_user_id, deposit_amount):
    referred_user = get_user(referred_user_id)
    referrer_code = referred_user.get("referred_by")
    if not referrer_code:
        return
    referrer_id = None
    for uid, data in users.items():
        if data.get("referral_code") == referrer_code:
            referrer_id = int(uid)
            break
    if not referrer_id:
        return
    referrer = get_user(referrer_id)
    commission_percent = referrer.get("commission_percent", COMMISSION_PERCENT)
    commission = int(deposit_amount * (commission_percent / 100))
    referrer["balance"] += commission
    referrer["referral_commission"] = referrer.get("referral_commission", 0) + commission
    add_transaction(referrer_id, commission, "commission", "کمیسیون از واریز زیرمجموعه")
    save_user(referrer_id, referrer)

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    if user.get("banned", False):
        await query.edit_message_text("⛔ حساب شما مسدود شده است!")
        return
    keyboard = [
        [InlineKeyboardButton("🎲 شروع بازی", callback_data="game_menu")],
        [InlineKeyboardButton("👤 حساب من", callback_data="my_account")],
        [InlineKeyboardButton("🎁 دریافت شارژ هدیه", callback_data="gift")],
        [InlineKeyboardButton("🏆 آخرین برداشت‌ها", callback_data="withdrawals_list")],
        [InlineKeyboardButton("🏆 لیگ برندگان", callback_data="leaderboard")],
        [InlineKeyboardButton("❓ چطور اعتماد کنم", callback_data="trust")],
        [InlineKeyboardButton("🆘 پشتیبانی", callback_data="support")]
    ]
    text = f"🎰 **شرطینو**\n\n👤 کاربر: @{user['username'] or 'کاربر'}\n💰 موجودی: {user['balance']:,} تومان\n\nبا تحلیل لحظه‌ای و سیگنال‌های دقیق\nو اولین سودت رو همین امروز بگیر!\n\n✅ با ریال می‌تونی برداشت کنی\n👥 با دعوت هر دوست {GIFT_AMOUNT:,} تومان هدیه"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    user = get_user(user_id)
    user["username"] = username
    save_user(user_id, user)
    if context.args and context.args[0].startswith("camp_"):
        camp_code = context.args[0]
        campaign = admin_config.get("campaigns", {}).get(camp_code)
        if campaign:
            if user_id not in campaign.get("users", []):
                campaign["clicks"] = campaign.get("clicks", 0) + 1
                campaign["users"] = campaign.get("users", []) + [user_id]
                user["campaign_code"] = camp_code
                save_user(user_id, user)
                save_json(ADMIN_CONFIG_FILE, admin_config)
    if context.args and context.args[0].startswith("ref_"):
        ref_code = context.args[0][4:]
        for uid, data in users.items():
            if data.get("referral_code") == ref_code and int(uid) != user_id:
                user["referred_by"] = ref_code
                save_user(user_id, user)
                break
    channels = admin_config.get("channels", [{"link": CHANNEL, "enabled": True}])
    enabled_channels = [c for c in channels if c.get("enabled", True)]
    channel_count = len(enabled_channels)
    if not user.get("free_gift_used", False):
        keyboard = []
        for i, channel in enumerate(enabled_channels, 1):
            link = channel["link"]
            label = f"📢 عضویت در کانال {i}" if channel_count > 1 else "📢 عضویت در کانال"
            keyboard.append([InlineKeyboardButton(label, url=f"https://t.me/{link[1:]}")])
        keyboard.append([InlineKeyboardButton("✅ عضو شدم", callback_data="check_gift")])
        if channel_count == 1:
            channels_text = f"1️⃣ {enabled_channels[0]['link']}"
            channel_word = "کانال"
            channel_word2 = "کانال"
            channel_word3 = "کانال بالا"
        else:
            channels_text = "\n".join([f"{i+1}️⃣ {c['link']}" for i, c in enumerate(enabled_channels)])
            channel_word = "کانال‌ها"
            channel_word2 = "کانال‌های"
            channel_word3 = "کانال‌های بالا"
        gift_amount = admin_config.get("gift_amount", GIFT_AMOUNT)
        text = f"🎁 **{gift_amount:,} تومان شارژ هدیه:**\n\nفقط با عضویت در {channel_word2} اطلاع‌رسانی ما، شارژ هدیه دریافت کنید!\n\n📌 **{channel_word} مورد نیاز:**\n\n{channels_text}\n\nبرای دریافت شارژ هدیه، ابتدا در {channel_word3} عضو شوید.\n\nپس از عضویت، روی دکمه «✅ عضو شدم» کلیک کنید."
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        keyboard = [
            [InlineKeyboardButton("🎲 شروع بازی", callback_data="game_menu")],
            [InlineKeyboardButton("👤 حساب من", callback_data="my_account")],
            [InlineKeyboardButton("🎁 دریافت شارژ هدیه", callback_data="gift")],
            [InlineKeyboardButton("🏆 آخرین برداشت‌ها", callback_data="withdrawals_list")],
            [InlineKeyboardButton("🏆 لیگ برندگان", callback_data="leaderboard")],
            [InlineKeyboardButton("❓ چطور اعتماد کنم", callback_data="trust")],
            [InlineKeyboardButton("🆘 پشتیبانی", callback_data="support")]
        ]
        await update.message.reply_text(
            f"🎰 **شرطینو**\n\n👤 کاربر: @{username or 'کاربر'}\n💰 موجودی: {user['balance']:,} تومان\n\nبا تحلیل لحظه‌ای و سیگنال‌های دقیق\nو اولین سودت رو همین امروز بگیر!\n\n✅ با ریال می‌تونی برداشت کنی\n👥 با دعوت هر دوست {admin_config.get('gift_amount', GIFT_AMOUNT):,} تومان هدیه",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )

async def check_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    channels = admin_config.get("channels", [{"link": CHANNEL, "enabled": True}])
    enabled_channels = [c for c in channels if c.get("enabled", True)]
    all_member = True
    for channel in enabled_channels:
        try:
            member = await context.bot.get_chat_member(chat_id=channel["link"], user_id=user_id)
            if member.status not in ["member", "administrator", "creator"]:
                all_member = False
                break
        except:
            all_member = False
            break
    if all_member:
        gift_amount = admin_config.get("gift_amount", GIFT_AMOUNT)
        user["free_gift_used"] = True
        user["balance"] += gift_amount
        add_transaction(user_id, gift_amount, "gift", "شارژ هدیه عضویت در کانال")
        save_user(user_id, user)
        referrer_code = user.get("referred_by")
        if referrer_code:
            for uid, data in users.items():
                if data.get("referral_code") == referrer_code:
                    referrer_id = int(uid)
                    referrer = get_user(referrer_id)
                    referrer["balance"] += gift_amount
                    referrer["referral_count"] = referrer.get("referral_count", 0) + 1
                    referrer["referral_gift"] = referrer.get("referral_gift", 0) + gift_amount
                    add_transaction(referrer_id, gift_amount, "referral_gift", "هدیه دعوت")
                    save_user(referrer_id, referrer)
                    try:
                        await context.bot.send_message(
                            referrer_id,
                            f"🎉 **یک عضو جدید با لینک شما عضو شد!**\n\n👤 کاربر جدید: @{user['username'] or user_id}\n🎁 شارژ هدیه: {gift_amount:,} تومان به حساب شما اضافه شد.\n\n📊 آمار دعوت‌های شما:\n👥 کل دعوت‌ها: {referrer.get('referral_count', 0)}\n💰 کل هدیه دریافتی: {referrer.get('referral_gift', 0):,} تومان",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
                    break
        await query.edit_message_text(
            f"✅ **تبریک! عضویت شما تأیید شد.**\n\n🎁 {gift_amount:,} تومان شارژ هدیه به حساب شما اضافه شد.\n💰 موجودی جدید: {user['balance']:,} تومان",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎲 شروع بازی", callback_data="game_menu")],
                [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
            ]),
            parse_mode="Markdown"
        )
    else:
        keyboard = []
        for i, channel in enumerate(enabled_channels, 1):
            link = channel["link"]
            label = f"📢 عضویت در کانال {i}" if len(enabled_channels) > 1 else "📢 عضویت در کانال"
            keyboard.append([InlineKeyboardButton(label, url=f"https://t.me/{link[1:]}")])
        keyboard.append([InlineKeyboardButton("✅ عضو شدم", callback_data="check_gift")])
        await query.edit_message_text(
            f"❌ شما هنوز در همه کانال‌ها عضو نشده‌اید!\n\nلطفاً ابتدا در همه کانال‌های بالا عضو شوید، سپس دوباره روی «عضو شدم» کلیک کنید.",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )

async def game_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    games = admin_config.get("games", {})
    keyboard = []
    if games.get("dice", True):
        keyboard.append([InlineKeyboardButton("🎲 تاس", callback_data="dice_game")])
    if games.get("coin", True):
        keyboard.append([InlineKeyboardButton("🪙 شیر یا خط", callback_data="coin_game")])
    if games.get("slot", True):
        keyboard.append([InlineKeyboardButton("🎰 اسلات", callback_data="slot_game")])
    if games.get("football", True):
        keyboard.append([InlineKeyboardButton("⚽ فوتبال", callback_data="football_game")])
    keyboard.append([InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")])
    await query.edit_message_text("🎮 **بازی‌های شرطینو**\n\nلطفاً یک بازی را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def dice_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    if user.get("banned", False):
        await query.edit_message_text("⛔ حساب شما مسدود شده است!")
        return
    context.user_data["game"] = "dice"
    await query.edit_message_text(
        f"🎲 **بازی تاس**\n\n💰 موجودی شما: {user['balance']:,} تومان\n📌 حداقل مبلغ شرط: {admin_config.get('min_bet', MIN_BET):,} تومان\n\nمبلغ شرط خود را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]]),
        parse_mode="Markdown"
    )

async def coin_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    if user.get("banned", False):
        await query.edit_message_text("⛔ حساب شما مسدود شده است!")
        return
    context.user_data["game"] = "coin"
    await query.edit_message_text(
        f"🪙 **شیر یا خط**\n\n💰 موجودی شما: {user['balance']:,} تومان\n📌 حداقل مبلغ شرط: {admin_config.get('min_bet', MIN_BET):,} تومان\n\n📌 عدد زوج = شیر 🦁 | عدد فرد = خط 📍\n\nمبلغ شرط خود را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]]),
        parse_mode="Markdown"
    )

async def slot_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    if user.get("banned", False):
        await query.edit_message_text("⛔ حساب شما مسدود شده است!")
        return
    context.user_data["game"] = "slot"
    slot_coeffs = admin_config.get("slot_coeffs", {})
    await query.edit_message_text(
        f"🎰 **بازی اسلات**\n\n💰 موجودی شما: {user['balance']:,} تومان\n📌 حداقل مبلغ شرط: {admin_config.get('min_bet', MIN_BET):,} تومان\n\n📊 **ضرایب:**\n💎💎💎 = {slot_coeffs.get('💎💎💎', 100)}× | ⭐⭐⭐ = {slot_coeffs.get('⭐⭐⭐', 50)}×\n۷۷۷ = {slot_coeffs.get('۷۷۷', 20)}× | 🍇🍇🍇 = {slot_coeffs.get('🍇🍇🍇', 15)}×\n🍋🍋🍋 = {slot_coeffs.get('🍋🍋🍋', 10)}× | 🍒🍒🍒 = {slot_coeffs.get('🍒🍒🍒', 5)}×\n۲ تا یکسان = {slot_coeffs.get('two_same', 2)}×\n\nمبلغ شرط خود را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]]),
        parse_mode="Markdown"
    )

async def football_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    if user.get("banned", False):
        await query.edit_message_text("⛔ حساب شما مسدود شده است!")
        return
    context.user_data["game"] = "football"
    await query.edit_message_text(
        f"⚽ **بازی فوتبال**\n\n💰 موجودی شما: {user['balance']:,} تومان\n📌 حداقل مبلغ شرط: {admin_config.get('min_bet', MIN_BET):,} تومان\n\nمبلغ شرط خود را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]]),
        parse_mode="Markdown"
    )

async def handle_bet_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if user.get("banned", False):
        await update.message.reply_text("⛔ حساب شما مسدود شده است!")
        return
    try:
        amount = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید.")
        return
    min_bet = admin_config.get("min_bet", MIN_BET)
    if amount < min_bet:
        await update.message.reply_text(f"❌ حداقل مبلغ شرط {min_bet:,} تومان است.")
        return
    if amount > user["balance"]:
        await update.message.reply_text(f"❌ موجودی شما کافی نیست!\n💰 موجودی شما: {user['balance']:,} تومان")
        return
    context.user_data["bet_amount"] = amount
    game = context.user_data.get("game", "dice")
    if game == "dice":
        keyboard = [
            [InlineKeyboardButton("🟢 زوج | ضریب ۳", callback_data="dice_even")],
            [InlineKeyboardButton("🔵 فرد | ضریب ۳", callback_data="dice_odd")],
            [InlineKeyboardButton("۱ | ضریب ۱۰", callback_data="dice_1")],
            [InlineKeyboardButton("۲ | ضریب ۱۰", callback_data="dice_2")],
            [InlineKeyboardButton("۳ | ضریب ۱۰", callback_data="dice_3")],
            [InlineKeyboardButton("۴ | ضریب ۱۰", callback_data="dice_4")],
            [InlineKeyboardButton("۵ | ضریب ۱۰", callback_data="dice_5")],
            [InlineKeyboardButton("۶ | ضریب ۱۰", callback_data="dice_6")],
            [InlineKeyboardButton("🔙 انصراف", callback_data="main_menu")]
        ]
        await update.message.reply_text(
            f"🎲 **انتخاب پیش‌بینی**\n\n💰 مبلغ شرط: {amount:,} تومان",
            reply_markup=InlineKeyboardMarkup([keyboard[i:i+2] for i in range(0, len(keyboard), 2)]),
            parse_mode="Markdown"
        )
    elif game == "coin":
        keyboard = [
            [InlineKeyboardButton("🦁 شیر", callback_data="coin_heads")],
            [InlineKeyboardButton("📍 خط", callback_data="coin_tails")],
            [InlineKeyboardButton("🔙 انصراف", callback_data="main_menu")]
        ]
        await update.message.reply_text(
            f"🪙 **انتخاب شیر یا خط**\n\n💰 مبلغ شرط: {amount:,} تومان\n\n📌 عدد زوج = شیر 🦁 | عدد فرد = خط 📍",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif game == "slot":
        await update.message.reply_text(
            f"🎰 **اسلات**\n\n💰 مبلغ شرط: {amount:,} تومان",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎰 چرخش اسلات", callback_data="slot_spin")],
                [InlineKeyboardButton("🔙 انصراف", callback_data="main_menu")]
            ]),
            parse_mode="Markdown"
        )
    elif game == "football":
        keyboard = [
            [InlineKeyboardButton("⚽️ گل می‌شود (ضریب ۲)", callback_data="football_goal")],
            [InlineKeyboardButton("❌ گل نمی‌شود (ضریب ۲)", callback_data="football_miss")],
            [InlineKeyboardButton("🔙 انصراف", callback_data="main_menu")]
        ]
        await update.message.reply_text(
            f"⚽ **پیش‌بینی فوتبال**\n\n💰 مبلغ شرط: {amount:,} تومان\n\nتوپ به سمت دروازه شوت می‌شود!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def dice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    bet_amount = context.user_data.get("bet_amount", 0)
    choice = query.data.split("_")[1]
    dice_message = await query.message.reply_dice(emoji="🎲")
    dice_value = dice_message.dice.value
    is_win = False
    coefficient = 0
    if choice == "even":
        coefficient = admin_config.get("dice_odd_coeff", 3)
        is_win = dice_value in [2, 4, 6]
        choice_name = "زوج"
    elif choice == "odd":
        coefficient = admin_config.get("dice_odd_coeff", 3)
        is_win = dice_value in [1, 3, 5]
        choice_name = "فرد"
    else:
        coefficient = admin_config.get("dice_exact_coeff", 10)
        is_win = int(choice) == dice_value
        choice_name = f"عدد {choice}"
    if is_win:
        win_amount = bet_amount * coefficient
        user["balance"] += win_amount
        user["total_wins"] += 1
        result_text = f"🎉 **تبریک! شما برنده شدید!**\n\n🎲 نتیجه تاس: {dice_value}\n🎯 پیش‌بینی: {choice_name}\n💰 مبلغ شرط: {bet_amount:,} تومان\n📊 ضریب: {coefficient}\n🏆 جایزه: {win_amount:,} تومان\n\n💰 موجودی جدید: {user['balance']:,} تومان"
        add_transaction(user_id, win_amount, "win", f"برد در تاس - {choice_name}")
    else:
        user["balance"] -= bet_amount
        user["total_losses"] += 1
        result_text = f"😔 **متاسفم... شما باختید.**\n\n🎲 نتیجه تاس: {dice_value}\n🎯 پیش‌بینی: {choice_name}\n💰 مبلغ شرط: {bet_amount:,} تومان\n💰 موجودی جدید: {user['balance']:,} تومان"
        add_transaction(user_id, -bet_amount, "bet", f"باخت در تاس - {choice_name}")
    user["total_bets"] += 1
    save_user(user_id, user)
    keyboard = [
        [InlineKeyboardButton("🎲 دوباره", callback_data="dice_game")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    await query.edit_message_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def coin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    bet_amount = context.user_data.get("bet_amount", 0)
    choice = query.data.split("_")[1]
    dice_message = await query.message.reply_dice(emoji="🎲")
    dice_value = dice_message.dice.value
    is_heads = dice_value in [2, 4, 6]
    result_name = "شیر 🦁" if is_heads else "خط 📍"
    is_win = (choice == "heads" and is_heads) or (choice == "tails" and not is_heads)
    if is_win:
        win_amount = bet_amount * admin_config.get("coin_coeff", 2)
        user["balance"] += win_amount
        user["total_wins"] += 1
        result_text = f"🎉 **تبریک! شما برنده شدید!**\n\n🪙 نتیجه سکه: {result_name}\n🎲 عدد تاس: {dice_value} ({'زوج' if is_heads else 'فرد'})\n💰 مبلغ شرط: {bet_amount:,} تومان\n📊 ضریب: {admin_config.get('coin_coeff', 2)}\n🏆 جایزه: {win_amount:,} تومان\n\n💰 موجودی جدید: {user['balance']:,} تومان"
        add_transaction(user_id, win_amount, "win", "برد در شیر یا خط")
    else:
        user["balance"] -= bet_amount
        user["total_losses"] += 1
        result_text = f"😔 **متاسفم... شما باختید.**\n\n🪙 نتیجه سکه: {result_name}\n🎲 عدد تاس: {dice_value} ({'زوج' if is_heads else 'فرد'})\n💰 مبلغ شرط: {bet_amount:,} تومان\n💰 موجودی جدید: {user['balance']:,} تومان"
        add_transaction(user_id, -bet_amount, "bet", "باخت در شیر یا خط")
    user["total_bets"] += 1
    save_user(user_id, user)
    keyboard = [
        [InlineKeyboardButton("🪙 دوباره", callback_data="coin_game")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    await query.edit_message_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def slot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    bet_amount = context.user_data.get("bet_amount", 0)
    dice_message = await query.message.reply_dice(emoji="🎰")
    dice_value = dice_message.dice.value
    slot_emojis = ["💎", "⭐", "７", "🍇", "🍋", "🍒"]
    result = [slot_emojis[(dice_value // 4) % 6], slot_emojis[(dice_value // 1) % 6], slot_emojis[(dice_value * 3) % 6]]
    combo = "".join(result)
    slot_coeffs = admin_config.get("slot_coeffs", {})
    coefficient = slot_coeffs.get(combo, 0)
    if coefficient == 0 and (result[0] == result[1] or result[1] == result[2] or result[0] == result[2]):
        coefficient = slot_coeffs.get("two_same", 2)
    if coefficient > 0:
        win_amount = bet_amount * coefficient
        user["balance"] += win_amount
        user["total_wins"] += 1
        result_text = f"🎉 **تبریک! شما برنده شدید!**\n\n🎰 نتیجه اسلات:\n[ {result[0]} ] [ {result[1]} ] [ {result[2]} ]\n\n📊 ترکیب: {combo}\n🎯 ضریب: {coefficient}×\n💰 مبلغ شرط: {bet_amount:,} تومان\n🏆 جایزه: {win_amount:,} تومان\n\n💰 موجودی جدید: {user['balance']:,} تومان"
        add_transaction(user_id, win_amount, "win", f"برد در اسلات - {combo}")
    else:
        user["balance"] -= bet_amount
        user["total_losses"] += 1
        result_text = f"😔 **متاسفم... شما باختید.**\n\n🎰 نتیجه اسلات:\n[ {result[0]} ] [ {result[1]} ] [ {result[2]} ]\n\n📊 ترکیب: {combo}\n🎯 ضریب: ۰\n💰 مبلغ شرط: {bet_amount:,} تومان\n💰 موجودی جدید: {user['balance']:,} تومان"
        add_transaction(user_id, -bet_amount, "bet", "باخت در اسلات")
    user["total_bets"] += 1
    save_user(user_id, user)
    keyboard = [
        [InlineKeyboardButton("🎰 دوباره", callback_data="slot_game")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    await query.edit_message_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def football_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    bet_amount = context.user_data.get("bet_amount", 0)
    prediction = query.data.split("_")[1]
    dice_message = await query.message.reply_dice(emoji="⚽")
    dice_value = dice_message.dice.value
    is_goal = dice_value >= 4
    result_text = "گل شد ✅" if is_goal else "گل نشد ❌"
    is_win = (prediction == "goal" and is_goal) or (prediction == "miss" and not is_goal)
    if is_win:
        win_amount = bet_amount * 2
        user["balance"] += win_amount
        user["total_wins"] += 1
        result_msg = f"🎉 **تبریک! شما برنده شدید!**\n\n⚽ نتیجه شوت: {result_text}\n🎯 پیش‌بینی شما: {'گل می‌شود' if prediction == 'goal' else 'گل نمی‌شود'} (درست)\n💰 مبلغ شرط: {bet_amount:,} تومان\n📊 ضریب: ۲×\n🏆 جایزه: {win_amount:,} تومان\n\n💰 موجودی جدید: {user['balance']:,} تومان"
        add_transaction(user_id, win_amount, "win", "برد در فوتبال")
    else:
        user["balance"] -= bet_amount
        user["total_losses"] += 1
        result_msg = f"😔 **متاسفم... شما باختید.**\n\n⚽ نتیجه شوت: {result_text}\n🎯 پیش‌بینی شما: {'گل می‌شود' if prediction == 'goal' else 'گل نمی‌شود'}\n💰 مبلغ شرط: {bet_amount:,} تومان\n💰 موجودی جدید: {user['balance']:,} تومان"
        add_transaction(user_id, -bet_amount, "bet", "باخت در فوتبال")
    user["total_bets"] += 1
    save_user(user_id, user)
    keyboard = [
        [InlineKeyboardButton("⚽ دوباره", callback_data="football_game")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    await query.edit_message_text(result_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    if user.get("banned", False):
        await query.edit_message_text("⛔ حساب شما مسدود شده است!")
        return
    total_bets = user.get("total_bets", 0)
    wins = user.get("total_wins", 0)
    losses = user.get("total_losses", 0)
    win_rate = round((wins / total_bets * 100) if total_bets > 0 else 0, 1)
    text = f"👤 **حساب من**\n\n🆔 کاربر شماره: {user_id}\n👥 دعوت‌های موفق: {user.get('referral_count', 0)}\n📊 تعداد پیش‌بینی‌ها: {total_bets} | برد: {wins} | باخت: {losses}\n📈 نرخ برد: {win_rate}%\n💰 موجودی: {user['balance']:,} تومان"
    keyboard = [
        [InlineKeyboardButton("💳 واریز وجه", callback_data="deposit")],
        [InlineKeyboardButton("🏦 برداشت موجودی", callback_data="withdraw")],
        [InlineKeyboardButton("📜 تاریخچه تراکنش‌ها", callback_data="transactions")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"💳 **واریز وجه**\n\n💰 حداقل مبلغ واریز: {admin_config.get('min_deposit', 500000):,} تومان\n\nلطفاً مبلغ مورد نظر برای واریز را وارد کنید:\n\n(مثال: 1000000)",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]]),
        parse_mode="Markdown"
    )
    context.user_data["admin_action"] = "deposit_amount"

async def handle_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if user.get("banned", False):
        await update.message.reply_text("⛔ حساب شما مسدود شده است!")
        return
    try:
        amount = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید.")
        return
    min_deposit = admin_config.get("min_deposit", 500000)
    if amount < min_deposit:
        await update.message.reply_text(
            f"❌ مبلغ وارد شده کمتر از حداقل مجاز است!\n\n💰 حداقل مبلغ واریز: {min_deposit:,} تومان\n🎯 مبلغ وارد شده: {amount:,} تومان\n\nلطفاً مبلغی برابر یا بیشتر از {min_deposit:,} تومان وارد کنید."
        )
        return
    context.user_data["deposit_amount"] = amount
    trx_wallet = admin_config.get("trx_wallet", TRX_WALLET)
    usdt_wallet = admin_config.get("usdt_wallet", USDT_WALLET)
    text = f"""💳 **تأیید مبلغ واریز**

💰 مبلغ واریز: {amount:,} تومان
🎁 هدیه واریز اول: ۵۰٪ بیشتر (در صورت اولین واریز)

━━━━━━━━━━━━━━━━━━━━━━
📌 **شماره کارت جهت واریز ریالی:**
`60376976********`

⚠️ واریز ریالی تا تاریخ ۳۰ مرداد‌ماه فعال نیست.

━━━━━━━━━━━━━━━━━━━━━━
🟣 **آدرس ولت ترون (TRX):**
`{trx_wallet}`

[ 📋 کپی آدرس ولت ترون ]

━━━━━━━━━━━━━━━━━━━━━━
🟢 **آدرس ولت تتر (USDT-TRC20):**
`{usdt_wallet}`

[ 📋 کپی آدرس ولت تتر ]

━━━━━━━━━━━━━━━━━━━━━━
📌 **آموزش واریز ارز دیجیتال:**

برای مشاهده آموزش کامل واریز، وارد کانال زیر شوید:

📢 @shartino_amoozesh

━━━━━━━━━━━━━━━━━━━━━━
📌 **پس از واریز، حتماً اسکرین‌شات خود را به پشتیبانی ارسال کنید.**

🆘 @shartino_sup"""
    keyboard = [
        [InlineKeyboardButton("📋 کپی آدرس ولت ترون", callback_data="copy_trx")],
        [InlineKeyboardButton("📋 کپی آدرس ولت تتر", callback_data="copy_usdt")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def copy_trx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.answer(f"✅ آدرس ولت ترون کپی شد:\n{admin_config.get('trx_wallet', TRX_WALLET)}", show_alert=True)

async def copy_usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.answer(f"✅ آدرس ولت تتر کپی شد:\n{admin_config.get('usdt_wallet', USDT_WALLET)}", show_alert=True)

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    if user.get("banned", False):
        await query.edit_message_text("⛔ حساب شما مسدود شده است!")
        return
    if not user.get("has_deposited", False):
        await query.edit_message_text(
            f"❌ **برداشت غیرمجاز!**\n\nشما تاکنون هیچ واریزی به ربات نداشته‌اید.\n\n📌 برداشت تنها پس از **اولین واریز** امکان‌پذیر است.\n\nبرای واریز، از بخش «💳 واریز وجه» اقدام کنید.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 واریز وجه", callback_data="deposit")],
                [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
            ]),
            parse_mode="Markdown"
        )
        return
    await query.edit_message_text(
        f"🏦 **برداشت موجودی**\n\n💰 موجودی قابل برداشت: {user['balance']:,} تومان\n📌 حداقل مبلغ برداشت: {admin_config.get('min_withdraw', MIN_WITHDRAW):,} تومان\n\nلطفاً مبلغ مورد نظر را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]]),
        parse_mode="Markdown"
    )

async def handle_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if user.get("banned", False):
        await update.message.reply_text("⛔ حساب شما مسدود شده است!")
        return
    try:
        amount = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید.")
        return
    min_withdraw = admin_config.get("min_withdraw", MIN_WITHDRAW)
    if amount > user["balance"]:
        await update.message.reply_text(f"❌ موجودی شما کافی نیست!\n💰 موجودی شما: {user['balance']:,} تومان")
        return
    if amount < min_withdraw:
        await update.message.reply_text(f"❌ حداقل مبلغ برداشت {min_withdraw:,} تومان است.")
        return
    context.user_data["withdraw_amount"] = amount
    keyboard = [
        [InlineKeyboardButton("💳 شماره کارت", callback_data="withdraw_card")],
        [InlineKeyboardButton("🟣 آدرس ولت (TRX)", callback_data="withdraw_wallet")],
        [InlineKeyboardButton("🔙 انصراف", callback_data="main_menu")]
    ]
    await update.message.reply_text(
        f"✅ مبلغ {amount:,} تومان برای برداشت ثبت شد.\n\nلطفاً یکی از روش‌های زیر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )

async def withdraw_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("💳 **برداشت با شماره کارت**\n\nلطفاً شماره کارت ۱۶ رقمی خود را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 انصراف", callback_data="main_menu")]]))
    context.user_data["withdraw_method"] = "card"

async def withdraw_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🟣 **برداشت با آدرس ولت (TRX)**\n\nلطفاً آدرس ولت ترون خود را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 انصراف", callback_data="main_menu")]]))
    context.user_data["withdraw_method"] = "wallet"

async def handle_withdraw_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    info = update.message.text.strip()
    amount = context.user_data.get("withdraw_amount", 0)
    method = context.user_data.get("withdraw_method", "unknown")
    if user.get("banned", False):
        await update.message.reply_text("⛔ حساب شما مسدود شده است!")
        return
    user["balance"] -= amount
    add_transaction(user_id, -amount, "withdraw", f"برداشت - {method}")
    save_user(user_id, user)
    method_name = "شماره کارت" if method == "card" else "آدرس ولت"
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, f"🏦 **درخواست برداشت جدید**\n\n👤 کاربر: @{user['username'] or user_id}\n💰 مبلغ: {amount:,} تومان\n📌 روش: {method_name}\n📋 اطلاعات: {info}")
        except:
            pass
    await update.message.reply_text(
        f"✅ **درخواست برداشت شما ثبت شد!**\n\n💰 مبلغ: {amount:,} تومان\n🕒 درخواست شما در صف پردازش قرار گرفت.\nدر صورت نیاز به پشتیبانی: {SUPPORT}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]]),
        parse_mode="Markdown"
    )

async def transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    if user.get("banned", False):
        await query.edit_message_text("⛔ حساب شما مسدود شده است!")
        return
    trans = user.get("transactions", [])[-10:]
    if not trans:
        text = "📜 **تاریخچه تراکنش‌ها**\n\nهیچ تراکنشی ثبت نشده است."
    else:
        text = "📜 **تاریخچه تراکنش‌ها**\n\n"
        for t in trans[-10:]:
            emoji = "💰" if t["amount"] > 0 else "💸"
            text += f"{t['date']} | {emoji} {t['amount']:,} | موجودی: {t['balance_after']:,}\n"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 حساب من", callback_data="my_account")]]), parse_mode="Markdown")

async def gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    if user.get("banned", False):
        await query.edit_message_text("⛔ حساب شما مسدود شده است!")
        return
    bot_username = "shartinobot"
    link = f"https://t.me/{bot_username}?start=ref_{user['referral_code']}"
    commission_percent = user.get("commission_percent", COMMISSION_PERCENT)
    text = f"🎁 **دریافت شارژ هدیه و کمیسیون**\n\n📌 **درصد کمیسیون شما:** {commission_percent}%\n\n👤 هر دعوت موفق = {admin_config.get('gift_amount', GIFT_AMOUNT):,} تومان شارژ هدیه\n💰 از هر واریز زیرمجموعه = {commission_percent}% کمیسیون\n\n🔗 لینک دعوت اختصاصی:\n`{link}`\n\n📊 **آمار شما:**\n👥 دعوت‌های موفق: {user.get('referral_count', 0)}\n💰 شارژ هدیه: {user.get('referral_gift', 0):,} تومان\n💸 کمیسیون دریافتی: {user.get('referral_commission', 0):,} تومان"
    keyboard = [
        [InlineKeyboardButton("📋 کپی لینک دعوت", callback_data="copy_referral")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def copy_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    bot_username = "shartinobot"
    link = f"https://t.me/{bot_username}?start=ref_{user['referral_code']}"
    await query.answer(f"✅ لینک دعوت کپی شد:\n{link}", show_alert=True)

async def trust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"❓ **چطور اعتماد کنم**\n\nما درک می‌کنیم که اعتماد کردن به یک سرویس آنلاین ممکن است برای شما چالش‌برانگیز باشد.\n\nبه منظور اینکه شما با خیال آسوده شروع به فعالیت کنید، **{admin_config.get('gift_amount', GIFT_AMOUNT):,} تومان موجودی رایگان** هنگام عضویت به شما اهدا کردیم.\n\nما متعهد به ارائه تجربه‌ای لذت‌بخش و عادلانه برای تمام کاربران هستیم. ❤️",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]]),
        parse_mode="Markdown"
    )

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"🆘 **پشتیبانی**\n\nبرای ارتباط با پشتیبانی، به آیدی زیر پیام دهید:\n\n👨‍💻 {SUPPORT}\n\n⏳ پاسخگویی: ۲۴ ساعته، همه روزه",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]]),
        parse_mode="Markdown"
    )

async def withdrawals_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    withdrawals = get_withdrawals()
    if not withdrawals:
        text = "🏆 **آخرین برداشت‌ها**\n\nهیچ برداشتی ثبت نشده است."
    else:
        text = "🏆 **آخرین برداشت‌های موفق**\n\n📌 برداشت‌های لحظه‌ای:\n\n─────────────────────\n"
        for w in withdrawals:
            text += f"🕐 {w['time']} | کاربر {w['user_id']} | {w['amount']:,} تومان | {w['status']}\n"
        text += "\n─────────────────────\n📌 نمایش ۵ برداشت اخیر\n\n💡 برداشت‌ها به صورت لحظه‌ای ثبت می‌شوند."
    keyboard = [
        [InlineKeyboardButton("🔄 بروزرسانی", callback_data="refresh_withdrawals")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def refresh_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await withdrawals_list(update, context)

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not admin_config.get("leaderboard_enabled", True):
        await query.edit_message_text("⛔ لیگ برندگان در حال حاضر غیرفعال است.")
        return
    week_ago = datetime.now() - timedelta(days=7)
    weekly_wins = []
    for uid, data in users.items():
        if data.get("banned", False):
            continue
        total_win = 0
        for t in data.get("transactions", []):
            try:
                trans_date = datetime.strptime(t["date"].split(" - ")[0], "%Y/%m/%d")
                if trans_date >= week_ago and t["type"] == "win":
                    total_win += t["amount"]
            except:
                pass
        if total_win > 0:
            weekly_wins.append({
                "uid": uid,
                "username": data.get("username", "کاربر"),
                "total_win": total_win
            })
    weekly_wins.sort(key=lambda x: x["total_win"], reverse=True)
    top_10 = weekly_wins[:10]
    user_rank = None
    user_id = str(query.from_user.id)
    for i, item in enumerate(weekly_wins, 1):
        if item["uid"] == user_id:
            user_rank = i
            user_win = item["total_win"]
            break
    text = "🏆 **لیگ برندگان هفته**\n\n"
    text += f"📅 بازه: ۷ روز گذشته\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, item in enumerate(top_10, 1):
        medal = medals[i-1] if i <= 3 else f"{i}️⃣"
        text += f"{medal} @{item['username']} → {item['total_win']:,} تومان\n"
    if user_rank:
        text += f"\n━━━━━━━━━━━━━━━━━━━━━━\n📌 رتبه شما: #{user_rank} با {user_win:,} تومان"
    else:
        text += f"\n━━━━━━━━━━━━━━━━━━━━━━\n📌 شما هنوز در لیگ ثبت نشده‌اید! بازی کنید و برنده شوید."
    keyboard = [
        [InlineKeyboardButton("🔄 بروزرسانی", callback_data="refresh_leaderboard")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def refresh_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await leaderboard(update, context)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ این دستور فقط برای ادمین است.")
        return
    keyboard = [
        [InlineKeyboardButton("📊 آمار کل", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin_users")],
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="admin_settings")],
        [InlineKeyboardButton("📢 مدیریت کمپین", callback_data="admin_campaign")],
        [InlineKeyboardButton("🔙 بستن", callback_data="admin_close")]
    ]
    await update.message.reply_text("👑 **پنل مدیریت ربات شرطینو**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    total = len(users)
    total_balance = sum(u["balance"] for u in users.values())
    banned = sum(1 for u in users.values() if u.get("banned", False))
    text = f"📊 **آمار کل ربات**\n\n👥 کل کاربران: {total}\n🚫 کاربران مسدود: {banned}\n💰 کل موجودی: {total_balance:,} تومان"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]), parse_mode="Markdown")

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="admin_search")],
        [InlineKeyboardButton("💸 مدیریت موجودی", callback_data="admin_balance")],
        [InlineKeyboardButton("🚫 مسدود کردن کاربر", callback_data="admin_ban")],
        [InlineKeyboardButton("📨 ارسال همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🎁 شارژ همگانی", callback_data="admin_global_gift")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]
    ]
    await query.edit_message_text("👥 **مدیریت کاربران**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("📅 تغییر تاریخ واریز ریالی", callback_data="admin_set_date")],
        [InlineKeyboardButton("🔄 تغییر آدرس ولت‌ها", callback_data="admin_set_wallets")],
        [InlineKeyboardButton("🎯 تغییر حداقل مبالغ", callback_data="admin_change_limits")],
        [InlineKeyboardButton("🎲 مدیریت بازی‌ها", callback_data="admin_manage_games")],
        [InlineKeyboardButton("🔌 وضعیت ربات", callback_data="admin_toggle_bot")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]
    ]
    await query.edit_message_text("⚙️ **تنظیمات ربات**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("➕ ساخت لینک جدید", callback_data="admin_new_campaign")],
        [InlineKeyboardButton("📊 آمار لینک‌ها", callback_data="admin_campaign_stats")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]
    ]
    await query.edit_message_text("📢 **مدیریت کمپین‌های تبلیغاتی**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_new_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "➕ **ساخت لینک تبلیغاتی جدید**\n\n📝 نام کمپین را وارد کنید:\n\n(مثال: کانال_ترید_بزرگ)",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]])
    )
    context.user_data["admin_action"] = "new_campaign"

async def admin_campaign_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    campaigns = admin_config.get("campaigns", {})
    if not campaigns:
        text = "📊 **آمار کمپین‌ها**\n\nهیچ کمپینی ایجاد نشده است."
    else:
        text = "📊 **آمار کمپین‌های تبلیغاتی**\n\n"
        total_clicks = 0
        total_deposits = 0
        total_amount = 0
        for code, data in campaigns.items():
            name = data.get("name", code)
            clicks = data.get("clicks", 0)
            deposits = data.get("deposits", 0)
            amount = data.get("total_amount", 0)
            total_clicks += clicks
            total_deposits += deposits
            total_amount += amount
            rate = round((deposits / clicks * 100) if clicks > 0 else 0, 1)
            text += f"🔹 {name}\n   👥 ورودی: {clicks} | 💰 واریز: {deposits} | {amount:,} تومان\n   📈 نرخ تبدیل: {rate}%\n\n"
        text += f"━━━━━━━━━━━━━━━━━━━━━━\n📌 **مجموع کل:**\n👥 کل ورودی: {total_clicks}\n💰 کل واریز: {total_deposits} | {total_amount:,} تومان\n📈 نرخ تبدیل کل: {round((total_deposits / total_clicks * 100) if total_clicks > 0 else 0, 1)}%"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]), parse_mode="Markdown")

async def admin_manage_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    games = admin_config.get("games", {})
    text = "🎲 **مدیریت بازی‌ها**\n\nوضعیت فعلی:\n"
    for game, status in games.items():
        text += f"✅ {game}: {'فعال' if status else 'غیرفعال'}\n"
    keyboard = []
    for game in games.keys():
        keyboard.append([InlineKeyboardButton(f"🔄 تغییر وضعیت {game}", callback_data=f"admin_toggle_game_{game}")])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_toggle_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game = query.data.split("_")[3]
    games = admin_config.get("games", {})
    games[game] = not games.get(game, True)
    admin_config["games"] = games
    save_json(ADMIN_CONFIG_FILE, admin_config)
    await query.edit_message_text(
        f"✅ وضعیت بازی {game} با موفقیت تغییر کرد.\n📌 وضعیت جدید: {'فعال' if games[game] else 'غیرفعال'}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 مدیریت بازی‌ها", callback_data="admin_manage_games")]])
    )

async def admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await admin_panel(update, context)

async def admin_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔐 پنل ادمین بسته شد.")

async def admin_toggle_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    current = admin_config.get("bot_enabled", True)
    admin_config["bot_enabled"] = not current
    save_json(ADMIN_CONFIG_FILE, admin_config)
    status_text = "✅ فعال" if admin_config["bot_enabled"] else "❌ غیرفعال"
    await query.edit_message_text(
        f"🔌 **وضعیت ربات تغییر کرد!**\n\n📌 وضعیت جدید: {status_text}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 تغییر وضعیت", callback_data="admin_toggle_bot")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]
        ]),
        parse_mode="Markdown"
    )

async def admin_set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"📅 **تغییر تاریخ فعال‌سازی واریز ریالی**\n\n📌 تاریخ فعلی: {admin_config.get('deposit_enable_date', '۳۰ مرداد‌ماه')}\n\nتاریخ جدید را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]])
    )
    context.user_data["admin_action"] = "set_date"

async def admin_set_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"🔄 **تغییر آدرس ولت‌ها**\n\n🟣 ولت ترون فعلی:\n`{admin_config.get('trx_wallet', TRX_WALLET)}`\n\n🟢 ولت تتر فعلی:\n`{admin_config.get('usdt_wallet', USDT_WALLET)}`\n\nبرای تغییر، یکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ تغییر ولت ترون", callback_data="admin_edit_trx")],
            [InlineKeyboardButton("✏️ تغییر ولت تتر", callback_data="admin_edit_usdt")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]
        ]),
        parse_mode="Markdown"
    )

async def admin_edit_trx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"✏️ **تغییر آدرس ولت ترون (TRX)**\n\n📌 آدرس فعلی:\n`{admin_config.get('trx_wallet', TRX_WALLET)}`\n\nآدرس جدید را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]])
    )
    context.user_data["admin_action"] = "edit_trx"

async def admin_edit_usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"✏️ **تغییر آدرس ولت تتر (USDT-TRC20)**\n\n📌 آدرس فعلی:\n`{admin_config.get('usdt_wallet', USDT_WALLET)}`\n\nآدرس جدید را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]])
    )
    context.user_data["admin_action"] = "edit_usdt"

async def admin_change_limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"🎯 **تغییر حداقل مبالغ**\n\n💰 حداقل شرط: {admin_config.get('min_bet', MIN_BET):,} تومان\n💰 حداقل واریز: {admin_config.get('min_deposit', 500000):,} تومان\n💰 حداقل برداشت: {admin_config.get('min_withdraw', MIN_WITHDRAW):,} تومان\n\nکدام مبلغ را تغییر می‌دهید؟",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ حداقل شرط", callback_data="admin_edit_min_bet")],
            [InlineKeyboardButton("✏️ حداقل واریز", callback_data="admin_edit_min_deposit")],
            [InlineKeyboardButton("✏️ حداقل برداشت", callback_data="admin_edit_min_withdraw")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]
        ]),
        parse_mode="Markdown"
    )

async def admin_edit_min_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"✏️ **تغییر حداقل شرط**\n\n📌 حداقل شرط فعلی: {admin_config.get('min_bet', MIN_BET):,} تومان\n\nمبلغ جدید را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]])
    )
    context.user_data["admin_action"] = "edit_min_bet"

async def admin_edit_min_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"✏️ **تغییر حداقل واریز**\n\n📌 حداقل واریز فعلی: {admin_config.get('min_deposit', 500000):,} تومان\n\nمبلغ جدید را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]])
    )
    context.user_data["admin_action"] = "edit_min_deposit"

async def admin_edit_min_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"✏️ **تغییر حداقل برداشت**\n\n📌 حداقل برداشت فعلی: {admin_config.get('min_withdraw', MIN_WITHDRAW):,} تومان\n\nمبلغ جدید را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]])
    )
    context.user_data["admin_action"] = "edit_min_withdraw"

async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🚫 **مسدود کردن کاربر**\n\n🆔 آیدی عددی کاربر را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]))
    context.user_data["admin_action"] = "ban_user"

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📨 **ارسال پیام همگانی**\n\nمتن پیام را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]))
    context.user_data["admin_action"] = "broadcast"

async def admin_global_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🎁 **شارژ همگانی**\n\n💰 مبلغ جایزه را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]))
    context.user_data["admin_action"] = "global_gift"

async def admin_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("💸 **مدیریت موجودی کاربر**\n\n🆔 آیدی عددی کاربر را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]))
    context.user_data["admin_action"] = "balance_user"

async def admin_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔍 **جستجوی کاربر**\n\n🆔 آیدی عددی کاربر را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]))
    context.user_data["admin_action"] = "search_user"

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    action = context.user_data.get("admin_action")
    text = update.message.text.strip()

    if action == "set_date":
        admin_config["deposit_enable_date"] = text
        save_json(ADMIN_CONFIG_FILE, admin_config)
        await update.message.reply_text(f"✅ تاریخ با موفقیت تغییر کرد.\n📅 تاریخ جدید: {text}")
        context.user_data["admin_action"] = None

    elif action == "edit_trx":
        admin_config["trx_wallet"] = text
        save_json(ADMIN_CONFIG_FILE, admin_config)
        await update.message.reply_text(f"✅ آدرس ولت ترون با موفقیت تغییر کرد.\n🟣 آدرس جدید: `{text}`")
        context.user_data["admin_action"] = None

    elif action == "edit_usdt":
        admin_config["usdt_wallet"] = text
        save_json(ADMIN_CONFIG_FILE, admin_config)
        await update.message.reply_text(f"✅ آدرس ولت تتر با موفقیت تغییر کرد.\n🟢 آدرس جدید: `{text}`")
        context.user_data["admin_action"] = None

    elif action == "edit_min_bet":
        try:
            new = int(text)
            if new < 0:
                await update.message.reply_text("❌ مبلغ نمی‌تواند منفی باشد.")
                return
            admin_config["min_bet"] = new
            save_json(ADMIN_CONFIG_FILE, admin_config)
            await update.message.reply_text(f"✅ حداقل شرط تغییر کرد.\n💰 حداقل شرط جدید: {new:,} تومان")
        except:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید.")
        context.user_data["admin_action"] = None

    elif action == "edit_min_deposit":
        try:
            new = int(text)
            if new < 0:
                await update.message.reply_text("❌ مبلغ نمی‌تواند منفی باشد.")
                return
            admin_config["min_deposit"] = new
            save_json(ADMIN_CONFIG_FILE, admin_config)
            await update.message.reply_text(f"✅ حداقل واریز تغییر کرد.\n💰 حداقل واریز جدید: {new:,} تومان")
        except:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید.")
        context.user_data["admin_action"] = None

    elif action == "edit_min_withdraw":
        try:
            new = int(text)
            if new < 0:
                await update.message.reply_text("❌ مبلغ نمی‌تواند منفی باشد.")
                return
            admin_config["min_withdraw"] = new
            save_json(ADMIN_CONFIG_FILE, admin_config)
            await update.message.reply_text(f"✅ حداقل برداشت تغییر کرد.\n💰 حداقل برداشت جدید: {new:,} تومان")
        except:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید.")
        context.user_data["admin_action"] = None

    elif action == "ban_user":
        try:
            target = int(text)
            user = get_user(target)
            if target in ADMIN_IDS:
                await update.message.reply_text("❌ نمی‌توانید ادمین را مسدود کنید.")
                return
            user["banned"] = not user.get("banned", False)
            save_user(target, user)
            status = "مسدود" if user["banned"] else "آزاد"
            await update.message.reply_text(f"✅ کاربر با موفقیت {status} شد.")
            if user["banned"]:
                try:
                    await context.bot.send_message(target, "⛔ حساب شما مسدود شده است!")
                except:
                    pass
        except:
            await update.message.reply_text("❌ آیدی نامعتبر است.")
        context.user_data["admin_action"] = None

    elif action == "broadcast":
        success = 0
        fail = 0
        for uid, data in users.items():
            if data.get("banned", False):
                continue
            try:
                await context.bot.send_message(int(uid), f"📨 **پیام همگانی**\n\n{text}")
                success += 1
            except:
                fail += 1
        await update.message.reply_text(f"✅ **پیام همگانی ارسال شد!**\n\n👥 ارسال موفق: {success} نفر\n❌ ناموفق: {fail} نفر")
        context.user_data["admin_action"] = None

    elif action == "global_gift":
        try:
            amount = int(text)
            if amount < 0:
                await update.message.reply_text("❌ مبلغ نمی‌تواند منفی باشد.")
                return
            context.user_data["global_gift_amount"] = amount
            await update.message.reply_text("📝 پیام همراه (اختیاری، برای رد کردن 0 بزنید):")
            context.user_data["admin_action"] = "global_gift_message"
        except:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید.")

    elif action == "global_gift_message":
        amount = context.user_data.get("global_gift_amount", 0)
        message = text if text != "0" else "جایزه ویژه شرطینو"
        occasion = "جشنواره ویژه"
        success = 0
        fail = 0
        for uid, data in users.items():
            if data.get("banned", False):
                continue
            user = get_user(uid)
            user["balance"] += amount
            add_transaction(uid, amount, "gift", f"جایزه همگانی - {occasion}")
            save_user(uid, user)
            try:
                await context.bot.send_message(uid, f"🎁 **جایزه ویژه شرطینو**\n\nبه مناسبت **{occasion}**، مبلغ {amount:,} تومان به حساب شما اضافه شد.\n\n📝 {message}\n\n💰 موجودی جدید: {user['balance']:,} تومان", parse_mode="Markdown")
                success += 1
            except:
                fail += 1
        await update.message.reply_text(f"✅ **شارژ همگانی با موفقیت انجام شد!**\n\n💰 مبلغ شارژ: {amount:,} تومان\n👥 ارسال موفق: {success} نفر\n❌ ناموفق: {fail} نفر")
        context.user_data["admin_action"] = None
        context.user_data["global_gift_amount"] = 0

    elif action == "balance_user":
        try:
            target = int(text)
            user = get_user(target)
            await update.message.reply_text(
                f"👤 **اطلاعات کاربر**\n\n🆔 آیدی: {target}\n👤 یوزرنیم: @{user['username'] or 'کاربر'}\n💰 موجودی: {user['balance']:,} تومان\n📊 وضعیت: {'🚫 مسدود' if user.get('banned', False) else '✅ فعال'}\n💳 واریز کرده: {'✅ بله' if user.get('has_deposited', False) else '❌ خیر'}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ افزایش موجودی", callback_data=f"admin_add_{target}")],
                    [InlineKeyboardButton("➖ کاهش موجودی", callback_data=f"admin_remove_{target}")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]
                ]),
                parse_mode="Markdown"
            )
        except:
            await update.message.reply_text("❌ آیدی نامعتبر است.")
        context.user_data["admin_action"] = None

    elif action == "search_user":
        try:
            target = int(text)
            user = get_user(target)
            await update.message.reply_text(
                f"👤 **اطلاعات کاربر**\n\n🆔 آیدی: {target}\n👤 یوزرنیم: @{user['username'] or 'کاربر'}\n💰 موجودی: {user['balance']:,} تومان\n📊 وضعیت: {'🚫 مسدود' if user.get('banned', False) else '✅ فعال'}\n💳 واریز کرده: {'✅ بله' if user.get('has_deposited', False) else '❌ خیر'}\n📅 تاریخ عضویت: {user.get('created_at', 'نامشخص')}"
            )
        except:
            await update.message.reply_text("❌ آیدی نامعتبر است.")
        context.user_data["admin_action"] = None

    elif action == "new_campaign":
        name = text
        code = generate_referral_code()
        campaigns = admin_config.get("campaigns", {})
        campaigns[code] = {"name": name, "clicks": 0, "deposits": 0, "total_amount": 0, "users": []}
        admin_config["campaigns"] = campaigns
        save_json(ADMIN_CONFIG_FILE, admin_config)
        link = f"https://t.me/shartinobot?start=camp_{code}"
        await update.message.reply_text(
            f"✅ **لینک تبلیغاتی ساخته شد!**\n\n🔗 لینک کمپین:\n{link}\n\n📋 برای کپی روی دکمه زیر کلیک کنید:\n\n📊 **آمار این لینک:**\n👥 ورودی: ۰ نفر\n💰 واریز: ۰ نفر | ۰ تومان\n📈 نرخ تبدیل: ۰٪"
        )
        context.user_data["admin_action"] = None

async def admin_add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target = int(query.data.split("_")[2])
    context.user_data["admin_add_user"] = target
    await query.edit_message_text(
        f"➕ **افزایش موجودی کاربر**\n\n👤 کاربر: @{get_user(target)['username'] or target}\n💰 موجودی فعلی: {get_user(target)['balance']:,} تومان\n\nمبلغ مورد نظر را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 انصراف", callback_data="admin_back")]])
    )
    context.user_data["admin_action"] = "admin_add_balance"

async def admin_remove_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target = int(query.data.split("_")[2])
    context.user_data["admin_remove_user"] = target
    await query.edit_message_text(
        f"➖ **کاهش موجودی کاربر**\n\n👤 کاربر: @{get_user(target)['username'] or target}\n💰 موجودی فعلی: {get_user(target)['balance']:,} تومان\n\nمبلغ مورد نظر را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 انصراف", callback_data="admin_back")]])
    )
    context.user_data["admin_action"] = "admin_remove_balance"

async def handle_admin_balance_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    action = context.user_data.get("admin_action")
    try:
        amount = int(update.message.text.strip())
        if amount < 0:
            await update.message.reply_text("❌ مبلغ نمی‌تواند منفی باشد.")
            return
    except:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید.")
        return

    if action == "admin_add_balance":
        target = context.user_data.get("admin_add_user")
        user = get_user(target)
        user["balance"] += amount
        add_transaction(target, amount, "deposit", "واریز توسط ادمین")
        user["has_deposited"] = True
        save_user(target, user)
        await update.message.reply_text(f"✅ موجودی کاربر @{user['username'] or target} افزایش یافت.\n💰 مبلغ: {amount:,} تومان\n💰 موجودی جدید: {user['balance']:,} تومان")
        try:
            await context.bot.send_message(target, f"✅ **موجودی شما افزایش یافت!**\n\n💰 مبلغ: {amount:,} تومان\n💰 موجودی جدید: {user['balance']:,} تومان")
        except:
            pass

    elif action == "admin_remove_balance":
        target = context.user_data.get("admin_remove_user")
        user = get_user(target)
        if user["balance"] < amount:
            await update.message.reply_text(f"❌ موجودی کاربر کافی نیست!\n💰 موجودی: {user['balance']:,} تومان")
            return
        user["balance"] -= amount
        add_transaction(target, -amount, "admin_remove", "کاهش موجودی توسط ادمین")
        save_user(target, user)
        await update.message.reply_text(f"✅ موجودی کاربر @{user['username'] or target} کاهش یافت.\n💰 مبلغ: {amount:,} تومان\n💰 موجودی جدید: {user['balance']:,} تومان")
        try:
            await context.bot.send_message(target, f"⚠️ **موجودی شما کاهش یافت!**\n\n💰 مبلغ: {amount:,} تومان\n💰 موجودی جدید: {user['balance']:,} تومان")
        except:
            pass

    context.user_data["admin_action"] = None
    context.user_data["admin_add_user"] = None
    context.user_data["admin_remove_user"] = None

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ دستور نامعتبر. لطفاً از منو استفاده کنید.")

def main():
    logging.basicConfig(level=logging.INFO)
    schedule_withdrawals()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))

    app.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(game_menu, pattern="^game_menu$"))
    app.add_handler(CallbackQueryHandler(dice_game, pattern="^dice_game$"))
    app.add_handler(CallbackQueryHandler(coin_game, pattern="^coin_game$"))
    app.add_handler(CallbackQueryHandler(slot_game, pattern="^slot_game$"))
    app.add_handler(CallbackQueryHandler(football_game, pattern="^football_game$"))
    app.add_handler(CallbackQueryHandler(dice_callback, pattern="^dice_"))
    app.add_handler(CallbackQueryHandler(coin_callback, pattern="^coin_"))
    app.add_handler(CallbackQueryHandler(slot_callback, pattern="^slot_"))
    app.add_handler(CallbackQueryHandler(football_callback, pattern="^football_"))

    app.add_handler(CallbackQueryHandler(my_account, pattern="^my_account$"))
    app.add_handler(CallbackQueryHandler(deposit, pattern="^deposit$"))
    app.add_handler(CallbackQueryHandler(withdraw, pattern="^withdraw$"))
    app.add_handler(CallbackQueryHandler(withdraw_card, pattern="^withdraw_card$"))
    app.add_handler(CallbackQueryHandler(withdraw_wallet, pattern="^withdraw_wallet$"))
    app.add_handler(CallbackQueryHandler(transactions, pattern="^transactions$"))

    app.add_handler(CallbackQueryHandler(gift, pattern="^gift$"))
    app.add_handler(CallbackQueryHandler(trust, pattern="^trust$"))
    app.add_handler(CallbackQueryHandler(support, pattern="^support$"))
    app.add_handler(CallbackQueryHandler(withdrawals_list, pattern="^withdrawals_list$"))
    app.add_handler(CallbackQueryHandler(refresh_withdrawals, pattern="^refresh_withdrawals$"))
    app.add_handler(CallbackQueryHandler(check_gift, pattern="^check_gift$"))
    app.add_handler(CallbackQueryHandler(copy_referral, pattern="^copy_referral$"))
    app.add_handler(CallbackQueryHandler(copy_trx, pattern="^copy_trx$"))
    app.add_handler(CallbackQueryHandler(copy_usdt, pattern="^copy_usdt$"))
    app.add_handler(CallbackQueryHandler(leaderboard, pattern="^leaderboard$"))
    app.add_handler(CallbackQueryHandler(refresh_leaderboard, pattern="^refresh_leaderboard$"))

    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_users, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(admin_settings, pattern="^admin_settings$"))
    app.add_handler(CallbackQueryHandler(admin_campaign, pattern="^admin_campaign$"))
    app.add_handler(CallbackQueryHandler(admin_back, pattern="^admin_back$"))
    app.add_handler(CallbackQueryHandler(admin_close, pattern="^admin_close$"))
    app.add_handler(CallbackQueryHandler(admin_toggle_bot, pattern="^admin_toggle_bot$"))
    app.add_handler(CallbackQueryHandler(admin_set_date, pattern="^admin_set_date$"))
    app.add_handler(CallbackQueryHandler(admin_set_wallets, pattern="^admin_set_wallets$"))
    app.add_handler(CallbackQueryHandler(admin_edit_trx, pattern="^admin_edit_trx$"))
    app.add_handler(CallbackQueryHandler(admin_edit_usdt, pattern="^admin_edit_usdt$"))
    app.add_handler(CallbackQueryHandler(admin_change_limits, pattern="^admin_change_limits$"))
    app.add_handler(CallbackQueryHandler(admin_edit_min_bet, pattern="^admin_edit_min_bet$"))
    app.add_handler(CallbackQueryHandler(admin_edit_min_deposit, pattern="^admin_edit_min_deposit$"))
    app.add_handler(CallbackQueryHandler(admin_edit_min_withdraw, pattern="^admin_edit_min_withdraw$"))
    app.add_handler(CallbackQueryHandler(admin_manage_games, pattern="^admin_manage_games$"))
    app.add_handler(CallbackQueryHandler(admin_toggle_game, pattern="^admin_toggle_game_"))
    app.add_handler(CallbackQueryHandler(admin_new_campaign, pattern="^admin_new_campaign$"))
    app.add_handler(CallbackQueryHandler(admin_campaign_stats, pattern="^admin_campaign_stats$"))
    app.add_handler(CallbackQueryHandler(admin_ban, pattern="^admin_ban$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast, pattern="^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(admin_global_gift, pattern="^admin_global_gift$"))
    app.add_handler(CallbackQueryHandler(admin_balance, pattern="^admin_balance$"))
    app.add_handler(CallbackQueryHandler(admin_search, pattern="^admin_search$"))
    app.add_handler(CallbackQueryHandler(admin_add_balance, pattern="^admin_add_"))
    app.add_handler(CallbackQueryHandler(admin_remove_balance, pattern="^admin_remove_"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bet_amount))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_amount))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_info))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_balance_action))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_deposit_amount))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    print("🤖 ربات شرطینو روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
