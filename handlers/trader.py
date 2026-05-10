from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.auth_service import AuthService
from services.deal_service import DealService
from database.models import db
from keyboards.menus import get_main_menu, get_trader_details_menu, get_confirm_keyboard, get_back_button, get_dispute_keyboard
from config.settings import config

class TraderStates(StatesGroup):
    waiting_detail_name = State()
    waiting_detail_type = State()
    waiting_bank_name = State()
    waiting_full_name = State()
    waiting_card_number = State()
    waiting_phone = State()
    waiting_min_amount = State()
    waiting_max_amount = State()
    waiting_deposit_amount = State()

# ============== ПРОВЕРКА ДОСТУПА ==============
async def check_trader_access(telegram_id: int):
    """Проверка доступа трейдера к функционалу"""
    user_data = await AuthService.get_user_data(telegram_id)
    
    if not user_data or user_data['role'] != 'trader':
        return False, "❌ Доступ запрещен. Только трейдеры могут использовать эту функцию."
    
    if not user_data['insurance_deposit_confirmed']:
        return False, (
            f"❌ *ДОСТУП ЗАПРЕЩЕН!*\n\n"
            f"Для доступа к функционалу необходимо:\n"
            f"1. Пополнить страховой депозит\n"
            f"2. Дождаться подтверждения от владельца\n\n"
            f"💰 *Сумма:* {config.REQUIRED_INSURANCE_DEPOSIT} USDT\n"
            f"🏦 *Адрес:* `{config.OWNER_WALLET_ADDRESS}`\n"
            f"🔗 *Сеть:* USDT TRC-20\n\n"
            f"После перевода обратитесь к владельцу."
        )
    
    if not user_data.get('is_active', True):
        return False, "❌ Ваш аккаунт деактивирован. Обратитесь к владельцу для активации."
    
    return True, ""

# ============== ЛИЧНЫЙ КАБИНЕТ ==============
async def show_trader_dashboard(message: types.Message):
    """Show trader's personal dashboard"""
    user_data = await AuthService.get_user_data(message.from_user.id)
    
    if not user_data or user_data['role'] != 'trader':
        await message.answer("❌ Доступ запрещен")
        return
    
    async with db.pool.acquire() as conn:
        stats = await conn.fetchrow(
            '''
            SELECT 
                COUNT(*) as total_deals,
                SUM(amount_usdt) as total_usdt,
                SUM(amount_rub) as total_rub,
                COUNT(CASE WHEN status = 'confirmed' THEN 1 END) as confirmed_deals,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_deals
            FROM deals 
            WHERE trader_id = $1 AND is_deleted = FALSE
            ''',
            user_data['user_id']
        )
        
        active_details = await conn.fetchrow(
            "SELECT COUNT(*) as count FROM payment_details WHERE trader_id = $1 AND is_active = TRUE",
            user_data['user_id']
        )
        
        deposit_status = "✅ Подтвержден" if user_data['insurance_deposit_confirmed'] else "❌ Ожидает подтверждения"
        account_status = "✅ Активен" if user_data.get('is_active', True) else "❌ Деактивирован"
        
        dashboard = f"""
👤 *Личный кабинет трейдера*

📋 *Статус:*
• Депозит: {deposit_status}
• Аккаунт: {account_status}

💰 *Балансы:*
• Страховой депозит: {user_data['insurance_deposit']} USDT
• Рабочий депозит: {user_data['working_deposit']} USDT

📊 *Статистика:*
• Всего сделок: {stats['total_deals'] or 0}
• Подтверждено: {stats['confirmed_deals'] or 0}
• В ожидании: {stats['pending_deals'] or 0}
• Общая сумма: {stats['total_rub'] or 0:.2f} RUB

💳 *Реквизиты:*
• Активных: {active_details['count'] or 0}
"""
        
        if not user_data['insurance_deposit_confirmed']:
            dashboard += f"\n\n⚠️ *ДЛЯ НАЧАЛА РАБОТЫ:*\n"
            dashboard += f"1. Переведите {config.REQUIRED_INSURANCE_DEPOSIT} USDT\n"
            dashboard += f"2. Адрес: `{config.OWNER_WALLET_ADDRESS}`\n"
            dashboard += f"3. Сеть: USDT TRC-20\n"
            dashboard += f"4. Сообщите владельцу о переводе"
        
        await message.answer(dashboard, parse_mode="Markdown", reply_markup=get_main_menu('trader'))

