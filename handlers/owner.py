from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import random
import string
import os
from datetime import datetime, timedelta
from services.exchange_service import ExchangeService
from services.auth_service import AuthService
from services.deal_service import DealService
from database.models import db
from keyboards.menus import get_main_menu, get_owner_tokens_menu, get_back_button, get_stats_period_menu, get_stats_filter_menu
from config.settings import config

class OwnerStates(StatesGroup):
    waiting_token_role = State()
    setting_exchange_rate = State()
    deactivating_token = State()
    waiting_stats_period = State()
    waiting_stats_start_date = State()
    waiting_stats_end_date = State()
    deleting_deal = State()
    confirming_deposit = State()
    confirming_working_deposit = State()

# ============== ���������� ==============
async def show_owner_stats_menu(message: types.Message):
    """���� ������ ������� ����������"""
    await message.answer("?? �������� ������ ��� ����������:", reply_markup=get_stats_period_menu())

async def show_stats_by_period(message: types.Message):
    """�������� ����� ����������"""
    await show_stats_with_filter(message, "", "�� ��� �����")

async def process_stats_start_date(message: types.Message, state: FSMContext):
    """���������� ��������� ����"""
    if message.text == "?? �����":
        await state.clear()
        await show_owner_stats_menu(message)
        return
    
    try:
        start_date = datetime.strptime(message.text, "%d.%m.%Y")
        await state.update_data(start_date=start_date)
        await OwnerStates.waiting_stats_end_date.set()
        await message.answer(
            "?? ������� �������� ���� � ������� ��.��.����:\n"
            "������: 31.12.2024",
            reply_markup=get_back_button()
        )
    except ValueError:
        await message.answer("? �������� ������ ����. ����������� ��.��.����:")

async def process_stats_end_date(message: types.Message, state: FSMContext):
    """���������� �������� ����"""
    if message.text == "?? �����":
        await state.clear()
        await show_owner_stats_menu(message)
        return

    try:
        end_date = datetime.strptime(message.text, "%d.%m.%Y")
        data = await state.get_data()
        start_date = data.get('start_date')

        if end_date < start_date:
            await message.answer("? �������� ���� ������ ���� ����� ���������:")
            return

        date_filter = f"AND d.created_at >= '{start_date.strftime('%Y-%m-%d')}' AND d.created_at <= '{end_date.strftime('%Y-%m-%d 23:59:59')}'"
        period_text = f"� {start_date.strftime('%d.%m.%Y')} �� {end_date.strftime('%d.%m.%Y')}"

        await state.clear()
        await show_stats_with_filter(message, date_filter, period_text)

    except ValueError:
        await message.answer("? �������� ������ ����. ����������� ��.��.����:")

async def show_stats_with_filter(message: types.Message, date_filter: str, period_text: str):
    """�������� ���������� � ��������"""
    async with db.pool.acquire() as conn:
        # ���������� �������������
        user_stats = await conn.fetchrow('''
            SELECT
                COUNT(*) as total_users,
                COUNT(CASE WHEN role = 'trader' THEN 1 END) as traders,
                COUNT(CASE WHEN role = 'operator' THEN 1 END) as operators
            FROM users
        ''')

        # ���������� ������
        stats = await conn.fetchrow(f'''
            SELECT
                COUNT(DISTINCT d.deal_id) as total_deals,
                COALESCE(SUM(d.amount_rub), 0) as total_rub,
                COALESCE(SUM(d.amount_usdt), 0) as total_usdt,
                COALESCE(AVG(d.amount_rub), 0) as avg_deal_rub
            FROM deals d
            WHERE 1=1 {date_filter} AND d.is_deleted = FALSE
        ''')

        # ���������� �� �������� ������
        deal_stats = await conn.fetchrow(f'''
            SELECT
                COUNT(CASE WHEN status = 'confirmed' THEN 1 END) as confirmed,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                COUNT(CASE WHEN status = 'expired' THEN 1 END) as expired,
                COUNT(CASE WHEN status = 'disputed' THEN 1 END) as disputed,
                COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected
            FROM deals
            WHERE 1=1 {date_filter} AND is_deleted = FALSE
        ''')

        rate = await ExchangeService.get_current_rate()

        stats_text = f"""
?? ���������� ������� ({period_text})

?? ������������:
� �����: {user_stats['total_users'] or 0}
� ���������: {user_stats['traders'] or 0}
� ����������: {user_stats['operators'] or 0}

?? �������:
� ����� ������: {stats['total_deals'] or 0}
� ����� ������: {stats['total_rub'] or 0:.2f} RUB
� � USDT: {stats['total_usdt'] or 0:.2f} USDT
� ������� ������: {stats['avg_deal_rub'] or 0:.2f} RUB
� ������� ����: {rate} RUB/USDT

?? ������� ������:
? ������������: {deal_stats['confirmed'] or 0}
? � ��������: {deal_stats['pending'] or 0}
? �������: {deal_stats['expired'] or 0}
?? ������: {deal_stats['disputed'] or 0}
?? ���������: {deal_stats['rejected'] or 0}
"""

        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton(
                "?? �����",
                callback_data="back_to_stats_menu"
            )
        )

        await message.answer(stats_text, reply_markup=keyboard)

