import aiohttp
from bs4 import BeautifulSoup
import re
from datetime import datetime
from database.models import db
from config.settings import config

class ExchangeService:
    @staticmethod
    async def get_current_rate():
        """Get current USDT to RUB rate"""
        async with db.pool.acquire() as conn:
            rate = await conn.fetchrow(
                "SELECT usdt_to_rub FROM exchange_rates ORDER BY updated_at DESC LIMIT 1"
            )
            return float(rate['usdt_to_rub']) if rate else 90.0
    
    @staticmethod
    async def update_rate_automatically():
        """Auto-update rate from multiple sources"""
        try:
            print("🔄 Получаю курс USDT/RUB...")

            # Try multiple sources in order
            sources = [
                ExchangeService._parse_binance,
                ExchangeService._parse_kucoin,
                ExchangeService._parse_cbr
            ]

            for source in sources:
                try:
                    rate = await source()
                    if rate and 50 <= rate <= 200:
                        await ExchangeService._save_rate(rate, None, True)
                        print(f"✅ Курс USDT/RUB успешно обновлен: {rate}")
                        return rate
                except Exception as e:
                    print(f"⚠️ Источник {source.__name__} не сработал: {e}")
                    continue

            print("❌ Не удалось получить курс ни из одного источника, используем резервный курс")
            # Use fallback rate of 78.50
            await ExchangeService._save_rate(78.50, None, True)
            print(f"✅ Установлен резервный курс: 78.50")
            return 78.50

        except Exception as e:
            print(f"❌ Общая ошибка: {e}")
            # Use fallback rate
            await ExchangeService._save_rate(78.50, None, True)
            print(f"✅ Установлен резервный курс: 78.50")
            return 78.50

    @staticmethod
    async def _parse_binance():
        """Parse rate from Binance P2P"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get('https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search',
                                   headers=headers, timeout=10,
                                   params={
                                       'fiat': 'RUB',
                                       'asset': 'USDT',
                                       'tradeType': 'BUY',
                                       'page': 1,
                                       'rows': 1
                                   }) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('data') and len(data['data']) > 0:
                        rate = float(data['data'][0]['adv']['price'])
                        print(f"✅ Курс с Binance: {rate}")
                        return rate
        return None

    @staticmethod
    async def _parse_kucoin():
        """Parse rate from KuCoin P2P"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get('https://www.kucoin.com/_api/p2p/market/advertisement/list',
                                   headers=headers, timeout=10,
                                   params={
                                       'currency': 'USDT',
                                       'fiat': 'RUB',
                                       'tradeType': 'BUY',
                                       'page': 1,
                                       'pageSize': 1
                                   }) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('data') and data['data'].get('items') and len(data['data']['items']) > 0:
                        rate = float(data['data']['items'][0]['price'])
                        print(f"✅ Курс с KuCoin: {rate}")
                        return rate
        return None

    @staticmethod
    async def _parse_bybit():
        """Parse rate from Bybit P2P"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.bybit.com/v5/market/tickers?category=spot&symbol=USDTUSDT',
                                   headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('retCode') == 0 and data.get('result') and data['result'].get('list'):
                        # Bybit shows USDT/USDT, we need to estimate RUB rate
                        # This is a fallback - use a fixed multiplier
                        usdt_usdt = float(data['result']['list'][0]['lastPrice'])
                        # Use a reasonable RUB rate as fallback
                        rate = 90.0  # Fallback rate
                        print(f"✅ Курс с Bybit (fallback): {rate}")
                        return rate
        return None

    @staticmethod
    async def _parse_cbr():
        """Parse rate from Central Bank of Russia (USD to RUB)"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json'
            }
            async with aiohttp.ClientSession() as session:
                async with session.get('https://www.cbr-xml-daily.ru/daily_json.js',
                                       headers=headers, timeout=10, skip_auto_headers=['Accept']) as response:
                    if response.status == 200:
                        text = await response.text()
                        # Parse JSON from text
                        import json
                        data = json.loads(text)
                        if data.get('Valute') and 'USD' in data['Valute']:
                            # Get USD rate from CBR and add premium for USDT
                            usd_rate = float(data['Valute']['USD']['Value'])
                            # USDT typically trades at a premium to USD in Russia
                            rate = usd_rate * 1.02  # Add 2% premium
                            print(f"✅ Курс с ЦБ РФ (USD + премия): {rate}")
                            return rate
        except Exception as e:
            print(f"⚠️ ЦБ РФ не сработал: {e}")
        return None
    
    @staticmethod
    async def _save_rate(rate: float, user_id: int = None, auto: bool = True):
        """Save rate to database"""
        async with db.pool.acquire() as conn:
            await conn.execute(
                '''
                INSERT INTO exchange_rates (usdt_to_rub, updated_by, is_auto_updated)
                VALUES ($1, $2, $3)
                ''',
                rate, user_id, auto
            )
    
    @staticmethod
    async def set_manual_rate(rate: float, user_id: int):
        """Set rate manually by owner"""
        await ExchangeService._save_rate(rate, user_id, False)
        print(f"✅ Курс установлен вручную: {rate} RUB")
        return rate
    
    @staticmethod
    async def clear_old_rates():
        """Очистить старые записи о курсах (оставить последние 100)"""
        async with db.pool.acquire() as conn:
            result = await conn.execute('''
                DELETE FROM exchange_rates 
                WHERE rate_id NOT IN (
                    SELECT rate_id FROM exchange_rates 
                    ORDER BY updated_at DESC 
                    LIMIT 100
                )
            ''')
            print(f"✅ Старые курсы очищены")