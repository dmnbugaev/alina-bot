from functools import lru_cache

from bot.config import get_settings
from bot.services.payment_orchestrator import PaymentOrchestrator
from bot.services.supabase_service import SupabaseService
from bot.services.worker import PaymentWorker
from bot.services.yookassa_service import YooKassaService


@lru_cache
def get_supabase_service() -> SupabaseService:
    return SupabaseService(get_settings())


@lru_cache
def get_yookassa_service() -> YooKassaService:
    return YooKassaService(get_settings())


@lru_cache
def get_payment_orchestrator() -> PaymentOrchestrator:
    return PaymentOrchestrator(
        get_settings(),
        get_supabase_service(),
        get_yookassa_service(),
    )


@lru_cache
def get_payment_worker() -> PaymentWorker:
    return PaymentWorker(
        get_settings(),
        get_supabase_service(),
        get_payment_orchestrator(),
    )
