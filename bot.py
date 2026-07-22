#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ربات شرطینو - نسخه نهایی
"""

import os
import json
import random
import logging
import string
import gc
from datetime import datetime
from threading import Thread
from flask import Flask, jsonify

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# ======================== تنظیمات ========================
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

# ======================== وب‌سرور ========================
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return jsonify({"status": "running", "bot": "shartino"})

@flask_app.route("/health")
def health():
    return jsonify({"status": "ok"})

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ======================== دیتابیس ========================
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DATA_FILE = os.path.join(DATA_DIR, "users.json")
ADMIN_CONFIG_FILE = os.path.join(DATA_DIR, "admin_config.json")

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
    "games": {"dice": True, "coin": True, "slot": True, "football": True},
    "slot_coeffs": {
        "💎💎💎": 100, "⭐⭐⭐": 50, "７７７": 20,
        "🍇🍇🍇": 15, "🍋🍋🍋": 10, "🍒🍒🍒": 5, "two_same": 2
    }
})

# ======================== توابع کاربر ========================
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
            "created_at": str(datetime.now())
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

# ======================== منوی اصلی ========================
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
        [InlineKeyboardButton("❓ چطور اعتماد کنم", callback_data="trust")]
    ]
    
    text = f"🎰 **شرطینو**\n\n" \
           f"👤 کاربر: @{user['username'] or 'کاربر'}\n" \
           f"💰 موجودی: {user['balance']:,} تومان\n\n" \
           f"✅ با ریال می‌تونی برداشت کنی\n" \
           f"👥 با دعوت هر دوست {GIFT_AMOUNT:,} تومان هدیه\n\n" \
           f"🆘 پشتیبانی: {SUPPORT}\n\n" \
           f"از منوی زیر انتخاب کنید:"
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ======================== استارت ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    user = get_user(user_id)
    user["username"] = username
    save_user(user_id, user)
    
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
    
    if user.get("free_gift_used", False):
        keyboard = [
            [InlineKeyboardButton("🎲 شروع بازی", callback_data="game_menu")],
            [InlineKeyboardButton("👤 حساب من", callback_data="my_account")],
            [InlineKeyboardButton("🎁 دریافت شارژ هدیه", callback_data="gift")],
            [InlineKeyboardButton("❓ چطور اعتماد کنم", callback_data="trust")]
        ]
        await update.message.reply_text(
            f"🎰 **شرطینو**\n\n"
            f"👤 کاربر: @{username or 'کاربر'}\n"
            f"💰 موجودی: {user['balance']:,} تومان\n\n"
            f"✅ با ریال می‌تونی برداشت کنی\n"
            f"👥 با دعوت هر دوست {admin_config.get('gift_amount', GIFT_AMOUNT):,} تومان هدیه\n\n"
            f"🆘 پشتیبانی: {SUPPORT}\n\n"
            f"از منوی زیر انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
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
    text = f"🎁 **{gift_amount:,} تومان شارژ هدیه:**\n\n"
    text += f"فقط با عضویت در {channel_word2} اطلاع‌رسانی ما، شارژ هدیه دریافت کنید!\n\n"
    text += f"📌 **{channel_word} مورد نیاز:**\n\n{channels_text}\n\n"
    text += f"برای دریافت شارژ هدیه، ابتدا در {channel_word3} عضو شوید.\n\n"
    text += f"پس از عضویت، روی دکمه «✅ عضو شدم» کلیک کنید."
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

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
                            f"🎉 **یک عضو جدید با لینک شما عضو شد!**\n\n"
                            f"👤 کاربر جدید: @{user['username'] or user_id}\n"
                            f"🎁 شارژ هدیه: {gift_amount:,} تومان به حساب شما اضافه شد.\n\n"
                            f"📊 آمار دعوت‌های شما:\n"
                            f"👥 کل دعوت‌ها: {referrer.get('referral_count', 0)}\n"
                            f"💰 کل هدیه دریافتی: {referrer.get('referral_gift', 0):,} تومان",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
                    break
        
        await query.edit_message_text(
            f"✅ **تبریک! عضویت شما تأیید شد.**\n\n"
            f"🎁 {gift_amount:,} تومان شارژ هدیه به حساب شما اضافه شد.\n"
            f"💰 موجودی جدید: {user['balance']:,} تومان",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎲 شروع بازی", callback_data="game_menu")],
                [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
            ])
        )
    else:
        keyboard = []
        for i, channel in enumerate(enabled_channels, 1):
            link = channel["link"]
            label = f"📢 عضویت در کانال {i}" if len(enabled_channels) > 1 else "📢 عضویت در کانال"
            keyboard.append([InlineKeyboardButton(label, url=f"https://t.me/{link[1:]}")])
        keyboard.append([InlineKeyboardButton("✅ عضو شدم", callback_data="check_gift")])
        
        await query.edit_message_text(
            f"❌ شما هنوز در همه کانال‌ها عضو نشده‌اید!\n\n"
            f"لطفاً ابتدا در همه کانال‌های بالا عضو شوید، سپس دوباره روی «عضو شدم» کلیک کنید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ======================== بازی‌ها ========================
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
    
    await query.edit_message_text("🎮 **بازی‌های شرطینو**\n\nلطفاً یک بازی را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

# ======================== بازی تاس ========================
async def dice_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if user.get("banned", False):
        await query.edit_message_text("⛔ حساب شما مسدود شده است!")
        return
    
    keyboard = [
        [InlineKeyboardButton("۱۰,۰۰۰", callback_data="dice_bet_10000"),
         InlineKeyboardButton("۲۰,۰۰۰", callback_data="dice_bet_20000")],
        [InlineKeyboardButton("۵۰,۰۰۰", callback_data="dice_bet_50000"),
         InlineKeyboardButton("۱۰۰,۰۰۰", callback_data="dice_bet_100000")],
        [InlineKeyboardButton("۲۰۰,۰۰۰", callback_data="dice_bet_200000"),
         InlineKeyboardButton("۵۰۰,۰۰۰", callback_data="dice_bet_500000")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        f"🎲 **بازی تاس**\n\n"
        f"💰 موجودی شما: {user['balance']:,} تومان\n"
        f"📌 مبلغ شرط را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def dice_bet_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    amount = int(query.data.split("_")[2])
    
    if amount > user["balance"]:
        await query.edit_message_text(
            f"❌ موجودی شما کافی نیست!\n"
            f"💰 موجودی شما: {user['balance']:,} تومان\n"
            f"🎯 مبلغ شرط: {amount:,} تومان",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 انتخاب مبلغ", callback_data="dice_game")],
                [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
            ])
        )
        return
    
    context.user_data["dice_amount"] = amount
    
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
    await query.edit_message_text(
        f"🎲 **انتخاب پیش‌بینی**\n\n"
        f"💰 مبلغ شرط: {amount:,} تومان\n\n"
        f"لطفاً پیش‌بینی خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup([keyboard[i:i+2] for i in range(0, len(keyboard), 2)])
    )

async def dice_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    bet_amount = context.user_data.get("dice_amount", 0)
    choice = query.data.split("_")[1]
    
    await query.edit_message_text("🎲 **در حال انداختن تاس...**")
    dice_message = await query.message.reply_dice(emoji="🎲")
    dice_value = dice_message.dice.value
    
    is_win = False
    coefficient = 0
    
    if choice == "even":
        coefficient = 3
        is_win = dice_value in [2, 4, 6]
        choice_name = "زوج"
    elif choice == "odd":
        coefficient = 3
        is_win = dice_value in [1, 3, 5]
        choice_name = "فرد"
    else:
        coefficient = 10
        is_win = int(choice) == dice_value
        choice_name = f"عدد {choice}"
    
    if is_win:
        win_amount = bet_amount * coefficient
        user["balance"] += win_amount
        user["total_wins"] += 1
        result_text = f"🎉 **تبریک! شما برنده شدید!**\n\n"
        result_text += f"🎲 نتیجه تاس: {dice_value}\n"
        result_text += f"🎯 پیش‌بینی: {choice_name}\n"
        result_text += f"💰 مبلغ شرط: {bet_amount:,} تومان\n"
        result_text += f"📊 ضریب: {coefficient}\n"
        result_text += f"🏆 جایزه: {win_amount:,} تومان\n\n"
        result_text += f"💰 موجودی جدید: {user['balance']:,} تومان"
        add_transaction(user_id, win_amount, "win", f"برد در تاس - {choice_name}")
    else:
        user["balance"] -= bet_amount
        user["total_losses"] += 1
        result_text = f"😔 **متاسفم... شما باختید.**\n\n"
        result_text += f"🎲 نتیجه تاس: {dice_value}\n"
        result_text += f"🎯 پیش‌بینی: {choice_name}\n"
        result_text += f"💰 مبلغ شرط: {bet_amount:,} تومان\n\n"
        result_text += f"💰 موجودی جدید: {user['balance']:,} تومان"
        add_transaction(user_id, -bet_amount, "bet", f"باخت در تاس - {choice_name}")
    
    user["total_bets"] += 1
    save_user(user_id, user)
    
    keyboard = [
        [InlineKeyboardButton("🎲 دوباره", callback_data="dice_game")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    await query.message.reply_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard))

# ======================== شیر یا خط ========================
async def coin_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if user.get("banned", False):
        await query.edit_message_text("⛔ حساب شما مسدود شده است!")
        return
    
    keyboard = [
        [InlineKeyboardButton("۱۰,۰۰۰", callback_data="coin_bet_10000"),
         InlineKeyboardButton("۲۰,۰۰۰", callback_data="coin_bet_20000")],
        [InlineKeyboardButton("۵۰,۰۰۰", callback_data="coin_bet_50000"),
         InlineKeyboardButton("۱۰۰,۰۰۰", callback_data="coin_bet_100000")],
        [InlineKeyboardButton("۲۰۰,۰۰۰", callback_data="coin_bet_200000"),
         InlineKeyboardButton("۵۰۰,۰۰۰", callback_data="coin_bet_500000")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        f"🪙 **شیر یا خط**\n\n"
        f"💰 موجودی شما: {user['balance']:,} تومان\n"
        f"📌 مبلغ شرط را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def coin_bet_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    amount = int(query.data.split("_")[2])
    
    if amount > user["balance"]:
        await query.edit_message_text(
            f"❌ موجودی شما کافی نیست!\n"
            f"💰 موجودی شما: {user['balance']:,} تومان\n"
            f"🎯 مبلغ شرط: {amount:,} تومان",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 انتخاب مبلغ", callback_data="coin_game")],
                [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
            ])
        )
        return
    
    context.user_data["coin_amount"] = amount
    
    keyboard = [
        [InlineKeyboardButton("🦁 شیر", callback_data="coin_heads")],
        [InlineKeyboardButton("📍 خط", callback_data="coin_tails")],
        [InlineKeyboardButton("🔙 انصراف", callback_data="main_menu")]
    ]
    await query.edit_message_text(
        f"🪙 **انتخاب شیر یا خط**\n\n"
        f"💰 مبلغ شرط: {amount:,} تومان\n\n"
        f"📌 عدد زوج = شیر 🦁 | عدد فرد = خط 📍\n\n"
        f"لطفاً انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def coin_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    bet_amount = context.user_data.get("coin_amount", 0)
    choice = query.data.split("_")[1]
    
    await query.edit_message_text("🪙 **در حال پرتاب سکه...**")
    dice_message = await query.message.reply_dice(emoji="🎲")
    dice_value = dice_message.dice.value
    
    is_heads = dice_value in [2, 4, 6]
    result_name = "شیر 🦁" if is_heads else "خط 📍"
    is_win = (choice == "heads" and is_heads) or (choice == "tails" and not is_heads)
    
    if is_win:
        win_amount = bet_amount * 2
        user["balance"] += win_amount
        user["total_wins"] += 1
        result_text = f"🎉 **تبریک! شما برنده شدید!**\n\n"
        result_text += f"🪙 نتیجه سکه: {result_name}\n"
        result_text += f"🎲 عدد تاس: {dice_value} ({'زوج' if is_heads else 'فرد'})\n"
        result_text += f"💰 مبلغ شرط: {bet_amount:,} تومان\n"
        result_text += f"📊 ضریب: ۲\n"
        result_text += f"🏆 جایزه: {win_amount:,} تومان\n\n"
        result_text += f"💰 موجودی جدید: {user['balance']:,} تومان"
        add_transaction(user_id, win_amount, "win", "برد در شیر یا خط")
    else:
        user["balance"] -= bet_amount
        user["total_losses"] += 1
        result_text = f"😔 **متاسفم... شما باختید.**\n\n"
        result_text += f"🪙 نتیجه سکه: {result_name}\n"
        result_text += f"🎲 عدد تاس: {dice_value} ({'زوج' if is_heads else 'فرد'})\n"
        result_text += f"💰 مبلغ شرط: {bet_amount:,} تومان\n\n"
        result_text += f"💰 موجودی جدید: {user['balance']:,} تومان"
        add_transaction(user_id, -bet_amount, "bet", "باخت در شیر یا خط")
    
    user["total_bets"] += 1
    save_user(user_id, user)
    
    keyboard = [
        [InlineKeyboardButton("🪙 دوباره", callback_data="coin_game")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    await query.message.reply_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard))

# ======================== اسلات ========================
async def slot_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if user.get("banned", False):
        await query.edit_message_text("⛔ حساب شما مسدود شده است!")
        return
    
    keyboard = [
        [InlineKeyboardButton("۱۰,۰۰۰", callback_data="slot_bet_10000"),
         InlineKeyboardButton("۲۰,۰۰۰", callback_data="slot_bet_20000")],
        [InlineKeyboardButton("۵۰,۰۰۰", callback_data="slot_bet_50000"),
         InlineKeyboardButton("۱۰۰,۰۰۰", callback_data="slot_bet_100000")],
        [InlineKeyboardButton("۲۰۰,۰۰۰", callback_data="slot_bet_200000"),
         InlineKeyboardButton("۵۰۰,۰۰۰", callback_data="slot_bet_500000")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    
    slot_coeffs = admin_config.get("slot_coeffs", {})
    await query.edit_message_text(
        f"🎰 **بازی اسلات**\n\n"
        f"💰 موجودی شما: {user['balance']:,} تومان\n"
        f"📊 **ضرایب:**\n"
        f"💎💎💎 = {slot_coeffs.get('💎💎💎', 100)}× | ⭐⭐⭐ = {slot_coeffs.get('⭐⭐⭐', 50)}×\n"
        f"۷۷۷ = {slot_coeffs.get('۷۷۷', 20)}× | 🍇🍇🍇 = {slot_coeffs.get('🍇🍇🍇', 15)}×\n"
        f"🍋🍋🍋 = {slot_coeffs.get('🍋🍋🍋', 10)}× | 🍒🍒🍒 = {slot_coeffs.get('🍒🍒🍒', 5)}×\n"
        f"۲ تا یکسان = {slot_coeffs.get('two_same', 2)}×\n\n"
        f"📌 مبلغ شرط را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def slot_bet_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    amount = int(query.data.split("_")[2])
    
    if amount > user["balance"]:
        await query.edit_message_text(
            f"❌ موجودی شما کافی نیست!\n"
            f"💰 موجودی شما: {user['balance']:,} تومان\n"
            f"🎯 مبلغ شرط: {amount:,} تومان",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 انتخاب مبلغ", callback_data="slot_game")],
                [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
            ])
        )
        return
    
    context.user_data["slot_amount"] = amount
    
    await query.edit_message_text(
        f"🎰 **اسلات**\n\n"
        f"💰 مبلغ شرط: {amount:,} تومان\n\n"
        f"دکمه زیر را بزنید تا دستگاه اسلات بچرخد:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎰 چرخش اسلات", callback_data="slot_spin")],
            [InlineKeyboardButton("🔙 انصراف", callback_data="main_menu")]
        ])
    )

async def slot_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    bet_amount = context.user_data.get("slot_amount", 0)
    
    await query.edit_message_text("🎰 **در حال چرخش اسلات...**")
    dice_message = await query.message.reply_dice(emoji="🎰")
    dice_value = dice_message.dice.value
    
    slot_emojis = ["🍇", "🍋", "７", "BAR"]
    result = [
        slot_emojis[(dice_value - 1) // 16 % 4],
        slot_emojis[(dice_value - 1) // 4 % 4],
        slot_emojis[(dice_value - 1) % 4]
    ]
    combo = "".join(result)
    
    slot_coeffs = admin_config.get("slot_coeffs", {})
    coefficient = slot_coeffs.get(combo, 0)
    if coefficient == 0 and (result[0] == result[1] or result[1] == result[2] or result[0] == result[2]):
        coefficient = slot_coeffs.get("two_same", 2)
    
    if coefficient > 0:
        win_amount = bet_amount * coefficient
        user["balance"] += win_amount
        user["total_wins"] += 1
        result_text = f"🎉 **تبریک! شما برنده شدید!**\n\n"
        result_text += f"🎰 نتیجه اسلات:\n[ {result[0]} ] [ {result[1]} ] [ {result[2]} ]\n\n"
        result_text += f"📊 ترکیب: {combo}\n"
        result_text += f"🎯 ضریب: {coefficient}×\n"
        result_text += f"💰 مبلغ شرط: {bet_amount:,} تومان\n"
        result_text += f"🏆 جایزه: {win_amount:,} تومان\n\n"
        result_text += f"💰 موجودی جدید: {user['balance']:,} تومان"
        add_transaction(user_id, win_amount, "win", f"برد در اسلات - {combo}")
    else:
        user["balance"] -= bet_amount
        user["total_losses"] += 1
        result_text = f"😔 **متاسفم... شما باختید.**\n\n"
        result_text += f"🎰 نتیجه اسلات:\n[ {result[0]} ] [ {result[1]} ] [ {result[2]} ]\n\n"
        result_text += f"📊 ترکیب: {combo}\n"
        result_text += f"🎯 ضریب: ۰\n"
        result_text += f"💰 مبلغ شرط: {bet_amount:,} تومان\n\n"
        result_text += f"💰 موجودی جدید: {user['balance']:,} تومان"
        add_transaction(user_id, -bet_amount, "bet", "باخت در اسلات")
    
    user["total_bets"] += 1
    save_user(user_id, user)
    
    keyboard = [
        [InlineKeyboardButton("🎰 دوباره", callback_data="slot_game")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    await query.message.reply_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard))

# ======================== فوتبال ========================
async def football_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if user.get("banned", False):
        await query.edit_message_text("⛔ حساب شما مسدود شده است!")
        return
    
    keyboard = [
        [InlineKeyboardButton("۱۰,۰۰۰", callback_data="football_bet_10000"),
         InlineKeyboardButton("۲۰,۰۰۰", callback_data="football_bet_20000")],
        [InlineKeyboardButton("۵۰,۰۰۰", callback_data="football_bet_50000"),
         InlineKeyboardButton("۱۰۰,۰۰۰", callback_data="football_bet_100000")],
        [InlineKeyboardButton("۲۰۰,۰۰۰", callback_data="football_bet_200000"),
         InlineKeyboardButton("۵۰۰,۰۰۰", callback_data="football_bet_500000")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        f"⚽ **بازی فوتبال**\n\n"
        f"💰 موجودی شما: {user['balance']:,} تومان\n"
        f"📌 مبلغ شرط را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def football_bet_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    amount = int(query.data.split("_")[2])
    
    if amount > user["balance"]:
        await query.edit_message_text(
            f"❌ موجودی شما کافی نیست!\n"
            f"💰 موجودی شما: {user['balance']:,} تومان\n"
            f"🎯 مبلغ شرط: {amount:,} تومان",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 انتخاب مبلغ", callback_data="football_game")],
                [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
            ])
        )
        return
    
    context.user_data["football_amount"] = amount
    
    keyboard = [
        [InlineKeyboardButton("⚽️ گل می‌شود (ضریب ۲)", callback_data="football_goal")],
        [InlineKeyboardButton("❌ گل نمی‌شود (ضریب ۲)", callback_data="football_miss")],
        [InlineKeyboardButton("🔙 انصراف", callback_data="main_menu")]
    ]
    await query.edit_message_text(
        f"⚽ **پیش‌بینی فوتبال**\n\n"
        f"💰 مبلغ شرط: {amount:,} تومان\n\n"
        f"توپ به سمت دروازه شوت می‌شود!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def football_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    bet_amount = context.user_data.get("football_amount", 0)
    prediction = query.data.split("_")[1]
    
    await query.edit_message_text("⚽ **در حال شوت...**")
    dice_message = await query.message.reply_dice(emoji="⚽")
    dice_value = dice_message.dice.value
    
    is_goal = dice_value >= 4
    result_text = "گل شد ✅" if is_goal else "گل نشد ❌"
    is_win = (prediction == "goal" and is_goal) or (prediction == "miss" and not is_goal)
    
    if is_win:
        win_amount = bet_amount * 2
        user["balance"] += win_amount
        user["total_wins"] += 1
        result_msg = f"🎉 **تبریک! شما برنده شدید!**\n\n"
        result_msg += f"⚽ نتیجه شوت: {result_text}\n"
        result_msg += f"🎯 پیش‌بینی شما: {'گل می‌شود' if prediction == 'goal' else 'گل نمی‌شود'} (درست)\n"
        result_msg += f"💰 مبلغ شرط: {bet_amount:,} تومان\n"
        result_msg += f"📊 ضریب: ۲\n"
        result_msg += f"🏆 جایزه: {win_amount:,} تومان\n\n"
        result_msg += f"💰 موجودی جدید: {user['balance']:,} تومان"
        add_transaction(user_id, win_amount, "win", "برد در فوتبال")
    else:
        user["balance"] -= bet_amount
        user["total_losses"] += 1
        result_msg = f"😔 **متاسفم... شما باختید.**\n\n"
        result_msg += f"⚽ نتیجه شوت: {result_text}\n"
        result_msg += f"🎯 پیش‌بینی شما: {'گل می‌شود' if prediction == 'goal' else 'گل نمی‌شود'}\n"
        result_msg += f"💰 مبلغ شرط: {bet_amount:,} تومان\n\n"
        result_msg += f"💰 موجودی جدید: {user['balance']:,} تومان"
        add_transaction(user_id, -bet_amount, "bet", "باخت در فوتبال")
    
    user["total_bets"] += 1
    save_user(user_id, user)
    
    keyboard = [
        [InlineKeyboardButton("⚽ دوباره", callback_data="football_game")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    await query.message.reply_text(result_msg, reply_markup=InlineKeyboardMarkup(keyboard))

# ======================== حساب من ========================
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
    
    text = f"👤 **حساب من**\n\n"
    text += f"🆔 کاربر شماره: {user_id}\n"
    text += f"👥 دعوت‌های موفق: {user.get('referral_count', 0)}\n"
    text += f"📊 تعداد پیش‌بینی‌ها: {total_bets} | برد: {wins} | باخت: {losses}\n"
    text += f"📈 نرخ برد: {win_rate}%\n"
    text += f"💰 موجودی: {user['balance']:,} تومان"
    
    keyboard = [
        [InlineKeyboardButton("💳 واریز وجه", callback_data="deposit")],
        [InlineKeyboardButton("🏦 برداشت موجودی", callback_data="withdraw")],
        [InlineKeyboardButton("📜 تاریخچه تراکنش‌ها", callback_data="transactions")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ======================== واریز ========================
async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("۵۰۰,۰۰۰", callback_data="deposit_500000"),
         InlineKeyboardButton("۱,۰۰۰,۰۰۰", callback_data="deposit_1000000")],
        [InlineKeyboardButton("۲,۰۰۰,۰۰۰", callback_data="deposit_2000000"),
         InlineKeyboardButton("۵,۰۰۰,۰۰۰", callback_data="deposit_5000000")],
        [InlineKeyboardButton("۱۰,۰۰۰,۰۰۰", callback_data="deposit_10000000")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        f"💳 **واریز وجه**\n\n"
        f"💰 حداقل مبلغ واریز: {admin_config.get('min_deposit', 500000):,} تومان\n\n"
        f"📌 مبلغ مورد نظر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def deposit_amount_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    amount = int(query.data.split("_")[1])
    context.user_data["deposit_amount"] = amount
    
    trx_wallet = admin_config.get("trx_wallet", TRX_WALLET)
    usdt_wallet = admin_config.get("usdt_wallet", USDT_WALLET)
    deposit_date = admin_config.get("deposit_enable_date", "۳۰ مرداد‌ماه")
    
    text = f"""💳 **تأیید مبلغ واریز**

