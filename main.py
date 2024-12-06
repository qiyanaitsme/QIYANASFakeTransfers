import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from config import BOT_TOKEN, ADMIN_ID
from database import init_models, get_session
from models import User, Transaction
from utils import (
    generate_btc_address_async,
    generate_eth_address_async,
    generate_trc20_address_async,
    generate_transaction_hash_async
)
from collections import defaultdict

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Message tracking
user_messages = defaultdict(list)
MAX_MESSAGES = 2

WITHDRAWAL_FEES = {
    'BTC': 0.0005,
    'ETH': 0.005,
    'USDT': 1.0
}

async def cleanup_messages(chat_id):
    while len(user_messages[chat_id]) > MAX_MESSAGES:
        msg_to_delete = user_messages[chat_id].pop(0)
        try:
            await msg_to_delete.delete()
        except:
            pass

async def send_tracked_message(chat_id, text, reply_markup=None, parse_mode=None):
    msg = await bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
    user_messages[chat_id].append(msg)
    await cleanup_messages(chat_id)
    return msg

class WalletStates(StatesGroup):
    waiting_for_wallet_type = State()

class AdminStates(StatesGroup):
    waiting_for_wallet = State()
    waiting_for_amount = State()

class WithdrawStates(StatesGroup):
    waiting_for_wallet = State()
    waiting_for_address = State()  # Add this line
    waiting_for_amount = State()
    waiting_for_confirmation = State()

class AdminDepositStates(StatesGroup):
    waiting_for_wallet = State()
    waiting_for_amount = State()

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔑 Create Wallet", callback_data="create_wallet"),
        InlineKeyboardButton("💼 My Wallets", callback_data="my_wallets"),
        InlineKeyboardButton("💰 Balance", callback_data="balance"),
        InlineKeyboardButton("📤 Withdraw", callback_data="withdraw"),
        InlineKeyboardButton("📋 History", callback_data="history")
    )
    if message.from_user.id == ADMIN_ID:
        keyboard.add(InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel"))

    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar()
        
        if not user:
            user = User(telegram_id=message.from_user.id)
            session.add(user)
            await session.commit()
    
    await send_tracked_message(
        message.chat.id,
        "Welcome to Crypto Wallet Bot! 🚀\nSelect an option from the menu below:",
        reply_markup=keyboard
    )

@dp.callback_query_handler(text="admin_panel")
async def admin_panel(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📊 Recent Transactions", callback_data="admin_transactions"),
        InlineKeyboardButton("👥 Users List", callback_data="admin_users"),
        InlineKeyboardButton("📥 Manual Deposit", callback_data="admin_deposit"),
        InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")
    )
    
    await send_tracked_message(callback_query.message.chat.id, "👑 Admin Panel", reply_markup=keyboard)

@dp.callback_query_handler(text="back_to_main")
async def back_to_main(callback_query: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔑 Create Wallet", callback_data="create_wallet"),
        InlineKeyboardButton("💼 My Wallets", callback_data="my_wallets"),
        InlineKeyboardButton("💰 Balance", callback_data="balance"),
        InlineKeyboardButton("📤 Withdraw", callback_data="withdraw"),
        InlineKeyboardButton("📋 History", callback_data="history")
    )
    if callback_query.from_user.id == ADMIN_ID:
        keyboard.add(InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel"))
    
    await send_tracked_message(
        callback_query.message.chat.id,
        "Main Menu:",
        reply_markup=keyboard
    )

@dp.callback_query_handler(text="create_wallet")
async def create_wallet_command(callback_query: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Bitcoin (BTC)", callback_data="direct_create_btc"),
        InlineKeyboardButton("Ethereum (ETH)", callback_data="direct_create_eth"),
        InlineKeyboardButton("USDT (TRC20)", callback_data="direct_create_usdt"),
        InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")
    )
    await send_tracked_message(
        callback_query.message.chat.id,
        "Select cryptocurrency type for your new wallet:",
        reply_markup=keyboard
    )


@dp.callback_query_handler(lambda c: c.data.startswith('direct_create_'))
async def direct_wallet_creation(callback_query: types.CallbackQuery):
    coin_type = callback_query.data.replace('direct_create_', '')
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback_query.from_user.id)
        )
        user = result.scalar()
        
        if coin_type == 'btc' and not user.btc_address:
            user.btc_address = await generate_btc_address_async()
        elif coin_type == 'eth' and not user.eth_address:
            user.eth_address = await generate_eth_address_async()
        elif coin_type == 'usdt' and not user.usdt_address:
            user.usdt_address = await generate_trc20_address_async()
        else:
            await callback_query.answer("You already have this wallet type!")
            return
        
        await session.commit()
        await callback_query.message.answer(
            f"✅ New {coin_type.upper()} wallet created:\n`{getattr(user, f'{coin_type}_address')}`",
            parse_mode="Markdown"
        )

