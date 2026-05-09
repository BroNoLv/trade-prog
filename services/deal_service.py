from datetime import datetime, timedelta
import random
import traceback
from database.models import db
from config.settings import config
from services.exchange_service import ExchangeService

class DealService:
    @staticmethod
    async def check_expired_deals():
        """Check and expire old deals"""
        async with db.pool.acquire() as conn:
            try:
                # Проверяем существование колонки is_deleted
                table_info = await conn.fetch('''
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'deals' AND column_name = 'is_deleted'
                ''')
                
                if table_info:
                    # Колонка существует
                    expired = await conn.fetch('''
                        UPDATE deals 
                        SET status = 'expired'
                        WHERE status = 'pending' 
                        AND expires_at < NOW()
                        AND (is_deleted = FALSE OR is_deleted IS NULL)
                        RETURNING *
                    ''')
                else:
                    # Колонки нет, используем старый запрос
                    expired = await conn.fetch('''
                        UPDATE deals 
                        SET status = 'expired'
                        WHERE status = 'pending' 
                        AND expires_at < NOW()
                        RETURNING *
                    ''')
                
                return [dict(d) for d in expired]
            except Exception as e:
                print(f"❌ Ошибка в check_expired_deals: {e}")
                return []
    
    @staticmethod
    async def delete_deal(deal_id: int):
        """Soft delete deal (mark as deleted)"""
        async with db.pool.acquire() as conn:
            try:
                # Проверяем существование колонки
                table_info = await conn.fetch('''
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'deals' AND column_name = 'is_deleted'
                ''')
                
                if table_info:
                    await conn.execute(
                        "UPDATE deals SET is_deleted = TRUE WHERE deal_id = $1",
                        deal_id
                    )
                else:
                    # Если колонки нет, просто удаляем
                    await conn.execute(
                        "DELETE FROM deals WHERE deal_id = $1",
                        deal_id
                    )
            except Exception as e:
                print(f"❌ Ошибка при удалении сделки: {e}")

    @staticmethod
    async def create_deal(operator_id: int, amount_rub: float):
        """Create new deal with available payment detail"""
        print(f"\n🔍 Создание сделки для суммы: {amount_rub} RUB")
        
        async with db.pool.acquire() as conn:
            try:
                # Ищем подходящий реквизит с учетом всех условий
                # Убрали проверку на наличие pending сделок для того же реквизита
                detail = await conn.fetchrow('''
                    SELECT 
                        pd.*,
                        u.telegram_id as trader_telegram_id,
                        u.username,
                        u.insurance_deposit_confirmed,
                        u.is_active as trader_active
                    FROM payment_details pd
                    JOIN users u ON pd.trader_id = u.user_id
                    WHERE pd.is_active = TRUE 
                    AND $1 BETWEEN pd.min_amount AND pd.max_amount
                    AND u.role = 'trader'
                    AND u.insurance_deposit_confirmed = TRUE
                    AND u.is_active = TRUE
                    ORDER BY RANDOM()
                    LIMIT 1
                ''', amount_rub)
                
                if not detail:
                    print(f"❌ Не найдено подходящих реквизитов для суммы {amount_rub} RUB")
                    return None, "No suitable payment details found"
                
                # Получаем текущий курс
                rate = await ExchangeService.get_current_rate()
                amount_usdt = round(amount_rub / rate, 2)
                
                # Генерируем номер заявки
                deal_number = f"D{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"
                
                # Рассчитываем время истечения
                expires_at = datetime.now() + timedelta(seconds=config.PAYMENT_TIMEOUT)
                
                # Создаем сделку
                deal = await conn.fetchrow('''
                    INSERT INTO deals (
                        deal_number, operator_id, trader_id, payment_detail_id,
                        amount_rub, amount_usdt, expires_at, status
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending')
                    RETURNING *
                ''', deal_number, operator_id, detail['trader_id'], detail['detail_id'],
                    amount_rub, amount_usdt, expires_at)
                
                print(f"✅ Создана сделка #{deal['deal_number']}")
                return dict(deal), dict(detail)
                
            except Exception as e:
                print(f"❌ Ошибка при создании сделки: {e}")
                traceback.print_exc()
                return None, f"Error creating deal: {str(e)}"
    
    @staticmethod
    async def get_deal_by_number(deal_number: str):
        """Get deal by number"""
        async with db.pool.acquire() as conn:
            deal = await conn.fetchrow(
                "SELECT * FROM deals WHERE deal_number = $1 AND is_deleted = FALSE",
                deal_number
            )
            return dict(deal) if deal else None
    
    @staticmethod
    async def confirm_deal(deal_id: int, trader_id: int):
        """Confirm deal by trader"""
        async with db.pool.acquire() as conn:
            deal = await conn.fetchrow(
                '''
                UPDATE deals 
                SET status = 'confirmed', 
                    confirmed_at = NOW(),
                    dispute_resolved = TRUE,
                    resolution = 'confirmed'
                WHERE deal_id = $1 
                AND trader_id = $2 
                AND status = 'pending'
                AND is_deleted = FALSE
                RETURNING *
                ''',
                deal_id, trader_id
            )
            return dict(deal) if deal else None
    
    @staticmethod
    async def open_dispute(deal_id: int, operator_id: int, reason: str = None):
        """Open dispute for deal"""
        async with db.pool.acquire() as conn:
            # Update deal
            await conn.execute(
                '''
                UPDATE deals 
                SET dispute_opened = TRUE,
                    status = 'disputed'
                WHERE deal_id = $1 AND is_deleted = FALSE
                ''',
                deal_id
            )
            
            # Create dispute record
            await conn.execute(
                '''
                INSERT INTO disputes (deal_id, opened_by, reason)
                VALUES ($1, $2, $3)
                ''',
                deal_id, operator_id, reason
            )
            
            return True
    
    @staticmethod
    async def resolve_dispute(deal_id: int, resolution: str, resolved_by: int):
        """Resolve dispute"""
        async with db.pool.acquire() as conn:
            await conn.execute(
                '''
                UPDATE deals 
                SET dispute_resolved = TRUE,
                    status = $2,
                    resolution = $3
                WHERE deal_id = $1 AND is_deleted = FALSE
                ''',
                deal_id, 'confirmed' if resolution == 'confirmed' else 'rejected', resolution
            )
            
            await conn.execute(
                '''
                UPDATE disputes 
                SET resolved_by = $2,
                    resolved_at = NOW(),
                    resolution = $3
                WHERE deal_id = $1
                ''',
                deal_id, resolved_by, resolution
            )
    
    @staticmethod
    async def get_deals_by_period(start_date: datetime = None, end_date: datetime = None):
        """Get deals within time period"""
        async with db.pool.acquire() as conn:
            query = '''
                SELECT d.*, 
                       u1.username as operator_name,
                       u2.username as trader_name,
                       pd.bank_name
                FROM deals d
                LEFT JOIN users u1 ON d.operator_id = u1.user_id
                LEFT JOIN users u2 ON d.trader_id = u2.user_id
                LEFT JOIN payment_details pd ON d.payment_detail_id = pd.detail_id
                WHERE d.is_deleted = FALSE
            '''
            
            params = []
            if start_date:
                query += " AND d.created_at >= $1"
                params.append(start_date)
            if end_date:
                query += " AND d.created_at <= $" + str(len(params) + 1)
                params.append(end_date)
            
            query += " ORDER BY d.created_at DESC"
            
            deals = await conn.fetch(query, *params)
            return [dict(d) for d in deals]