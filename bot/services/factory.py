from functools import lru_cache

from bot.config import get_settings
from bot.services.supabase_service import SupabaseService
from bot.services.yookassa_service import YooKassaService


@lru_cache
def get_supabase_service() -> SupabaseService:
    return SupabaseService(get_settings())


@lru_cache
def get_yookassa_service() -> YooKassaService:
    return YooKassaService(get_settings())