async def back_to_stats_menu_callback(callback_query: types.CallbackQuery):
    """��������� � ������� ���� ���������"""
    await callback_query.message.delete()
    await callback_query.message.answer("������� ����:", reply_markup=get_main_menu('owner'))

async def delete_deals_callback(callback_query: types.CallbackQuery):
    """������� ������ �� ������"""
    try:
        data = callback_query.data
        date_filter = data.replace("delete_deals_", "")
        
        async with db.pool.acquire() as conn:
            # ������������ ���������� ������ ��� ��������
            count = await conn.fetchrow(f'''
                SELECT COUNT(*) as count FROM deals
                WHERE 1=1 {date_filter} AND is_deleted = FALSE
            ''')
            
            if count['count'] == 0:
                await callback_query.answer("? ��� ������ ��� ��������")
                return
            
            # �������� ������ ��� ���������
            result = await conn.execute(f'''
                UPDATE deals SET is_deleted = TRUE
                WHERE 1=1 {date_filter} AND is_deleted = FALSE
            ''')
            
            await callback_query.answer(f"? ������� {result.split()[1]} ������")
            await callback_query.message.edit_text(
                f"{callback_query.message.text}\n\n? ������� {result.split()[1]} ������"
            )
            
    except Exception as e:
        print(f"Error in delete_deals_callback: {e}")
        await callback_query.answer("? ������ ��������")

# ============== ���������� �������� ==============
async def manage_tokens_start(message: types.Message):
    """Start token management"""
    await message.answer("?? ���������� ��������:", reply_markup=get_owner_tokens_menu())

async def create_token_start(message: types.Message, state: FSMContext):
    """Start creating new token"""
    await state.set_state(OwnerStates.waiting_token_role.state)
    await message.answer(
        "?? �������� ���� ��� ������ ������:\n"
        "������� 'trader', 'operator' ��� 'owner'",
        reply_markup=get_back_button()
    )

async def process_token_role(message: types.Message, state: FSMContext):
    """Process token role and generate token"""
    if message.text == "?? �����":
        await state.clear()
        await manage_tokens_start(message)
        return
    
    role = message.text.lower()
    if role not in ['trader', 'operator', 'owner']:
        await message.answer("? ������������ ����. ������� 'trader', 'operator' ��� 'owner':")
        return
    
    # Generate token
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    
    async with db.pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT user_id FROM users WHERE telegram_id = $1",
            message.from_user.id
        )
        
        await conn.execute(
            '''
            INSERT INTO tokens (token, role, created_by, is_active)
            VALUES ($1, $2, $3, TRUE)
            ''',
            token, role, user['user_id'] if user else None
        )
    
    await state.clear()
    await message.answer(
        f"? ����� ������� ������!\n\n"
        f"����: {role}\n"
        f"�����: `{token}`\n\n"
        f"?? ��������� ���� �����! �� ������ �� ����� �������.",
        parse_mode="Markdown",
        reply_markup=get_main_menu('owner')
    )