@dp.callback_query_handler(text="my_wallets")
async def show_wallets(callback_query: types.CallbackQuery):
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback_query.from_user.id)
        )
        user = result.scalar()
        
        response = "Your wallet addresses:\n\n"
        if user.btc_address:
            response += f"🔹 BTC: `{user.btc_address}`\n"
        if user.eth_address:
            response += f"🔹 ETH: `{user.eth_address}`\n"
        if user.usdt_address:
            response += f"🔹 USDT: `{user.usdt_address}`\n"
        
        if response == "Your wallet addresses:\n\n":
            response = "You don't have any wallets yet. Create one using '🔑 Create Wallet' button!"
    
    await callback_query.message.answer(response, parse_mode="Markdown")

@dp.callback_query_handler(text="balance")
async def show_balance(callback_query: types.CallbackQuery):
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback_query.from_user.id)
        )
        user = result.scalar()
        
        response = "Your balances:\n\n"
        if user.btc_address:
            response += f"🔹 BTC: {user.btc_balance or 0.0:.8f}\n"
        if user.eth_address:
            response += f"🔹 ETH: {user.eth_balance or 0.0:.8f}\n"
        if user.usdt_address:
            response += f"🔹 USDT: {user.usdt_balance or 0.0:.2f}\n"
        
        if response == "Your balances:\n\n":
            response = "You don't have any wallets yet. Create one using '🔑 Create Wallet' button!"
    
    await send_tracked_message(callback_query.message.chat.id, response)

@dp.callback_query_handler(text="withdraw")
async def withdraw_start(callback_query: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Bitcoin (BTC)", callback_data="withdraw_btc"),
        InlineKeyboardButton("Ethereum (ETH)", callback_data="withdraw_eth"),
        InlineKeyboardButton("USDT (TRC20)", callback_data="withdraw_usdt")
    )
    await WithdrawStates.waiting_for_wallet.set()
    await callback_query.message.answer("Select cryptocurrency to withdraw:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith('withdraw_'), state=WithdrawStates.waiting_for_wallet)
async def process_withdraw_coin(callback_query: types.CallbackQuery, state: FSMContext):
    coin_type = callback_query.data.replace('withdraw_', '').upper()
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback_query.from_user.id)
        )
        user = result.scalar()
        wallet_address = getattr(user, f"{coin_type.lower()}_address")
        
        if not wallet_address:
            await send_tracked_message(callback_query.message.chat.id, 
                f"You don't have a {coin_type} wallet. Please create one first.")
            await state.finish()
            return
        
        await state.update_data(coin_type=coin_type, from_address=wallet_address)
        await WithdrawStates.waiting_for_address.set()
        await send_tracked_message(callback_query.message.chat.id, 
            f"Enter recipient's {coin_type} address:")

@dp.message_handler(state=WithdrawStates.waiting_for_address)
async def process_withdraw_address(message: types.Message, state: FSMContext):
    to_address = message.text
    await state.update_data(to_address=to_address)
    data = await state.get_data()
    
    await WithdrawStates.waiting_for_amount.set()
    await send_tracked_message(message.chat.id, 
        f"Enter amount to withdraw (Fee: {WITHDRAWAL_FEES[data['coin_type']]} {data['coin_type']}):")

@dp.callback_query_handler(text="admin_panel")
async def admin_panel(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📊 Recent Transactions", callback_data="admin_transactions"),
        InlineKeyboardButton("👥 Users List", callback_data="admin_users"),
        InlineKeyboardButton("📥 Manual Deposit", callback_data="admin_deposit")
    )
    
    await callback_query.message.answer("👑 Admin Panel", reply_markup=keyboard)