# ============== УПРАВЛЕНИЕ РЕКВИЗИТАМИ ==============
async def trader_payment_details(message: types.Message):
    """Show trader's payment details menu"""
    has_access, error_msg = await check_trader_access(message.from_user.id)
    if not has_access:
        await message.answer(error_msg, parse_mode="Markdown")
        return
    
    await message.answer("💳 Управление реквизитами:", reply_markup=get_trader_details_menu())

async def add_detail_start(message: types.Message, state: FSMContext):
    """Начать добавление реквизита"""
    has_access, error_msg = await check_trader_access(message.from_user.id)
    if not has_access:
        await message.answer(error_msg, parse_mode="Markdown")
        return
    
    await state.set_state(TraderStates.waiting_detail_name.state)
    
    keyboard = types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="🔙 Назад")]], resize_keyboard=True)
    
    await message.answer(
        "🏷️ *Придумайте название для этого реквизита:*\n\n"
        "Например: 'Основная карта Тинькофф', 'СБП на Сбер', 'Зарплатная карта'",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def process_detail_name(message: types.Message, state: FSMContext):
    """Обработать название реквизита"""
    if message.text == "🔙 Назад":
        await state.clear()
        await trader_payment_details(message)
        return
    
    if len(message.text) < 3:
        await message.answer("❌ Название слишком короткое. Минимум 3 символа:")
        return
    
    await state.update_data(detail_name=message.text)
    
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="💳 Банковская карта")],
            [types.KeyboardButton(text="📱 СБП")],
            [types.KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )
    
    await state.set_state(TraderStates.waiting_detail_type.state)
    await message.answer("📋 *Выберите тип реквизита:*", parse_mode="Markdown", reply_markup=keyboard)

async def process_detail_type(message: types.Message, state: FSMContext):
    """Обработать выбор типа реквизита"""
    if message.text == "🔙 Назад":
        await state.set_state(TraderStates.waiting_detail_name.state)
        await message.answer("🏷️ Введите название реквизита:")
        return
    
    if message.text == "💳 Банковская карта":
        await state.update_data(detail_type='card')
    elif message.text == "📱 СБП":
        await state.update_data(detail_type='sbp')
    else:
        await message.answer("❌ Выберите тип из предложенных вариантов")
        return
    
    await state.set_state(TraderStates.waiting_bank_name.state)
    await message.answer("🏦 *Введите название банка:*", parse_mode="Markdown", reply_markup=get_back_button())

async def process_bank_name(message: types.Message, state: FSMContext):
    """Обработать название банка"""
    if message.text == "🔙 Назад":
        await state.set_state(TraderStates.waiting_detail_type.state)
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="💳 Банковская карта")],
                [types.KeyboardButton(text="📱 СБП")],
                [types.KeyboardButton(text="🔙 Назад")]
            ],
            resize_keyboard=True
        )
        await message.answer("📋 Выберите тип реквизита:", reply_markup=keyboard)
        return
    
    await state.update_data(bank_name=message.text)
    await state.set_state(TraderStates.waiting_full_name.state)
    await message.answer("👤 *Введите ФИО владельца:*", parse_mode="Markdown", reply_markup=get_back_button())

async def process_full_name(message: types.Message, state: FSMContext):
    """Обработать ФИО"""
    if message.text == "🔙 Назад":
        await state.set_state(TraderStates.waiting_bank_name.state)
        await message.answer("🏦 Введите название банка:")
        return
    
    words = message.text.split()
    if len(words) < 2:
        await message.answer("❌ Введите Фамилию и Имя (минимум 2 слова):")
        return
    
    await state.update_data(full_name=message.text)
    
    data = await state.get_data()
    
    if data.get('detail_type') == 'card':
        await state.set_state(TraderStates.waiting_card_number.state)
        await message.answer("💳 *Введите номер карты (16-19 цифр):*", parse_mode="Markdown", reply_markup=get_back_button())
    else:
        await state.set_state(TraderStates.waiting_phone.state)
        await message.answer("📱 *Введите номер телефона для СБП:*", parse_mode="Markdown", reply_markup=get_back_button())

