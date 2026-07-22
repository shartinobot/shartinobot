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
TRX_WALLET = os.environ.get("TRX_WALLET", "TEv9t55am7zcCi2Z7dUXtFfKQmofeN7e1r")
USDT_WALLET = os.environ.get("USDT_WALLET", "TEVuvWZ68UbDUdzpd6EqxncsqDVjwyY7cj")

MIN_BET = int(os.environ.get("MIN_BET", 10000))
GIFT_AMOUNT = int(os.environ.get("GIFT_AMOUNT", 50000))
MIN_WITHDRAW = int(os.environ.get("MIN_WITHDRAW", 500000))
COMMISSION_PERCENT = int(os.environ.get("COMMISSION_PERCENT", 30))
INITIAL_BALANCE = int(os.environ.get("INITIAL_BALANCE", 0))

# آیدی پشتیبانی ثابت
SUPPORT = "@shartino_sup"

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
        "💎💎💎": 100, "⭐⭐⭐": 50, "۷۷۷": 20,
        "🍇🍇🍇": 15, "🍋🍋🍋": 10, "🍒🍒🍒": 5, "two_same": 2
    }
})

# ======================== توابع کاربر ========================
def get_user(user_id):
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "balance": INITIAL_B