💰 مبلغ واریز: {amount:,} تومان
🎁 هدیه واریز اول: ۵۰٪ بیشتر (در صورت اولین واریز)

━━━━━━━━━━━━━━━━━━━━━━
📌 شماره کارت جهت واریز ریالی:
`60376976********`

⚠️ واریز ریالی تا تاریخ {deposit_date} فعال نیست.

━━━━━━━━━━━━━━━━━━━━━━
🟣 آدرس ولت ترون (TRX):
`{trx_wallet}`

📋 روی آدرس بالا کلیک کنید تا کپی شود

━━━━━━━━━━━━━━━━━━━━━━
🟢 آدرس ولت تتر (USDT-TRC20):
`{usdt_wallet}`

📋 روی آدرس بالا کلیک کنید تا کپی شود

━━━━━━━━━━━━━━━━━━━━━━
📌 پس از واریز، حتماً اسکرین‌شات خود را به پشتیبانی ارسال کنید.

🆘 {SUPPORT}"""
    
    keyboard = [
        [InlineKeyboardButton("📋 کپی آدرس ولت ترون", callback_data="copy_trx")],
        [InlineKeyboardButton("📋 کپی آدرس ولت تتر", callback_data="copy_usdt")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def copy_trx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.answer(f"✅ آدرس ولت ترون کپی شد:\n{admin_config.get('trx_wallet', TRX_WALLET)}", show_alert=True)

async def copy_usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.answer(f"✅ آدرس ولت تتر کپی شد:\n{admin_config.get('usdt_wallet', USDT_WALLET)}", show_alert=True)

# ======================== برداشت ========================
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
            f"❌ **برداشت غیرمجاز!**\n\n"
            f"شما تاکنون هیچ واریزی به ربات نداشته‌اید.\n\n"
            f"📌 برداشت تنها پس از **اولین واریز** امکان‌پذیر است.\n\n"
            f"برای واریز، از بخش «💳 واریز وجه» اقدام کنید.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 واریز وجه", callback_data="deposit")],
                [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
            ])
        )
        return
    
    balance = user["balance"]
    min_withdraw = admin_config.get("min_withdraw", MIN_WITHDRAW)
    
    keyboard = []
    amounts = [500000, 1000000, 2000000, 5000000, 10000000]
    row = []
    for amount in amounts:
        if amount >= min_withdraw and amount <= balance:
            row.append(InlineKeyboardButton(f"{amount:,}", callback_data=f"withdraw_{amount}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
    if row:
        keyboard.append(row)
    
    if not keyboard:
        keyboard.append([InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")])
        await query.edit_message_text(
            f"🏦 **برداشت موجودی**\n\n"
            f"💰 موجودی قابل برداشت: {balance:,} تومان\n"
            f"📌 حداقل مبلغ برداشت: {min_withdraw:,} تومان\n\n"
            f"❌ موجودی شما برای برداشت کافی نیست!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    keyboard.append([InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")])
    
    await query.edit_message_text(
        f"🏦 **برداشت موجودی**\n\n"
        f"💰 موجودی قابل برداشت: {balance:,} تومان\n"
        f"📌 حداقل مبلغ برداشت: {min_withdraw:,} تومان\n\n"
        f"📌 مبلغ مورد نظر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def withdraw_amount_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    amount = int(query.data.split("_")[1])
    context.user_data["withdraw_amount"] = amount
    
    keyboard = [
        [InlineKeyboardButton("💳 شماره کارت", callback_data="withdraw_card")],
        [InlineKeyboardButton("🟣 آدرس ولت (TRX)", callback_data="withdraw_wallet")],
        [InlineKeyboardButton("🔙 انصراف", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        f"✅ مبلغ {amount:,} تومان برای برداشت ثبت شد.\n\n"
        f"لطفاً یکی از روش‌های زیر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def withdraw_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["withdraw_method"] = "card"
    await query.edit_message_text(
        "💳 **برداشت با شماره کارت**\n\n"
        f"لطفاً شماره کارت ۱۶ رقمی خود را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 انصراف", callback_data="main_menu")]])
    )

async def withdraw_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["withdraw_method"] = "wallet"
    await query.edit_message_text(
        "🟣 **برداشت با آدرس ولت (TRX)**\n\n"
        f"لطفاً آدرس ولت ترون خود را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 انصراف", callback_data="main_menu")]])
    )

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
            await context.bot.send_message(
                admin_id,
                f"🏦 **درخواست برداشت جدید**\n\n"
                f"👤 کاربر: @{user['username'] or user_id}\n"
                f"💰 مبلغ: {amount:,} تومان\n"
                f"📌 روش: {method_name}\n"
                f"📋 اطلاعات: {info}"
            )
        except:
            pass
    
    await update.message.reply_text(
        f"✅ **درخواست برداشت شما ثبت شد!**\n\n"
        f"💰 مبلغ: {amount:,} تومان\n"
        f"🕒 درخواست شما در صف پردازش قرار گرفت.\n"
        f"در صورت نیاز به پشتیبانی: {SUPPORT}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]])
    )

# ======================== تاریخچه تراکنش‌ها ========================
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
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 حساب من", callback_data="my_account")]]))

# ======================== سایر بخش‌ها ========================
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
    
    text = f"🎁 **دریافت شارژ هدیه و کمیسیون**\n\n"
    text += f"📌 **درصد کمیسیون شما:** {commission_percent}%\n\n"
    text += f"👤 هر دعوت موفق = {admin_config.get('gift_amount', GIFT_AMOUNT):,} تومان شارژ هدیه\n"
    text += f"💰 از هر واریز زیرمجموعه = {commission_percent}% کمیسیون\n\n"
    text += f"🔗 لینک دعوت اختصاصی:\n`{link}`\n\n"
    text += f"📋 روی لینک بالا کلیک کنید تا کپی شود\n\n"
    text += f"📊 **آمار شما:**\n"
    text += f"👥 دعوت‌های موفق: {user.get('referral_count', 0)}\n"
    text += f"💰 شارژ هدیه: {user.get('referral_gift', 0):,} تومان\n"
    text += f"💸 کمیسیون دریافتی: {user.get('referral_commission', 0):,} تومان"
    
    keyboard = [
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def trust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"❓ **چطور اعتماد کنم**\n\n"
        f"ما درک می‌کنیم که اعتماد کردن به یک سرویس آنلاین ممکن است برای شما چالش‌برانگیز باشد.\n\n"
        f"به منظور اینکه شما با خیال آسوده شروع به فعالیت کنید، **{admin_config.get('gift_amount', GIFT_AMOUNT):,} تومان موجودی رایگان** هنگام عضویت به شما اهدا کردیم.\n\n"
        f"ما متعهد به ارائه تجربه‌ای لذت‌بخش و عادلانه برای تمام کاربران هستیم. ❤️",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]])
    )

# ======================== پنل ادمین (خلاصه) ========================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ این دستور فقط برای ادمین است.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 آمار کل", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin_users")],
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="admin_settings")],
        [InlineKeyboardButton("🔙 بستن", callback_data="admin_close")]
    ]
    await update.message.reply_text("👑 **پنل مدیریت ربات شرطینو**", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    total = len(users)
    total_balance = sum(u["balance"] for u in users.values())
    banned = sum(1 for u in users.values() if u.get("banned", False))
    text = f"📊 **آمار کل ربات**\n\n"
    text += f"👥 کل کاربران: {total}\n"
    text += f"🚫 کاربران مسدود: {banned}\n"
    text += f"💰 کل موجودی: {total_balance:,} تومان"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]))

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
    await query.edit_message_text("👥 **مدیریت کاربران**", reply_markup=InlineKeyboardMarkup(keyboard))

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
    await query.edit_message_text("⚙️ **تنظیمات ربات**", reply_markup=InlineKeyboardMarkup(keyboard))

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
        f"🔌 **وضعیت ربات تغییر کرد!**\n\n"
        f"📌 وضعیت جدید: {status_text}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 تغییر وضعیت", callback_data="admin_toggle_bot")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]
        ])
    )

async def admin_set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"📅 **تغییر تاریخ فعال‌سازی واریز ریالی**\n\n"
        f"📌 تاریخ فعلی: {admin_config.get('deposit_enable_date', '۳۰ مرداد‌ماه')}\n\n"
        f"تاریخ جدید را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]])
    )

async def admin_set_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"🔄 **تغییر آدرس ولت‌ها**\n\n"
        f"🟣 ولت ترون فعلی:\n`{admin_config.get('trx_wallet', TRX_WALLET)}`\n\n"
        f"🟢 ولت تتر فعلی:\n`{admin_config.get('usdt_wallet', USDT_WALLET)}`\n\n"
        f"برای تغییر، یکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ تغییر ولت ترون", callback_data="admin_edit_trx")],
            [InlineKeyboardButton("✏️ 변경 ولت تتر", callback_data="admin_edit_usdt")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]
        ])
    )

async def admin_edit_trx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"✏️ **تغییر آدرس ولت ترون (TRX)**\n\n"
        f"📌 آدرس فعلی:\n`{admin_config.get('trx_wallet', TRX_WALLET)}`\n\n"
        f"آدرس جدید را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]])
    )

async def admin_edit_usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"✏️ **تغییر آدرس ولت تتر (USDT-TRC20)**\n\n"
        f"📌 آدرس فعلی:\n`{admin_config.get('usdt_wallet', USDT_WALLET)}`\n\n"
        f"آدرس جدید را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]])
    )

async def admin_change_limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"🎯 **تغییر حداقل مبالغ**\n\n"
        f"💰 حداقل شرط: {admin_config.get('min_bet', MIN_BET):,} تومان\n"
        f"💰 حداقل واریز: {admin_config.get('min_deposit', 500000):,} تومان\n"
        f"💰 حداقل برداشت: {admin_config.get('min_withdraw', MIN_WITHDRAW):,} تومان\n\n"
        f"کدام مبلغ را تغییر می‌دهید؟",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ حداقل شرط", callback_data="admin_edit_min_bet")],
            [InlineKeyboardButton("✏️ حداقل واریز", callback_data="admin_edit_min_deposit")],
            [InlineKeyboardButton("✏️ حداقل برداشت", callback_data="admin_edit_min_withdraw")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]
        ])
    )

async def admin_edit_min_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"✏️ **تغییر حداقل شرط**\n\n"
        f"📌 حداقل شرط فعلی: {admin_config.get('min_bet', MIN_BET):,} تومان\n\n"
        f"مبلغ جدید را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]])
    )

async def admin_edit_min_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"✏️ **تغییر حداقل واریز**\n\n"
        f"📌 حداقل واریز فعلی: {admin_config.get('min_deposit', 500000):,} تومان\n\n"
        f"مبلغ جدید را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]])
    )

async def admin_edit_min_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"✏️ **تغییر حداقل برداشت**\n\n"
        f"📌 حداقل برداشت فعلی: {admin_config.get('min_withdraw', MIN_WITHDRAW):,} تومان\n\n"
        f"مبلغ جدید را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]])
    )

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
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_toggle_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game = query.data.split("_")[3]
    games = admin_config.get("games", {})
    games[game] = not games.get(game, True)
    admin_config["games"] = games
    save_json(ADMIN_CONFIG_FILE, admin_config)
    
    await query.edit_message_text(
        f"✅ وضعیت بازی {game} با موفقیت تغییر کرد.\n"
        f"📌 وضعیت جدید: {'فعال' if games[game] else 'غیرفعال'}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 مدیریت بازی‌ها", callback_data="admin_manage_games")]])
    )

async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🚫 **مسدود کردن کاربر**\n\n"
        f"🆔 آیدی عددی کاربر را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]])
    )

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📨 **ارسال پیام همگانی**\n\n"
        f"متن پیام را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]])
    )

async def admin_global_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🎁 **شارژ همگانی**\n\n"
        f"💰 مبلغ جایزه را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]])
    )

async def admin_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "💸 **مدیریت موجودی کاربر**\n\n"
        f"🆔 آیدی عددی کاربر را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]])
    )

async def admin_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔍 **جستجوی کاربر**\n\n"
        f"🆔 آیدی عددی کاربر را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]])
    )

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    
    text = update.message.text.strip()
    action = context.user_data.get("admin_action")
    
    if action == "ban":
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
        await update.message.reply_text(
            f"✅ **پیام همگانی ارسال شد!**\n\n"
            f"👥 ارسال موفق: {success} نفر\n"
            f"❌ ناموفق: {fail} نفر"
        )
    
    elif action == "gift":
        try:
            amount = int(text)
            if amount < 0:
                await update.message.reply_text("❌ مبلغ نمی‌تواند منفی باشد.")
                return
            success = 0
            fail = 0
            for uid, data in users.items():
                if data.get("banned", False):
                    continue
                user = get_user(uid)
                user["balance"] += amount
                add_transaction(uid, amount, "gift", "جایزه همگانی")
                save_user(uid, user)
                try:
                    await context.bot.send_message(
                        uid,
                        f"🎁 **جایزه ویژه شرطینو**\n\n"
                        f"مبلغ {amount:,} تومان به حساب شما اضافه شد.\n\n"
                        f"💰 موجودی جدید: {user['balance']:,} تومان",
                        parse_mode="Markdown"
                    )
                    success += 1
                except:
                    fail += 1
            await update.message.reply_text(
                f"✅ **شارژ همگانی با موفقیت انجام شد!**\n\n"
                f"💰 مبلغ شارژ: {amount:,} تومان\n"
                f"👥 ارسال موفق: {success} نفر\n"
                f"❌ ناموفق: {fail} نفر"
            )
        except:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید.")
    
    elif action == "balance":
        try:
            target = int(text)
            user = get_user(target)
            await update.message.reply_text(
                f"👤 **اطلاعات کاربر**\n\n"
                f"🆔 آیدی: {target}\n"
                f"👤 یوزرنیم: @{user['username'] or 'کاربر'}\n"
                f"💰 موجودی: {user['balance']:,} تومان\n"
                f"📊 وضعیت: {'🚫 مسدود' if user.get('banned', False) else '✅ فعال'}\n"
                f"💳 واریز کرده: {'✅ بله' if user.get('has_deposited', False) else '❌ خیر'}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ افزایش موجودی", callback_data=f"admin_add_{target}")],
                    [InlineKeyboardButton("➖ کاهش موجودی", callback_data=f"admin_remove_{target}")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]
                ])
            )
        except:
            await update.message.reply_text("❌ آیدی نامعتبر است.")
    
    elif action == "search":
        try:
            target = int(text)
            user = get_user(target)
            await update.message.reply_text(
                f"👤 **اطلاعات کاربر**\n\n"
                f"🆔 آیدی: {target}\n"
                f"👤 یوزرنیم: @{user['username'] or 'کاربر'}\n"
                f"💰 موجودی: {user['balance']:,} تومان\n"
                f"📊 وضعیت: {'🚫 مسدود' if user.get('banned', False) else '✅ فعال'}\n"
                f"💳 واریز کرده: {'✅ بله' if user.get('has_deposited', False) else '❌ خیر'}\n"
                f"📅 تاریخ عضویت: {user.get('created_at', 'نامشخص')}"
            )
        except:
            await update.message.reply_text("❌ آیدی نامعتبر است.")
    
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
    
    elif action == "edit_trx":
        admin_config["trx_wallet"] = text
        save_json(ADMIN_CONFIG_FILE, admin_config)
        await update.message.reply_text(f"✅ آدرس ولت ترون با موفقیت تغییر کرد.\n🟣 آدرس جدید: `{text}`")
    
    elif action == "edit_usdt":
        admin_config["usdt_wallet"] = text
        save_json(ADMIN_CONFIG_FILE, admin_config)
        await update.message.reply_text(f"✅ آدرس ولت تتر با موفقیت تغییر کرد.\n🟢 آدرس جدید: `{text}`")
    
    elif action == "set_date":
        admin_config["deposit_enable_date"] = text
        save_json(ADMIN_CONFIG_FILE, admin_config)
        await update.message.reply_text(f"✅ تاریخ با موفقیت تغییر کرد.\n📅 تاریخ جدید: {text}")
    
    context.user_data["admin_action"] = None

async def admin_add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target = int(query.data.split("_")[2])
    context.user_data["admin_add_user"] = target
    context.user_data["admin_action"] = "admin_add"
    
    await query.edit_message_text(
        f"➕ **افزایش موجودی کاربر**\n\n"
        f"👤 کاربر: @{get_user(target)['username'] or target}\n"
        f"💰 موجودی فعلی: {get_user(target)['balance']:,} تومان\n\n"
        f"مبلغ مورد نظر را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 انصراف", callback_data="admin_back")]])
    )

async def admin_remove_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target = int(query.data.split("_")[2])
    context.user_data["admin_remove_user"] = target
    context.user_data["admin_action"] = "admin_remove"
    
    await query.edit_message_text(
        f"➖ **کاهش موجودی کاربر**\n\n"
        f"👤 کاربر: @{get_user(target)['username'] or target}\n"
        f"💰 موجودی فعلی: {get_user(target)['balance']:,} تومان\n\n"
        f"مبلغ مورد نظر را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 انصراف", callback_data="admin_back")]])
    )

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
    
    if action == "admin_add":
        target = context.user_data.get("admin_add_user")
        user = get_user(target)
        user["balance"] += amount
        add_transaction(target, amount, "deposit", "واریز توسط ادمین")
        user["has_deposited"] = True
        save_user(target, user)
        await update.message.reply_text(
            f"✅ موجودی کاربر @{user['username'] or target} افزایش یافت.\n"
            f"💰 مبلغ: {amount:,} تومان\n"
            f"💰 موجودی جدید: {user['balance']:,} تومان"
        )
        try:
            await context.bot.send_message(
                target,
                f"✅ **موجودی شما افزایش یافت!**\n\n"
                f"💰 مبلغ: {amount:,} تومان\n"
                f"💰 موجودی جدید: {user['balance']:,} تومان"
            )
        except:
            pass
    
    elif action == "admin_remove":
        target = context.user_data.get("admin_remove_user")
        user = get_user(target)
        if user["balance"] < amount:
            await update.message.reply_text(f"❌ موجودی کاربر کافی نیست!\n💰 موجودی: {user['balance']:,} تومان")
            return
        user["balance"] -= amount
        add_transaction(target, -amount, "admin_remove", "کاهش موجودی توسط ادمین")
        save_user(target, user)
        await update.message.reply_text(
            f"✅ موجودی کاربر @{user['username'] or target} کاهش یافت.\n"
            f"💰 مبلغ: {amount:,} تومان\n"
            f"💰 موجودی جدید: {user['balance']:,} تومان"
        )
        try:
            await context.bot.send_message(
                target,
                f"⚠️ **موجودی شما کاهش یافت!**\n\n"
                f"💰 مبلغ: {amount:,} تومان\n"
                f"💰 موجودی جدید: {user['balance']:,} تومان"
            )
        except:
            pass
    
    context.user_data["admin_action"] = None
    context.user_data["admin_add_user"] = None
    context.user_data["admin_remove_user"] = None

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ دستور نامعتبر. لطفاً از منو استفاده کنید.")

# ======================== اصلی ========================
def main():
    logging.basicConfig(level=logging.INFO)
    
    gc.enable()
    gc.set_threshold(700, 10, 5)
    
    # اجرای وب‌سرور
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print("✅ وب‌سرور Flask روشن شد")
    
    app = Application.builder().token(TOKEN).build()
    
    # ======================== دستورات ========================
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    
    # ======================== کالبک‌های اصلی ========================
    app.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(game_menu, pattern="^game_menu$"))
    app.add_handler(CallbackQueryHandler(check_gift, pattern="^check_gift$"))
    
    # ======================== بازی تاس ========================
    app.add_handler(CallbackQueryHandler(dice_game, pattern="^dice_game$"))
    app.add_handler(CallbackQueryHandler(dice_bet_selected, pattern="^dice_bet_"))
    app.add_handler(CallbackQueryHandler(dice_result, pattern="^dice_"))
    
    # ======================== شیر یا خط ========================
    app.add_handler(CallbackQueryHandler(coin_game, pattern="^coin_game$"))
    app.add_handler(CallbackQueryHandler(coin_bet_selected, pattern="^coin_bet_"))
    app.add_handler(CallbackQueryHandler(coin_result, pattern="^coin_"))
    
    # ======================== اسلات ========================
    app.add_handler(CallbackQueryHandler(slot_game, pattern="^slot_game$"))
    app.add_handler(CallbackQueryHandler(slot_bet_selected, pattern="^slot_bet_"))
    app.add_handler(CallbackQueryHandler(slot_result, pattern="^slot_"))
    
    # ======================== فوتبال ========================
    app.add_handler(CallbackQueryHandler(football_game, pattern="^football_game$"))
    app.add_handler(CallbackQueryHandler(football_bet_selected, pattern="^football_bet_"))
    app.add_handler(CallbackQueryHandler(football_result, pattern="^football_"))
    
    # ======================== حساب من ========================
    app.add_handler(CallbackQueryHandler(my_account, pattern="^my_account$"))
    app.add_handler(CallbackQueryHandler(deposit, pattern="^deposit$"))
    app.add_handler(CallbackQueryHandler(deposit_amount_selected, pattern="^deposit_"))
    app.add_handler(CallbackQueryHandler(withdraw, pattern="^withdraw$"))
    app.add_handler(CallbackQueryHandler(withdraw_amount_selected, pattern="^withdraw_"))
    app.add_handler(CallbackQueryHandler(withdraw_card, pattern="^withdraw_card$"))
    app.add_handler(CallbackQueryHandler(withdraw_wallet, pattern="^withdraw_wallet$"))
    app.add_handler(CallbackQueryHandler(transactions, pattern="^transactions$"))
    app.add_handler(CallbackQueryHandler(copy_trx, pattern="^copy_trx$"))
    app.add_handler(CallbackQueryHandler(copy_usdt, pattern="^copy_usdt$"))
    
    # ======================== سایر ========================
    app.add_handler(CallbackQueryHandler(gift, pattern="^gift$"))
    app.add_handler(CallbackQueryHandler(trust, pattern="^trust$"))
    
    # ======================== ادمین ========================
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_users, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(admin_settings, pattern="^admin_settings$"))
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
    app.add_handler(CallbackQueryHandler(admin_ban, pattern="^admin_ban$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast, pattern="^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(admin_global_gift, pattern="^admin_global_gift$"))
    app.add_handler(CallbackQueryHandler(admin_balance, pattern="^admin_balance$"))
    app.add_handler(CallbackQueryHandler(admin_search, pattern="^admin_search$"))
    app.add_handler(CallbackQueryHandler(admin_add_balance, pattern="^admin_add_"))
    app.add_handler(CallbackQueryHandler(admin_remove_balance, pattern="^admin_remove_"))
    
    # ======================== هندلرهای پیام ========================
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_balance_action))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_info))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))
    
    print("🤖 ربات شرطینو روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