async def process_card_number(message: types.Message, state: FSMContext):
    """Обработать номер карты"""
    if message.text == "🔙 Назад":
        await state.set_state(TraderStates.waiting_full_name.state)
        await message.answer("👤 Введите ФИО владельца:")
        return
    
    card_number = ''.join(filter(str.isdigit, message.text))
    
    if not card_number or len(card_number) < 16 or len(card_number) > 19:
        await message.answer("❌ Номер карты должен содержать 16-19 цифр:")
        return
    
    await state.update_data(card_number=card_number)
    await state.set_state(TraderStates.waiting_min_amount.state)
    await message.answer("💰 *Введите минимальную сумму (RUB):*", parse_mode="Markdown", reply_markup=get_back_button())

async def process_phone(message: types.Message, state: FSMContext):
    """Обработать номер телефона"""
    if message.text == "🔙 Назад":
        await state.set_state(TraderStates.waiting_full_name.state)
        await message.answer("👤 Введите ФИО владельца:")
        return
    
    phone = ''.join(filter(str.isdigit, message.text))
    
    if len(phone) not in [10, 11]:
        await message.answer("❌ Неверная длина номера. Должно быть 10-11 цифр:")
        return
    
    await state.update_data(phone_number=phone)
    await state.set_state(TraderStates.waiting_min_amount.state)
    await message.answer("💰 *Введите минимальную сумму (RUB):*", parse_mode="Markdown", reply_markup=get_back_button())

async def process_min_amount(message: types.Message, state: FSMContext):
    """Обработать минимальную сумму"""
    if message.text == "🔙 Назад":
        data = await state.get_data()
        if data.get('detail_type') == 'card':
            await state.set_state(TraderStates.waiting_card_number.state)
            await message.answer("💳 Введите номер карты:")
        else:
            await state.set_state(TraderStates.waiting_phone.state)
            await message.answer("📱 Введите номер телефона:")
        return
    
    try:
        min_amount = float(message.text)
        if min_amount < 0:
            raise ValueError
        
        await state.update_data(min_amount=min_amount)
        await state.set_state(TraderStates.waiting_max_amount.state)
        await message.answer(f"💰 *Введите максимальную сумму (больше {min_amount} RUB):*", parse_mode="Markdown", reply_markup=get_back_button())
    except ValueError:
        await message.answer("❌ Введите корректную сумму:")

async def process_max_amount(message: types.Message, state: FSMContext):
    """Обработать максимальную сумму и сохранить реквизит"""
    if message.text == "🔙 Назад":
        await state.set_state(TraderStates.waiting_min_amount.state)
        await message.answer("💰 Введите минимальную сумму:")
        return
    
    try:
        max_amount = float(message.text)
        data = await state.get_data()
        min_amount = data.get('min_amount', 0)
        
        if max_amount <= min_amount:
            await message.answer(f"❌ Максимальная сумма должна быть больше {min_amount} RUB:")
            return
        
        # Проверяем доступ
        has_access, error_msg = await check_trader_access(message.from_user.id)
        if not has_access:
            await message.answer(error_msg, parse_mode="Markdown")
            await state.clear()
            return
        
        # Сохраняем в базу данных
        async with db.pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT user_id FROM users WHERE telegram_id = $1",
                message.from_user.id
            )
            
            await conn.execute('''
                INSERT INTO payment_details (
                    trader_id, detail_name, detail_type, bank_name, full_name, card_number,
                    phone_number, min_amount, max_amount, is_active
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, TRUE)
            ''',
                user['user_id'],
                data.get('detail_name', 'Без названия'),
                data.get('detail_type', 'card'),
                data['bank_name'],
                data['full_name'],
                data.get('card_number'),
                data.get('phone_number'),
                min_amount,
                max_amount
            )
        
        await state.clear()
        await message.answer("✅ Реквизит успешно добавлен!", reply_markup=get_main_menu('trader'))
        
    except Exception as e:
        print(f"❌ Ошибка при сохранении реквизита: {e}")
        await message.answer("❌ Ошибка при сохранении реквизита.")
        await state.clear()