async def list_tokens(message: types.Message):
    """Show list of all tokens (������ ��������)"""
    async with db.pool.acquire() as conn:
        tokens = await conn.fetch(
            '''
            SELECT token, role, created_at
            FROM tokens
            WHERE is_active = TRUE
            ORDER BY created_at DESC
            '''
        )
        
        if not tokens:
            await message.answer("?? �������� ������� ���")
            return
        
        tokens_text = "?? ������ �������� �������:\n\n"
        for token in tokens:
            tokens_text += f"""
{token['role'].upper()}
�����: `{token['token']}`
������: {token['created_at'].strftime('%d.%m.%Y %H:%M')}
"""
        
        await message.answer(tokens_text, parse_mode="Markdown")

async def deactivate_token_start(message: types.Message, state: FSMContext):
    """Start deactivating token"""
    await state.set_state(OwnerStates.deactivating_token.state)
    await message.answer(
        "? ������� ����� ��� �����������:",
        reply_markup=get_back_button()
    )

async def process_deactivate_token(message: types.Message, state: FSMContext):
    """Deactivate token (������� �� �������)"""
    if message.text == "?? �����":
        await state.clear()
        await manage_tokens_start(message)
        return
    
    token = message.text.strip()
    
    async with db.pool.acquire() as conn:
        # ������� ����� ���������
        result = await conn.execute(
            "DELETE FROM tokens WHERE token = $1 RETURNING token",
            token
        )
        
        if "0" in str(result):
            await message.answer("? ����� �� ������")
        else:
            await message.answer("? ����� ������ �� �������")
    
    await state.clear()
    await message.answer("������� ����:", reply_markup=get_main_menu('owner'))

# ============== ���������� ������ ==============
async def manage_exchange_rate(message: types.Message):
    """Manage exchange rate"""
    rate = await ExchangeService.get_current_rate()
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("?? �������� �������������", callback_data="update_rate_auto"),
        types.InlineKeyboardButton("?? ���������� �������", callback_data="set_rate_manual")
    )
    
    await message.answer(
        f"?? ������� ���� USDT: {rate} RUB\n\n"
        f"�������� ��������:",
        reply_markup=keyboard
    )

async def update_rate_auto_callback(callback_query: types.CallbackQuery):
    """Handle auto rate update callback"""
    try:
        await callback_query.answer("?? ���������� �����...")
        rate = await ExchangeService.update_rate_automatically()
        
        if rate:
            await callback_query.message.edit_text(f"? ���� �������� �������������: {rate} RUB")
        else:
            await callback_query.message.edit_text(
                "? �� ������� �������� ���� �������������\n"
                "����������� ������ ��������� �����"
            )
    except Exception as e:
        print(f"Error in update_rate_auto_callback: {e}")
        await callback_query.message.edit_text(f"? ������: {str(e)}")

