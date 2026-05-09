from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu(role: str, deposit_confirmed: bool = True):
    """Get main menu based on user role"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)

    if role == "trader":
        if not deposit_confirmed:
            # Limited menu for traders without confirmed deposit
            keyboard.add(KeyboardButton("� Пополнить депозит"))
            keyboard.add(KeyboardButton("�🚪 Выйти"))
        else:
            keyboard.add(KeyboardButton("👤 Личный кабинет"))
            keyboard.add(KeyboardButton("💳 Мои реквизиты"))
            keyboard.add(KeyboardButton("📊 Мои сделки"))
            keyboard.add(KeyboardButton("⚡ Активные заявки"))
            keyboard.add(KeyboardButton("⚖️ Споры"))
            keyboard.add(KeyboardButton("💰 Пополнить депозит"))
    
    elif role == "operator":
        keyboard.add(KeyboardButton("➕ Создать заявку"))
        keyboard.add(KeyboardButton("📋 Активные заявки"))
        keyboard.add(KeyboardButton("📊 Статистика"))
        keyboard.add(KeyboardButton("🔍 Поиск транзакций"))
    
    elif role == "owner":
        keyboard.add(KeyboardButton("📈 Общая статистика"))
        keyboard.add(KeyboardButton("🔑 Управление токенами"))
        keyboard.add(KeyboardButton("💱 Курс USDT"))
        keyboard.add(KeyboardButton("👥 Управление пользователями"))
        keyboard.add(KeyboardButton("🔄 Автообновление курса"))
        keyboard.add(KeyboardButton("🗑️ Удалить сделку"))
    
    keyboard.add(KeyboardButton("🚪 Выйти"))
    return keyboard

def get_trader_details_menu():
    """Menu for trader's payment details"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("➕ Добавить реквизит"))
    keyboard.add(KeyboardButton("📋 Список реквизитов"))
    keyboard.add(KeyboardButton("🔙 Назад"))
    return keyboard

def get_confirm_keyboard(deal_id: int):
    """Inline keyboard for deal confirmation"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{deal_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{deal_id}")
    )
    return keyboard

def get_dispute_keyboard(deal_id: int):
    """Inline keyboard for disputes"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"dispute_confirm_{deal_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"dispute_reject_{deal_id}")
    )
    return keyboard

def get_owner_tokens_menu():
    """Owner's token management menu"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("🔐 Создать токен"))
    keyboard.add(KeyboardButton("📋 Список токенов"))
    keyboard.add(KeyboardButton("❌ Деактивировать токен"))
    keyboard.add(KeyboardButton("🔙 Назад"))
    return keyboard

def get_stats_period_menu():
    """Menu for selecting statistics period"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("📊 Общая статистика"))
    return keyboard

def get_stats_filter_menu():
    """Menu for statistics filtering"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(KeyboardButton("📅 По дате"))
    keyboard.add(KeyboardButton("👤 По трейдеру"))
    keyboard.add(KeyboardButton("👨‍💼 По оператору"))
    keyboard.add(KeyboardButton("💰 По сумме"))
    keyboard.add(KeyboardButton("🔙 Назад"))
    return keyboard

def get_back_button():
    """Simple back button"""
    return ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("🔙 Назад"))