async def show_my_details(message: types.Message):
    """Показать реквизиты трейдера"""
    has_access, error_msg = await check_trader_access(message.from_user.id)
    if not has_access:
        await message.answer(error_msg, parse_mode="Markdown")
        return
    
    async with db.pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT user_id FROM users WHERE telegram_id = $1",
            message.from_user.id
        )
        
        details = await conn.fetch('''
            SELECT * FROM payment_details 
            WHERE trader_id = $1
            ORDER BY created_at DESC
        ''', user['user_id'])
        
        if not details:
            await message.answer("📭 У вас нет добавленных реквизитов")
            return
        
        for detail in details:
            status = "✅" if detail['is_active'] else "❌"
            detail_name = detail.get('detail_name', 'Без названия')
            detail_text = f"""
{status} {detail_name}
🏦 Банк: {detail['bank_name']}
👤 ФИО: {detail['full_name']}
"""
            if detail['card_number']:
                card_num = detail['card_number']
                # Показываем полный номер карты
                detail_text += f"💳 Карта: {card_num}\n"
            if detail['phone_number']:
                detail_text += f"📱 СБП: {detail['phone_number']}\n"
            
            detail_text += f"💰 Лимиты: {detail['min_amount']} - {detail['max_amount']} RUB\n"
            detail_text += f"📅 Добавлен: {detail['created_at'].strftime('%d.%m.%Y')}\n"
            detail_text += f"⚡ Статус: {'Активен ✅' if detail['is_active'] else 'Не активен ❌'}"
            
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="🔴 Выключить" if detail['is_active'] else "🟢 Включить",
                        callback_data=f"toggle_detail_{detail['detail_id']}"
                    ),
                    types.InlineKeyboardButton(
                        text="❌ Удалить",
                        callback_data=f"delete_detail_{detail['detail_id']}"
                    )
                ]
            ])
            
            await message.answer(detail_text, reply_markup=keyboard)

# ============== АКТИВНЫЕ ЗАЯВКИ ==============
async def show_active_deals(message: types.Message):
    """Show trader's active deals"""
    has_access, error_msg = await check_trader_access(message.from_user.id)
    if not has_access:
        await message.answer(error_msg, parse_mode="Markdown")
        return
    
    async with db.pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT user_id FROM users WHERE telegram_id = $1",
            message.from_user.id
        )
        
        deals = await conn.fetch(
            '''
            SELECT d.*, pd.bank_name, pd.full_name, pd.card_number, pd.phone_number, pd.detail_name
            FROM deals d
            LEFT JOIN payment_details pd ON d.payment_detail_id = pd.detail_id
            WHERE d.trader_id = $1 AND d.status = 'pending' AND d.is_deleted = FALSE
            ORDER BY d.created_at DESC
            ''',
            user['user_id']
        )
        
        if not deals:
            await message.answer("📭 Активных заявок нет")
            return
        
        for deal in deals:
            detail_name = deal.get('detail_name', 'Без названия')
            deal_text = f"""
📋 Заявка #{deal['deal_number']}

💰 Сумма: {deal['amount_rub']} RUB / {deal['amount_usdt']} USDT
🕐 Создана: {deal['created_at'].strftime('%d.%m.%Y %H:%M')}
⏳ Истекает: {deal['expires_at'].strftime('%d.%m.%Y %H:%M')}

💳 Реквизит: {detail_name}
• Банк: {deal['bank_name']}
• ФИО: {deal['full_name']}
"""
            if deal['card_number']:
                card_num = deal['card_number']
                # Показываем полный номер карты
                deal_text += f"• Карта: {card_num}\n"
            if deal['phone_number']:
                deal_text += f"• СБП: {deal['phone_number']}\n"
            
            await message.answer(deal_text, reply_markup=get_confirm_keyboard(deal['deal_id']))