async def set_rate_manual_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Handle manual rate set callback"""
    await callback_query.answer()
    await OwnerStates.setting_exchange_rate.set()
    
    await callback_query.message.answer(
        "?? ������� ����� ���� USDT � RUB:\n"
        "������: 95.50",
        reply_markup=get_back_button()
    )

async def set_rate_manual_start(message: types.Message, state: FSMContext):
    """Start manual rate setting"""
    await state.set_state(OwnerStates.setting_exchange_rate.state)
    await message.answer(
        "?? ������� ����� ���� USDT � RUB:\n"
        "������: 95.50",
        reply_markup=get_back_button()
    )

async def process_manual_rate(message: types.Message, state: FSMContext):
    """Process manual rate"""
    if message.text == "?? �����":
        await state.clear()
        await message.answer("������� ����:", reply_markup=get_main_menu('owner'))
        return
    
    try:
        rate = float(message.text)
        if rate <= 0:
            raise ValueError
        
        async with db.pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT user_id FROM users WHERE telegram_id = $1",
                message.from_user.id
            )
        
        await ExchangeService.set_manual_rate(rate, user['user_id'] if user else None)
        
        await state.clear()
        await message.answer(
            f"? ���� ����������: {rate} RUB/USDT",
            reply_markup=get_main_menu('owner')
        )
        
    except ValueError:
        await message.answer("? ������� ���������� ����� (������ 0):")

async def auto_update_rate(message: types.Message):
    """Auto update exchange rate"""
    await message.answer("?? ���������� �����...")
    rate = await ExchangeService.update_rate_automatically()
    
    if rate:
        await message.answer(f"? ���� ��������: {rate} RUB/USDT")
    else:
        await message.answer("? �� ������� �������� ����")

# ============== ���������� �������������� ==============
async def manage_users(message: types.Message):
    """Manage users and their balances"""
    async with db.pool.acquire() as conn:
        traders = await conn.fetch('''
            SELECT user_id, username, telegram_id,
                   insurance_deposit, working_deposit,
                   insurance_deposit_confirmed, is_active
            FROM users
            WHERE role = 'trader'
            ORDER BY created_at DESC
        ''')
        
        if not traders:
            await message.answer("?? ��������� ��� � �������")
            return
        
        users_text = "?? ������ ���������:\n\n"
        
        for trader in traders:
            status = "?" if trader['insurance_deposit_confirmed'] else "?"
            active_status = "??" if trader['is_active'] else "??"
            
            users_text += f"""
{active_status} {status} @{trader['username'] or '��� username'} (ID: {trader['user_id']})
� ���������: {trader['insurance_deposit']} USDT
� �������: {trader['working_deposit']} USDT
� ������� �����������: {'��' if trader['insurance_deposit_confirmed'] else '���'}
� �������: {'��' if trader['is_active'] else '���'}
"""
        
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton(
                "? ����������� ��������� �������",
                callback_data="confirm_deposit_menu"
            ),
            types.InlineKeyboardButton(
                "?? ����������� ������� �������",
                callback_data="confirm_working_deposit_menu"
            )
        )
        
        await message.answer(users_text, reply_markup=keyboard)

async def confirm_deposit_menu_callback(callback_query: types.CallbackQuery):
    """���� ������������� ��������"""
    async with db.pool.acquire() as conn:
        traders = await conn.fetch('''
            SELECT user_id, username, telegram_id, insurance_deposit
            FROM users 
            WHERE role = 'trader' AND insurance_deposit_confirmed = FALSE
            ORDER BY created_at DESC
        ''')
        
        if not traders:
            await callback_query.answer("? ��� ��������� ��� �������������")
            return
        
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        for trader in traders:
            keyboard.add(
                types.InlineKeyboardButton(
                    f"@{trader['username'] or trader['user_id']}",
                    callback_data=f"confirm_deposit_{trader['user_id']}"
                )
            )
        
        await callback_query.message.answer(
            "?? �������� �������� ��� ������������� ��������:",
            reply_markup=keyboard
        )

async def confirm_working_deposit_menu_callback(callback_query: types.CallbackQuery):
    """���� ������������� �������� ��������"""
    async with db.pool.acquire() as conn:
        traders = await conn.fetch('''
            SELECT user_id, username, telegram_id, working_deposit
            FROM users
            WHERE role = 'trader'
            ORDER BY created_at DESC
        ''')

        if not traders:
            await callback_query.answer("? ��� ��������� ��� �������������")
            return

        keyboard = types.InlineKeyboardMarkup(row_width=2)
        for trader in traders:
            keyboard.add(
                types.InlineKeyboardButton(
                    f"@{trader['username'] or trader['user_id']} ({trader['working_deposit']} USDT)",
                    callback_data=f"confirm_working_deposit_{trader['user_id']}"
                )
            )

        await callback_query.message.answer(
            "?? �������� �������� ��� ������������� �������� ��������:",
            reply_markup=keyboard
        )

async def confirm_working_deposit_callback(callback_query: types.CallbackQuery):
    """����������� ������� ������� ��������"""
    try:
        data = callback_query.data
        if not data.startswith('confirm_working_deposit_'):
            await callback_query.answer("? �������� ������ �������")
            return

        trader_id = int(data.split('_')[3])

        async with db.pool.acquire() as conn:
            # �������� ������ ��������
            trader = await conn.fetchrow(
                "SELECT telegram_id, username, working_deposit FROM users WHERE user_id = $1",
                trader_id
            )

            if not trader:
                await callback_query.answer("? ������� �� ������")
                return

            # ���������� ����������� ��������
            if trader and trader['telegram_id']:
                try:
                    await callback_query.bot.send_message(
                        trader['telegram_id'],
                        f"?? *������ �����������!*\n\n"
                        f"? ��� ������� ������� ����������� ����������!\n\n"
                        f"?? �����: {trader['working_deposit']} USDT\n\n"
                        f"������ �� ������ ������������ ��� �������� ��� ������.\n"
                        f"?? �� �������� ����������� � ���������.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print(f"�� ������� ��������� ����������� ��������: {e}")

            await callback_query.answer(f"? ������� ������� �����������")

            # ��������� ���������� � �������������
            await manage_users(callback_query.message)

    except (ValueError, IndexError) as e:
        print(f"Error in confirm_working_deposit_callback: {e}")
        await callback_query.answer("? ������: �������� ������ ID ��������")
    except Exception as e:
        print(f"Error in confirm_working_deposit_callback: {e}")
        await callback_query.answer("? ������ �������������")

async def confirm_deposit_callback(callback_query: types.CallbackQuery):
    """����������� ������� ��������"""
    try:
        # ��������� ������ callback_data: "confirm_deposit_123"
        data = callback_query.data
        if not data.startswith('confirm_deposit_'):
            await callback_query.answer("? �������� ������ �������")
            return
        
        trader_id = int(data.split('_')[2])
        
        async with db.pool.acquire() as conn:
            # ������������ ������� � ���������� ������������
            await conn.execute(
                '''
                UPDATE users 
                SET insurance_deposit_confirmed = TRUE,
                    is_active = TRUE,
                    insurance_deposit = $1
                WHERE user_id = $2 AND role = 'trader'
                ''',
                config.REQUIRED_INSURANCE_DEPOSIT,
                trader_id
            )
            
            # �������� ������ �������� ��� �����������
            trader = await conn.fetchrow(
                "SELECT telegram_id, username FROM users WHERE user_id = $1",
                trader_id
            )
            
            if trader and trader['telegram_id']:
                # ���������� ����������� ��������
                try:
                    await callback_query.bot.send_message(
                        trader['telegram_id'],
                        f"?? *������ �����������!*\n\n"
                        f"? ��� ��������� ������� ����������� ����������!\n\n"
                        f"������ �� ������ ������ ������ � �������:\n"
                        f"1. �������� ��������� ����� ���� '?? ��� ���������'\n"
                        f"2. �������� ������ �� ����������\n"
                        f"3. ������������� ����������� �������\n\n"
                        f"?? �� �������� ����������� � ���������.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print(f"�� ������� ��������� ����������� ��������: {e}")
            
            # ��������� ���������� � ������������� ��� �����������
            traders = await conn.fetch('''
                SELECT user_id, username, telegram_id, 
                       insurance_deposit, working_deposit,
                       insurance_deposit_confirmed, is_active
                FROM users 
                WHERE role = 'trader'
                ORDER BY created_at DESC
            ''')
            
            users_text = "?? ������ ���������:\n\n"
            
            for trader_data in traders:
                status = "?" if trader_data['insurance_deposit_confirmed'] else "?"
                active_status = "??" if trader_data['is_active'] else "??"
                
                users_text += f"""
{active_status} {status} @{trader_data['username'] or '��� username'} (ID: {trader_data['user_id']})
� ���������: {trader_data['insurance_deposit']} USDT
� �������: {trader_data['working_deposit']} USDT
� ������� �����������: {'��' if trader_data['insurance_deposit_confirmed'] else '���'}
� �������: {'��' if trader_data['is_active'] else '���'}
"""
            
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton(
                    "? ����������� �������", 
                    callback_data="confirm_deposit_menu"
                )
            )
            
            await callback_query.answer(f"? ������� ����������� � ������� �����������")
            await callback_query.message.edit_text(
                f"{users_text}",
                reply_markup=keyboard
            )
            
    except (ValueError, IndexError) as e:
        print(f"Error in confirm_deposit_callback: {e}")
        await callback_query.answer("? ������: �������� ������ ID ��������")
    except Exception as e:
        print(f"Error in confirm_deposit_callback: {e}")
        await callback_query.answer("? ������ �������������")

async def delete_specific_deal_start(message: types.Message, state: FSMContext):
    """������ �������� ���������� ������"""
    await state.set_state(OwnerStates.deleting_deal.state)
    await message.answer(
        "??? ������� ����� ������ ��� ��������:\n"
        "������: D202501011234",
        reply_markup=get_back_button()
    )

async def delete_specific_deal(message: types.Message, state: FSMContext):
    """������� ���������� ������"""
    if message.text == "?? �����":
        await state.clear()
        await message.answer("������� ����:", reply_markup=get_main_menu('owner'))
        return
    
    deal_number = message.text.strip()
    
    async with db.pool.acquire() as conn:
        deal = await conn.fetchrow(
            "SELECT deal_id FROM deals WHERE deal_number = $1 AND is_deleted = FALSE",
            deal_number
        )
        
        if not deal:
            await message.answer("? ������ �� �������")
            return
        
        await conn.execute(
            "UPDATE deals SET is_deleted = TRUE WHERE deal_id = $1",
            deal['deal_id']
        )
        
        await message.answer(f"? ������ #{deal_number} �������")
    
    await state.clear()

# ============== ���������� ������ ����� ==============
async def handle_back_from_tokens(message: types.Message, state: FSMContext):
    """Handle back button from token management"""
    await state.clear()
    await message.answer("������� ����:", reply_markup=get_main_menu('owner'))

# ============== ����������� ������������ ==============
def register_owner_handlers(router: Router):
    # ����������
    router.message.register(show_owner_stats_menu, F.text == "?? ����� ����������")
    router.message.register(show_stats_by_period, F.text == "?? ����� ����������", )
    
    # ���������� ��������
    router.message.register(manage_tokens_start, F.text == "?? ���������� ��������")
    router.message.register(create_token_start, F.text == "?? ������� �����", )
    router.message.register(process_token_role, waiting_token_role)
    router.message.register(list_tokens, F.text == "?? ������ �������")
    router.message.register(deactivate_token_start, F.text == "? �������������� �����", )
    router.message.register(process_deactivate_token, deactivating_token)
    
    # ���������� ������
    router.message.register(manage_exchange_rate, F.text == "?? ���� USDT")
    router.message.register(set_rate_manual_start, F.text == "?? ���������� ����", )
    router.message.register(process_manual_rate, setting_exchange_rate)
    router.message.register(auto_update_rate, F.text == "?? �������������� �����")
    
    # ���������� ��������������
    router.message.register(manage_users, F.text == "?? ���������� ��������������")
    
    # �������� ������
    router.message.register(delete_specific_deal_start, F.text == "??? ������� ������", )
    router.message.register(delete_specific_deal, deleting_deal)
    
    # ������ "�����"
    router.message.register(handle_back_from_tokens, F.text == "?? �����", )
    
    # Callback ��������
    router.callback_query.register(
        update_rate_auto_callback, 
        lambda c: c.data == "update_rate_auto"
    )
    router.callback_query.register(
        set_rate_manual_callback, 
        lambda c: c.data == "set_rate_manual",
        
    )
    router.callback_query.register(
        delete_deals_callback,
        F.data.startswith('delete_deals_')
    )
    router.callback_query.register(
        back_to_stats_menu_callback,
        lambda c: c.data == "back_to_stats_menu"
    )
    router.callback_query.register(
        confirm_deposit_menu_callback,
        lambda c: c.data == "confirm_deposit_menu"
    )
    router.callback_query.register(
        confirm_deposit_callback,
        F.data.startswith('confirm_deposit_')
    )
    router.callback_query.register(
        confirm_working_deposit_menu_callback,
        lambda c: c.data == "confirm_working_deposit_menu"
    )
    router.callback_query.register(
        confirm_working_deposit_callback,
        F.data.startswith('confirm_working_deposit_')
    )
