from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu(role: str, deposit_confirmed: bool = True):
    """Get main menu based on user role"""
    buttons = []

    if role == "trader":
        if not deposit_confirmed:
            # Limited menu for traders without confirmed deposit
            buttons = [
                [KeyboardButton(text="💰 Пополнить депозит")],
                [KeyboardButton(text="🚪 Выйти")]
            ]
        else:
            buttons = [
                [KeyboardButton(text="👤 Личный кабинет")],
                [KeyboardButton(text="💳 Мои реквизиты")],
                [KeyboardButton(text="📊 Мои сделки")],
                [KeyboardButton(text="⚡ Активные заявки")],
                [KeyboardButton(text="⚖️ Споры")],
                [KeyboardButton(text="💰 Пополнить депозит")],
                [KeyboardButton(text="🚪 Выйти")]
            ]
    
    elif role == "operator":
        buttons = [
            [KeyboardButton(text="➕ Создать заявку")],
            [KeyboardButton(text="📋 Активные заявки")],
            [KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="🔍 Поиск транзакций")],
            [KeyboardButton(text="🚪 Выйти")]
        ]
    
    elif role == "owner":
        buttons = [
            [KeyboardButton(text="📈 Общая статистика")],
            [KeyboardButton(text="🔑 Управление токенами")],
            [KeyboardButton(text="💱 Курс USDT")],
            [KeyboardButton(text="👥 Управление пользователями")],
            [KeyboardButton(text="🔄 Автообновление курса")],
            [KeyboardButton(text="🗑️ Удалить сделку")],
            [KeyboardButton(text="🚪 Выйти")]
        ]
    else:
        buttons = [[KeyboardButton(text="🚪 Выйти")]]
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_trader_details_menu():
    """Menu for trader's payment details"""
    buttons = [
        [KeyboardButton(text="➕ Добавить реквизит")],
        [KeyboardButton(text="📋 Список реквизитов")],
        [KeyboardButton(text="🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_confirm_keyboard(deal_id: int):
    """Inline keyboard for deal confirmation"""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{deal_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{deal_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_dispute_keyboard(deal_id: int):
    """Inline keyboard for disputes"""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"dispute_confirm_{deal_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"dispute_reject_{deal_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_owner_tokens_menu():
    """Owner's token management menu"""
    buttons = [
        [KeyboardButton(text="🔐 Создать токен")],
        [KeyboardButton(text="📋 Список токенов")],
        [KeyboardButton(text="❌ Деактивировать токен")],
        [KeyboardButton(text="🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_stats_period_menu():
    """Menu for selecting statistics period"""
    buttons = [
        [KeyboardButton(text="📊 Общая статистика")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_stats_filter_menu():
    """Menu for statistics filtering"""
    buttons = [
        [KeyboardButton(text="📅 По дате"), KeyboardButton(text="👤 По трейдеру")],
        [KeyboardButton(text="👨‍💼 По оператору"), KeyboardButton(text="💰 По сумме")],
        [KeyboardButton(text="🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_back_button():
    """Simple back button"""
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔙 Назад")]], resize_keyboard=True)