# ============== МОИ СДЕЛКИ ==============
async def show_my_deals(message: types.Message):
    """Show all trader's deals"""
    has_access, error_msg = await check_trader_access(message.from_user.id)
    if not has_access:
        await message.answer(error_msg, parse_mode="Markdown")
        return
    
    async with db.pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT user_id FROM users WHERE telegram_id = $1",
            message.from_user.id
        )
        
        deals = await conn.fetch(
            '''
            SELECT d.*, pd.bank_name, pd.full_name
            FROM deals d
            LEFT JOIN payment_details pd ON d.payment_detail_id = pd.detail_id
            WHERE d.trader_id = $1 AND d.is_deleted = FALSE
            ORDER BY d.created_at DESC
            LIMIT 20
            ''',
            user['user_id']
        )
        
        if not deals:
            await message.answer("📭 Сделок нет")
            return
        
        for deal in deals:
            status_emoji = {
                'pending': '⏳',
                'confirmed': '✅',
                'expired': '❌',
                'disputed': '⚖️',
                'rejected': '🚫'
            }.get(deal['status'], '❓')
            
            deal_text = f"""
{status_emoji} Заявка #{deal['deal_number']}

💰 Сумма: {deal['amount_rub']} RUB / {deal['amount_usdt']} USDT
📅 Дата: {deal['created_at'].strftime('%d.%m.%Y %H:%M')}
📊 Статус: {deal['status']}
"""
            if deal['bank_name']:
                deal_text += f"\n🏦 Банк: {deal['bank_name']}"
            
            await message.answer(deal_text)

# ============== ПОПОЛНЕНИЕ РАБОЧЕГО ДЕПОЗИТА ==============
async def top_up_deposit_start(message: types.Message, state: FSMContext):
    """Начать пополнение рабочего депозита"""
    has_access, error_msg = await check_trader_access(message.from_user.id)
    if not has_access:
        await message.answer(error_msg, parse_mode="Markdown")
        return

    await state.set_state(TraderStates.waiting_deposit_amount.state)
    await message.answer(
        f"💰 Введите сумму пополнения рабочего депозита в USDT:\n\n"
        f"🏦 Адрес для перевода: `{config.OWNER_WALLET_ADDRESS}`\n"
        f"🔗 Сеть: USDT TRC-20\n\n"
        f"После перевода введите сумму для подтверждения.",
        parse_mode="Markdown",
        reply_markup=get_back_button()
    )

async def process_deposit_amount(message: types.Message, state: FSMContext):
    """Обработать сумму пополнения"""
    if message.text == "🔙 Назад":
        await state.clear()
        await message.answer("Главное меню:", reply_markup=get_main_menu('trader'))
        return

    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError

        async with db.pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT user_id, username FROM users WHERE telegram_id = $1",
                message.from_user.id
            )

            if not user:
                await message.answer("❌ Пользователь не найден")
                return

            # Обновляем рабочий депозит
            await conn.execute(
                '''
                UPDATE users
                SET working_deposit = working_deposit + $1
                WHERE user_id = $2
                ''',
                amount, user['user_id']
            )

        await state.clear()
        await message.answer(
            f"✅ Запрос на пополнение рабочего депозита на {amount} USDT отправлен!\n\n"
            f"Ожидайте подтверждения от владельца.",
            reply_markup=get_main_menu('trader')
        )

    except ValueError:
        await message.answer("❌ Введите корректную сумму (число больше 0):")