@dp.callback_query_handler(text="admin_users")
async def admin_users_list(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    async with get_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        response = "👥 Users List:\n\n"
        for user in users:
            response += (
                f"User ID: {user.telegram_id}\n"
                f"BTC Balance: {user.btc_balance:.8f}\n"
                f"ETH Balance: {user.eth_balance:.8f}\n"
                f"USDT Balance: {user.usdt_balance:.2f}\n"
                f"{'─' * 20}\n"
            )
        
        await callback_query.message.answer(response)

@dp.callback_query_handler(text="admin_transactions")
async def admin_transactions(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    async with get_session() as session:
        result = await session.execute(
            select(Transaction)
            .order_by(Transaction.timestamp.desc())
            .limit(20)
        )
        transactions = result.scalars().all()
        
        response = "Recent transactions:\n\n"
        for tx in transactions:
            response += (
                f"User ID: {tx.user_id}\n"
                f"Type: {'📥' if tx.transaction_type == 'deposit' else '📤'} {tx.transaction_type}\n"
                f"Amount: {tx.amount} {tx.coin_type}\n"
                f"Status: {get_status_emoji(tx.status)}\n"
                f"Hash: `{tx.tx_hash}`\n"
                f"{'─' * 20}\n"
            )
        
        await callback_query.message.answer(response, parse_mode="Markdown")

@dp.message_handler(state=WithdrawStates.waiting_for_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        data = await state.get_data()
        coin_type = data['coin_type']
        fee = WITHDRAWAL_FEES[coin_type]
        total_amount = amount + fee
        
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )
            user = result.scalar()
            
            balance = getattr(user, f"{coin_type.lower()}_balance")
            if balance < total_amount:
                await send_tracked_message(message.chat.id, 
                    f"Insufficient balance. You need {total_amount} {coin_type} (including fee)")
                await state.finish()
                return
            
            await state.update_data(amount=amount)
            
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton("✅ Confirm", callback_data="confirm_withdrawal"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdrawal")
            )
            
            await WithdrawStates.waiting_for_confirmation.set()
            await send_tracked_message(
                message.chat.id,
                f"📤 Withdrawal Details:\n\n"
                f"From Wallet: `{data['from_address']}`\n"
                f"To Wallet: `{data['to_address']}`\n"
                f"Amount: {amount} {coin_type}\n"
                f"Fee: {fee} {coin_type}\n"
                f"Total: {total_amount} {coin_type}",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
    except ValueError:
        await send_tracked_message(message.chat.id, "Please enter a valid number")

@dp.callback_query_handler(lambda c: c.data in ['confirm_withdrawal', 'cancel_withdrawal'], state=WithdrawStates.waiting_for_confirmation)
async def process_withdraw_confirmation(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == 'cancel_withdrawal':
        await send_tracked_message(callback_query.message.chat.id, "Withdrawal cancelled")
        await state.finish()
        return
    
    data = await state.get_data()
    coin_type = data['coin_type']
    amount = float(data['amount'])
    fee = WITHDRAWAL_FEES[coin_type]
    
    tx_hash = await generate_transaction_hash_async()
    short_hash = tx_hash[:8]
    
    async with get_session() as session:
        transaction = Transaction(
            user_id=callback_query.from_user.id,
            transaction_type='withdrawal',
            coin_type=coin_type,
            amount=amount,
            fee=fee,
            from_address=data['from_address'],
            to_address=data['to_address'],
            tx_hash=tx_hash,
            status='pending'
        )
        session.add(transaction)
        
        admin_keyboard = InlineKeyboardMarkup()
        admin_keyboard.add(
            InlineKeyboardButton("✅ Approve", callback_data=f"a_{short_hash}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"r_{short_hash}")
        )
        
        await send_tracked_message(
            ADMIN_ID,
            f"🔄 New withdrawal request:\n\n"
            f"From Wallet: `{data['from_address']}`\n"
            f"To Wallet: `{data['to_address']}`\n"
            f"Amount: {amount} {coin_type}\n"
            f"Fee: {fee} {coin_type}\n"
            f"Hash: `{tx_hash}`",
            reply_markup=admin_keyboard,
            parse_mode="Markdown"
        )
        
        await session.commit()
        
    await send_tracked_message(
        callback_query.message.chat.id,
        f"Withdrawal request submitted!\n"
        f"Transaction Hash: `{tx_hash}`\n"
        f"Status: Pending admin approval",
        parse_mode="Markdown"
    )
    
    await state.finish()

@dp.callback_query_handler(text="admin_deposit")
async def admin_deposit_start(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("BTC", callback_data="deposit_btc"),
        InlineKeyboardButton("ETH", callback_data="deposit_eth"),
        InlineKeyboardButton("USDT", callback_data="deposit_usdt")
    )
    await AdminDepositStates.waiting_for_wallet.set()
    await callback_query.message.answer("Select coin type for deposit:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith('deposit_'), state=AdminDepositStates.waiting_for_wallet)
async def process_deposit_coin(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    coin_type = callback_query.data.replace('deposit_', '').upper()
    await state.update_data(coin_type=coin_type)
    await callback_query.message.answer(f"Enter {coin_type} wallet address:")

@dp.message_handler(state=AdminDepositStates.waiting_for_wallet)
async def process_deposit_wallet(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    wallet_address = message.text
    data = await state.get_data()
    coin_type = data['coin_type']
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(getattr(User, f"{coin_type.lower()}_address") == wallet_address)
        )
        user = result.scalar()
        
        if not user:
            await message.answer("Wallet address not found in system!")
            await state.finish()
            return
        
        await state.update_data(wallet_address=wallet_address, user_id=user.telegram_id)
        await AdminDepositStates.waiting_for_amount.set()
        await message.answer(f"Enter amount in {coin_type}:")

@dp.message_handler(state=AdminDepositStates.waiting_for_amount)
async def process_deposit_amount(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        amount = float(message.text)
        data = await state.get_data()
        
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == data['user_id'])
            )
            user = result.scalar()
            
            balance_attr = f"{data['coin_type'].lower()}_balance"
            current_balance = getattr(user, balance_attr)
            setattr(user, balance_attr, current_balance + amount)
            
            tx_hash = await generate_transaction_hash_async()
            
            transaction = Transaction(
                user_id=user.telegram_id,
                transaction_type='deposit',
                coin_type=data['coin_type'],
                amount=amount,
                fee=0,
                from_address='admin_deposit',
                to_address=data['wallet_address'],
                tx_hash=tx_hash,
                status='completed'
            )
            session.add(transaction)
            await session.commit()
            
            await message.answer(
                f"✅ Deposit successful!\n"
                f"Wallet: {data['wallet_address']}\n"
                f"Amount: {amount} {data['coin_type']}\n"
                f"New balance: {getattr(user, balance_attr)} {data['coin_type']}"
            )
            
            await bot.send_message(
                user.telegram_id,
                f"💰 Your wallet has been credited!\n"
                f"Amount: {amount} {data['coin_type']}\n"
                f"Transaction Hash: `{tx_hash}`",
                parse_mode="Markdown"
            )
            
    except ValueError:
        await message.answer("Please enter a valid number")
    
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith('a_'))
async def approve_withdrawal(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        return
        
    short_hash = callback_query.data.replace('a_', '')
    async with get_session() as session:
        result = await session.execute(
            select(Transaction).where(Transaction.tx_hash.like(f"{short_hash}%"))
        )
        transaction = result.scalar()
        
        if transaction and transaction.status == 'pending':
            transaction.status = 'completed'
            
            result = await session.execute(
                select(User).where(User.telegram_id == transaction.user_id)
            )
            user = result.scalar()
            balance_attr = f"{transaction.coin_type.lower()}_balance"
            current_balance = getattr(user, balance_attr) or 0
            setattr(user, balance_attr, current_balance - (transaction.amount + transaction.fee))
            
            await session.commit()
            
            await send_tracked_message(
                transaction.user_id,
                f"✅ Withdrawal approved!\n"
                f"Amount: {transaction.amount} {transaction.coin_type}\n"
                f"Transaction Hash: `{transaction.tx_hash}`",
                parse_mode="Markdown"
            )
            
            await callback_query.message.edit_text(
                callback_query.message.text + "\n\nStatus: ✅ Approved"
            )

@dp.callback_query_handler(lambda c: c.data.startswith('reject_'))
async def reject_withdrawal(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        return
        
    tx_hash = callback_query.data.replace('reject_', '')
    async with get_session() as session:
        result = await session.execute(
            select(Transaction).where(Transaction.tx_hash == tx_hash)
        )
        transaction = result.scalar()
        
        if transaction and transaction.status == 'pending':
            transaction.status = 'rejected'
            await session.commit()
            
            await bot.send_message(
                transaction.user_id,
                f"❌ Withdrawal rejected!\n"
                f"Amount: {transaction.amount} {transaction.coin_type}\n"
                f"Transaction Hash: `{transaction.tx_hash}`",
                parse_mode="Markdown"
            )
            
            await callback_query.message.edit_text(
                callback_query.message.text + "\n\nStatus: ❌ Rejected"
            )

@dp.callback_query_handler(text="history")
async def show_history(callback_query: types.CallbackQuery):
    async with get_session() as session:
        result = await session.execute(
            select(Transaction)
            .where(Transaction.user_id == callback_query.from_user.id)
            .order_by(Transaction.timestamp.desc())
            .limit(10)
        )
        transactions = result.scalars().all()
        
        if not transactions:
            await callback_query.message.answer("No transaction history yet.")
            return
        
        response = "Recent transactions:\n\n"
        for tx in transactions:
            response += (
                f"{'📥' if tx.transaction_type == 'deposit' else '📤'} "
                f"{tx.amount} {tx.coin_type}\n"
                f"Fee: {tx.fee} {tx.coin_type}\n"
                f"Status: {get_status_emoji(tx.status)}\n"
                f"Hash: `{tx.tx_hash}`\n"
                f"Date: {tx.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )
        
        await callback_query.message.answer(response, parse_mode="Markdown")

def get_status_emoji(status):
    return {
        'pending': '⏳',
        'completed': '✅',
        'rejected': '❌'
    }.get(status, '❓')

async def on_startup(dp):
    await init_models()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
