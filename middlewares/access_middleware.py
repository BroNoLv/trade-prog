from aiogram import types
from aiogram.types import Message
from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramAPIError
from services.auth_service import AuthService
from handlers.common import AuthStates

class AccessMiddleware(BaseMiddleware):
    """Middleware для проверки доступа трейдера к функционалу"""
    
    async def __call__(self, handler, event: Message, data: dict):
        # Пропускаем системные команды
        if event.text in ['/start', '/logout'] or event.text.startswith('/'):
            return await handler(event, data)
        
        # Разрешаем кнопку "Назад" всегда
        if event.text == "🔙 Назад":
            return await handler(event, data)
        
        # Пропускаем ввод токена (пользователь еще не авторизован)
        # Проверяем, находится ли пользователь в состоянии ожидания токена
        # Это позволяет вводить токен даже если пользователь уже существует в БД
        from aiogram.fsm.context import FSMContext
        state = data.get('state')
        if state:
            current_state = await state.get_state()
            if current_state == AuthStates.waiting_for_token.state:
                return await handler(event, data)
        
        # Получаем данные пользователя
        user_data = await AuthService.get_user_data(event.from_user.id)
        
        if not user_data:
            return await handler(event, data)
        
        # Проверяем доступ только для трейдеров
        if user_data['role'] == 'trader':
            # Разрешаем доступ к личному кабинету и выходу всегда
            allowed_for_all = [
                "👤 Личный кабинет",
                "🚪 Выйти"
            ]
            
            if event.text in allowed_for_all:
                return await handler(event, data)
            
            # Проверяем доступ к остальному функционалу
            if not user_data['insurance_deposit_confirmed']:
                await event.answer(
                    "❌ *ДОСТУП ЗАПРЕЩЕН!*\n\n"
                    "Для доступа к функционалу необходимо подтверждение страхового депозита.\n"
                    "Обратитесь к владельцу после пополнения депозита.",
                    parse_mode="Markdown"
                )
                return
            
            if not user_data.get('is_active', True):
                await event.answer(
                    "❌ Ваш аккаунт деактивирован.\n"
                    "Обратитесь к владельцу для активации."
                )
                return
        
        return await handler(event, data)