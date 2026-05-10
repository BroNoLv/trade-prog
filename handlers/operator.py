from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.deal_service import DealService
from services.exchange_service import ExchangeService
from services.auth_service import AuthService
from database.models import db
from keyboards.menus import get_main_menu, get_dispute_keyboard

class OperatorStates(StatesGroup):
    waiting_deal_amount = State()
    searching_transaction = State()

async def create_deal_start(message: types.Message, state: FSMContext):
    """Start creating new deal"""
    await state.set_state(OperatorStates.waiting_deal_amount.state)
    await message.answer(
        "💰 Введите сумму сделки в RUB:\n"
        "Пример: 15000",
        reply_markup=types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="🔙 Назад")]], resize_keyboard=True)
    )

async def process_deal_amount(message: types.Message, state: FSMContext):
    """Process deal amount and create deal"""
    if message.text == "🔙 Назад":
        await state.clear()
        await message.answer("Главное меню:", reply_markup=get_main_menu('operator'))
        return
    
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        
        async with db.pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT user_id FROM users WHERE telegram_id = $1",
                message.from_user.id
            )
            
            if not user:
                await message.answer("❌ Пользователь не найден")
                return
        
        deal, details = await DealService.create_deal(user['user_id'], amount)
        
        if not deal:
            await message.answer("❌ Не найдено подходящих реквизитов для этой суммы")
            return
        
        # Get current rate
        rate = await ExchangeService.get_current_rate()
        
        deal_text = f"""
✅ Создана новая заявка #{deal['deal_number']}

💳 Реквизиты для оплаты:
• Банк: {details['bank_name']}
• ФИО: {details['full_name']}
"""
        
        if details.get('card_number'):
            card_num = details['card_number']
            deal_text += f"• Номер карты: {card_num}\n"
        
        if details.get('phone_number'):
            deal_text += f"• СБП: {details['phone_number']}\n"
        
        deal_text += f"""
💰 Сумма: {amount} RUB / {deal['amount_usdt']} USDT
📅 Создана: {deal['created_at'].strftime('%d.%m.%Y %H:%M')}
⏳ Оплатить до: {deal['expires_at'].strftime('%d.%m.%Y %H:%M')}

📝 ИНСТРУКЦИЯ:
Отправлять сумму необходимо ТОЧНО {amount} RUB.
На оплату дается 30 минут.
В случае неверной суммы или просрочки платеж не будет засчитан.
"""
        
        await state.clear()
        await message.answer(deal_text, reply_markup=get_main_menu('operator'))
        
    except ValueError:
        await message.answer("❌ Введите корректную сумму (число больше 0):")

async def show_operator_stats(message: types.Message):
    """Show operator statistics"""
    async with db.pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT user_id FROM users WHERE telegram_id = $1",
            message.from_user.id
        )
        
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        stats = await conn.fetchrow(
            '''
            SELECT 
                COUNT(*) as total_deals,
                SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed_deals,
                SUM(CASE WHEN status = 'expired' THEN 1 ELSE 0 END) as expired_deals,
                SUM(CASE WHEN status = 'confirmed' THEN amount_rub ELSE 0 END) as total_rub,
                SUM(CASE WHEN status = 'confirmed' THEN amount_usdt ELSE 0 END) as total_usdt
            FROM deals 
            WHERE operator_id = $1 AND is_deleted = FALSE
            ''',
            user['user_id']
        )
        
        rate = await ExchangeService.get_current_rate()
        
        stats_text = f"""
📊 Статистика оператора

📈 Общая статистика:
• Всего заявок: {stats['total_deals'] or 0}
• Подтверждено: {stats['confirmed_deals'] or 0}
• Истекло: {stats['expired_deals'] or 0}

💰 Финансы:
• Общая сумма: {stats['total_rub'] or 0} RUB
• В USDT: {stats['total_usdt'] or 0} USDT
• Текущий курс: {rate} RUB/USDT
"""
        
        await message.answer(stats_text)

async def search_transactions_start(message: types.Message, state: FSMContext):
    """Start transaction search"""
    await state.set_state(OperatorStates.searching_transaction.state)
    await message.answer(
        "🔍 Введите номер заявки или сумму для поиска:",
        reply_markup=types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="🔙 Назад")]], resize_keyboard=True)
    )

async def show_active_deals_operator(message: types.Message):
    """Show operator's active deals"""
    async with db.pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT user_id FROM users WHERE telegram_id = $1",
            message.from_user.id
        )

        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        deals = await conn.fetch(
            '''
            SELECT d.*, COALESCE(u.username, 'ID:' || u.user_id::text) as trader_name
            FROM deals d
            LEFT JOIN users u ON d.trader_id = u.user_id
            WHERE d.operator_id = $1 AND d.status = 'pending' AND d.is_deleted = FALSE
            ORDER BY d.created_at DESC
            ''',
            user['user_id']
        )

        if not deals:
            await message.answer("📭 Активных заявок нет")
            return

        for deal in deals:
            status_emoji = {
                'pending': '⏳',
                'confirmed': '✅',
                'expired': '❌',
                'disputed': '⚖️'
            }.get(deal['status'], '❓')

            deal_text = f"""
{status_emoji} Заявка #{deal['deal_number']}

💰 Сумма: {deal['amount_rub']} RUB
👤 Трейдер: {deal['trader_name']}
🕐 Создана: {deal['created_at'].strftime('%d.%m.%Y %H:%M')}
⏳ Статус: {deal['status']}
"""

            keyboard_buttons = []
            if deal['status'] == 'pending':
                keyboard_buttons.append([types.InlineKeyboardButton(
                    text="⚖️ Открыть спор",
                    callback_data=f"open_dispute_{deal['deal_id']}"
                )])
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

            await message.answer(deal_text, reply_markup=keyboard)

