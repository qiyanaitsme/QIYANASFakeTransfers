from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("🔑 Create Wallet"))
    keyboard.add(KeyboardButton("💼 My Wallets"), KeyboardButton("💰 Balance"))
    keyboard.add(KeyboardButton("📥 Deposit"), KeyboardButton("📤 Withdraw"))
    keyboard.add(KeyboardButton("💱 Exchange"), KeyboardButton("📊 History"))
    return keyboard

def get_wallet_creation_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Bitcoin (BTC)", callback_data="create_btc"))
    keyboard.add(InlineKeyboardButton("Ethereum (ETH)", callback_data="create_eth"))
    keyboard.add(InlineKeyboardButton("USDT (TRC20)", callback_data="create_usdt"))
    return keyboard
