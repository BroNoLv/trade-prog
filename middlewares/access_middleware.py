from aiogram import types
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher.handler import CancelHandler
from services.auth_service import AuthService

class AccessMiddleware(BaseMiddleware):
    """Middleware для проверки доступа трейдера к функционалу"""
    
    async def on_pre_process_message(self, message: types.Message, data: dict):
        # Пропускаем системные команды
        if message.text in ['/start', '/logout'] or message.text.startswith('/'):
            return
        
        # Разрешаем кнопку "Назад" всегда
        if message.text == "🔙 Назад":
            return
        
        # Получаем данные пользователя
        user_data = await AuthService.get_user_data(message.from_user.id)
        
        if not user_data:
            return
        
        # Проверяем доступ только для трейдеров
        if user_data['role'] == 'trader':
            # Разрешаем доступ к личному кабинету и выходу всегда
            allowed_for_all = [
                "👤 Личный кабинет",
                "🚪 Выйти"
            ]
            
            if message.text in allowed_for_all:
                return
            
            # Проверяем доступ к остальному функционалу
            if not user_data['insurance_deposit_confirmed']:
                await message.answer(
                    "❌ *ДОСТУП ЗАПРЕЩЕН!*\n\n"
                    "Для доступа к функционалу необходимо подтверждение страхового депозита.\n"
                    "Обратитесь к владельцу после пополнения депозита.",
                    parse_mode="Markdown"
                )
                raise CancelHandler()
            
            if not user_data.get('is_active', True):
                await message.answer(
                    "❌ Ваш аккаунт деактивирован.\n"
                    "Обратитесь к владельцу для активации."
                )
                raise CancelHandler()