async def show_disputes(message: types.Message):
    """Show operator's disputes"""
    async with db.pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT user_id, role FROM users WHERE telegram_id = $1",
            message.from_user.id
        )

        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        if user['role'] != 'operator':
            await message.answer("❌ Доступ запрещен. Только операторы могут использовать эту функцию.")
            return

        disputes = await conn.fetch(
            '''
            SELECT d.*, COALESCE(u.username, 'ID:' || u.user_id::text) as trader_name
            FROM deals d
            LEFT JOIN users u ON d.trader_id = u.user_id
            WHERE d.operator_id = $1 AND d.dispute_opened = TRUE AND d.is_deleted = FALSE
            ORDER BY d.created_at DESC
            ''',
            user['user_id']
        )

        if not disputes:
            await message.answer("📭 Споров нет")
            return

        for dispute in disputes:
            dispute_text = f"""
⚖️ Спор по заявке #{dispute['deal_number']}

💰 Сумма: {dispute['amount_rub']} RUB
👤 Трейдер: {dispute['trader_name']}
🕐 Создана: {dispute['created_at'].strftime('%d.%m.%Y %H:%M')}
"""

            await message.answer(dispute_text)

async def handle_dispute_callback(callback_query: types.CallbackQuery):
    """Handle dispute button"""
    try:
        if '_' not in callback_query.data or len(callback_query.data.split('_')) < 3:
            await callback_query.answer("❌ Неверный формат запроса")
            return
        
        data = callback_query.data
        action = data.split('_')[1]  # open_dispute_123
        deal_id = int(data.split('_')[2])
        
        if action == 'dispute':
            async with db.pool.acquire() as conn:
                await conn.execute(
                    '''
                    UPDATE deals 
                    SET dispute_opened = TRUE,
                        status = 'disputed'
                    WHERE deal_id = $1 AND is_deleted = FALSE
                    ''',
                    deal_id
                )
                
                user = await conn.fetchrow(
                    "SELECT user_id FROM users WHERE telegram_id = $1",
                    callback_query.from_user.id
                )
                
                await conn.execute(
                    '''
                    INSERT INTO disputes (deal_id, opened_by)
                    VALUES ($1, $2)
                    ''',
                    deal_id, user['user_id']
                )
            
            await callback_query.answer("⚖️ Спор открыт!")
            await callback_query.message.edit_text(
                f"{callback_query.message.text}\n\n✅ Спор открыт"
            )
            
    except Exception as e:
        print(f"Error in handle_dispute_callback: {e}")
        await callback_query.answer("❌ Ошибка открытия спора")

async def process_transaction_search(message: types.Message, state: FSMContext):
    """Process transaction search"""
    if message.text == "🔙 Назад":
        await state.clear()
        await message.answer("Главное меню:", reply_markup=get_main_menu('operator'))
        return

    search_query = message.text.strip()

    async with db.pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT user_id FROM users WHERE telegram_id = $1",
            message.from_user.id
        )

        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        # Убираем # и пробелы из номера заявки
        clean_query = search_query.replace('#', '').strip()

        # Поиск по номеру заявки
        deals = await conn.fetch(
            '''
            SELECT d.*, u.username as trader_name
            FROM deals d
            JOIN users u ON d.trader_id = u.user_id
            WHERE d.operator_id = $1 AND d.deal_number ILIKE $2 AND d.is_deleted = FALSE
            ORDER BY d.created_at DESC
            LIMIT 10
            ''',
            user['user_id'], f"%{clean_query}%"
        )

        if not deals:
            # Попробуем поиск по сумме
            try:
                amount = float(search_query)
                deals = await conn.fetch(
                    '''
                    SELECT d.*, u.username as trader_name
                    FROM deals d
                    JOIN users u ON d.trader_id = u.user_id
                    WHERE d.operator_id = $1 AND d.amount_rub = $2 AND d.is_deleted = FALSE
                    ORDER BY d.created_at DESC
                    LIMIT 10
                    ''',
                    user['user_id'], amount
                )
            except ValueError:
                pass

        if not deals:
            await message.answer("❌ Ничего не найдено")
            return

        for deal in deals:
            status_emoji = {
                'pending': '⏳',
                'confirmed': '✅',
                'expired': '❌',
                'disputed': '⚖️'
            }.get(deal['status'], '❓')

            deal_text = f"""
{status_emoji} Заявка #{deal['deal_number']}

💰 Сумма: {deal['amount_rub']} RUB
👤 Трейдер: {deal['trader_name']}
📅 Дата: {deal['created_at'].strftime('%d.%m.%Y %H:%M')}
📊 Статус: {deal['status']}
"""

            await message.answer(deal_text)

    await state.clear()
    await message.answer("🔍 Поиск завершен", reply_markup=get_main_menu('operator'))

def register_operator_handlers(router: Router):
    router.message.register(create_deal_start, F.text == "➕ Создать заявку")
    router.message.register(process_deal_amount, OperatorStates.waiting_deal_amount)
    router.message.register(show_operator_stats, F.text == "📊 Статистика")
    router.message.register(search_transactions_start, F.text == "🔍 Поиск транзакций")
    router.message.register(show_active_deals_operator, F.text == "📋 Активные заявки")
    router.message.register(process_transaction_search, OperatorStates.searching_transaction)
    
    router.callback_query.register(
        handle_dispute_callback,
        F.data.startswith('open_dispute_')
    )