# ============== СПОРЫ ==============
async def show_disputes_trader(message: types.Message):
    """Show trader's disputes"""
    has_access, error_msg = await check_trader_access(message.from_user.id)
    if not has_access:
        await message.answer(error_msg, parse_mode="Markdown")
        return
    
    async with db.pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT user_id FROM users WHERE telegram_id = $1",
            message.from_user.id
        )
        
        disputes = await conn.fetch(
            '''
            SELECT d.*, u.username as operator_name
            FROM deals d
            JOIN users u ON d.operator_id = u.user_id
            WHERE d.trader_id = $1 AND d.dispute_opened = TRUE AND d.is_deleted = FALSE
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
👤 Оператор: {dispute['operator_name']}
🕐 Создан: {dispute['created_at'].strftime('%d.%m.%Y %H:%M')}
"""
            keyboard = get_dispute_keyboard(dispute['deal_id'])
            await message.answer(dispute_text, reply_markup=keyboard)

# ============== ОБРАБОТЧИКИ CALLBACK ==============
async def handle_deal_confirmation(callback_query: types.CallbackQuery):
    """Handle deal confirmation from trader"""
    try:
        data = callback_query.data
        
        # Проверяем, что это callback для подтверждения/отклонения сделки, а не депозита
        if not data.startswith(('confirm_', 'reject_')):
            return
        
        # Игнорируем callback для подтверждения депозита (это обрабатывается в owner.py)
        if 'deposit' in data:
            return
            
        if '_' not in data:
            await callback_query.answer("❌ Неверный формат запроса")
            return
            
        parts = data.split('_')
        if len(parts) < 2:
            await callback_query.answer("❌ Неверный формат запроса")
            return
            
        action = parts[0]
        deal_id = int(parts[1])
        
        has_access, error_msg = await check_trader_access(callback_query.from_user.id)
        if not has_access:
            await callback_query.answer("❌ Доступ запрещен")
            return
        
        async with db.pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT user_id FROM users WHERE telegram_id = $1",
                callback_query.from_user.id
            )
            
            if not user:
                await callback_query.answer("❌ Пользователь не найден")
                return
            
            if action == 'confirm':
                deal = await DealService.confirm_deal(deal_id, user['user_id'])
                if deal:
                    await callback_query.message.edit_text(
                        f"✅ Заявка #{deal['deal_number']} подтверждена!"
                    )
                    await callback_query.answer("✅ Заявка подтверждена!")
                else:
                    await callback_query.answer("❌ Заявка не найдена или уже обработана")
            elif action == 'reject':
                await conn.execute(
                    '''
                    UPDATE deals 
                    SET status = 'rejected',
                        dispute_resolved = TRUE,
                        resolution = 'rejected'
                    WHERE deal_id = $1 AND trader_id = $2 AND is_deleted = FALSE
                    ''',
                    deal_id, user['user_id']
                )
                await callback_query.message.edit_text("❌ Заявка отклонена")
                await callback_query.answer("❌ Заявка отклонена")
                
    except Exception as e:
        print(f"Error in handle_deal_confirmation: {e}")
        await callback_query.answer("❌ Ошибка обработки")

async def handle_detail_toggle(callback_query: types.CallbackQuery):
    """Toggle payment detail status"""
    try:
        if '_' not in callback_query.data or len(callback_query.data.split('_')) < 3:
            await callback_query.answer("❌ Неверный формат запроса")
            return
            
        detail_id = int(callback_query.data.split('_')[2])
        
        has_access, error_msg = await check_trader_access(callback_query.from_user.id)
        if not has_access:
            await callback_query.answer("❌ Доступ запрещен")
            return
        
        async with db.pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT user_id FROM users WHERE telegram_id = $1",
                callback_query.from_user.id
            )
            
            if not user:
                await callback_query.answer("❌ Пользователь не найден")
                return
            
            detail = await conn.fetchrow(
                "SELECT is_active FROM payment_details WHERE detail_id = $1 AND trader_id = $2",
                detail_id, user['user_id']
            )
            
            if not detail:
                await callback_query.answer("❌ Реквизит не найден")
                return
            
            new_status = not detail['is_active']
            
            await conn.execute(
                "UPDATE payment_details SET is_active = $1 WHERE detail_id = $2",
                new_status, detail_id
            )
            
            await callback_query.answer(f"✅ Реквизит {'включен' if new_status else 'выключен'}")
            
            message_text = callback_query.message.text
            if new_status:
                updated_text = message_text.replace("Не активен ❌", "Активен ✅")
                updated_text = updated_text.replace("🔴", "🟢")
            else:
                updated_text = message_text.replace("Активен ✅", "Не активен ❌")
                updated_text = updated_text.replace("🟢", "🔴")
            
            await callback_query.message.edit_text(updated_text)
            
    except Exception as e:
        print(f"Error in handle_detail_toggle: {e}")
        await callback_query.answer("❌ Ошибка")

async def handle_detail_delete(callback_query: types.CallbackQuery):
    """Delete payment detail"""
    try:
        if '_' not in callback_query.data or len(callback_query.data.split('_')) < 3:
            await callback_query.answer("❌ Неверный формат запроса")
            return
            
        detail_id = int(callback_query.data.split('_')[2])
        
        has_access, error_msg = await check_trader_access(callback_query.from_user.id)
        if not has_access:
            await callback_query.answer("❌ Доступ запрещен")
            return
        
        async with db.pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT user_id FROM users WHERE telegram_id = $1",
                callback_query.from_user.id
            )
            
            if not user:
                await callback_query.answer("❌ Пользователь не найден")
                return
            
            detail = await conn.fetchrow(
                "SELECT * FROM payment_details WHERE detail_id = $1 AND trader_id = $2",
                detail_id, user['user_id']
            )
            
            if not detail:
                await callback_query.answer("❌ Реквизит не найден")
                return
            
            active_deals = await conn.fetchrow(
                '''
                SELECT COUNT(*) as count FROM deals 
                WHERE payment_detail_id = $1 
                AND status = 'pending' 
                AND is_deleted = FALSE
                ''',
                detail_id
            )
            
            if active_deals['count'] > 0:
                await callback_query.answer("❌ Нельзя удалить реквизит с активными заявками")
                return
            
            await conn.execute(
                "DELETE FROM payment_details WHERE detail_id = $1 AND trader_id = $2",
                detail_id, user['user_id']
            )
            
            await callback_query.answer("✅ Реквизит удален")
            await callback_query.message.edit_text("❌ Реквизит удален")
            
    except Exception as e:
        print(f"Error in handle_detail_delete: {e}")
        await callback_query.answer("❌ Ошибка")

async def handle_dispute_trader(callback_query: types.CallbackQuery):
    """Handle trader's dispute response"""
    try:
        data = callback_query.data
        if not data.startswith('dispute_'):
            await callback_query.answer("❌ Неверный формат запроса")
            return

        parts = data.split('_')
        if len(parts) < 3:
            await callback_query.answer("❌ Неверный формат запроса")
            return

        action = parts[1]
        deal_id = int(parts[2])

        has_access, error_msg = await check_trader_access(callback_query.from_user.id)
        if not has_access:
            await callback_query.answer("❌ Доступ запрещен")
            return

        async with db.pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT user_id FROM users WHERE telegram_id = $1",
                callback_query.from_user.id
            )

            if not user:
                await callback_query.answer("❌ Пользователь не найден")
                return

            if action == 'confirm':
                await DealService.resolve_dispute(deal_id, 'confirmed', user['user_id'])
                await callback_query.answer("✅ Спор разрешен в пользу оператора")
                await callback_query.message.edit_text(
                    f"{callback_query.message.text}\n\n✅ Подтверждено"
                )
            elif action == 'reject':
                await DealService.resolve_dispute(deal_id, 'rejected', user['user_id'])
                await callback_query.answer("❌ Спор отклонен")
                await callback_query.message.edit_text(
                    f"{callback_query.message.text}\n\n❌ Отклонено"
                )

    except Exception as e:
        print(f"Error in handle_dispute_trader: {e}")
        await callback_query.answer("❌ Ошибка")

# ============== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ ==============
def register_trader_handlers(router: Router):
    # Основные команды
    router.message.register(show_trader_dashboard, F.text == "👤 Личный кабинет")
    router.message.register(trader_payment_details, F.text == "💳 Мои реквизиты")
    router.message.register(add_detail_start, F.text == "➕ Добавить реквизит")
    router.message.register(show_my_details, F.text == "📋 Список реквизитов")
    router.message.register(show_active_deals, F.text == "⚡ Активные заявки")
    router.message.register(show_my_deals, F.text == "📊 Мои сделки")
    router.message.register(show_disputes_trader, F.text == "⚖️ Споры")
    router.message.register(top_up_deposit_start, F.text == "💰 Пополнить депозит")
    
    # State handlers для добавления реквизитов
    router.message.register(process_detail_name, TraderStates.waiting_detail_name)
    router.message.register(process_detail_type, TraderStates.waiting_detail_type)
    router.message.register(process_bank_name, TraderStates.waiting_bank_name)
    router.message.register(process_full_name, TraderStates.waiting_full_name)
    router.message.register(process_card_number, TraderStates.waiting_card_number)
    router.message.register(process_phone, TraderStates.waiting_phone)
    router.message.register(process_min_amount, TraderStates.waiting_min_amount)
    router.message.register(process_max_amount, TraderStates.waiting_max_amount)
    router.message.register(process_deposit_amount, TraderStates.waiting_deposit_amount)
    
    # Callback handlers
    router.callback_query.register(
        handle_deal_confirmation, 
        F.data.startswith(('confirm_', 'reject_')) & ~F.data.contains('deposit') & ~F.data.contains('dispute')
    )
    router.callback_query.register(
        handle_detail_toggle,
        F.data.startswith('toggle_detail_')
    )
    router.callback_query.register(
        handle_detail_delete,
        F.data.startswith('delete_detail_')
    )
    router.callback_query.register(
        handle_dispute_trader,
        F.data.startswith('dispute_')
    )
