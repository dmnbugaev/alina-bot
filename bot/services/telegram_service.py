import logging
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError

from bot.config import Settings

logger = logging.getLogger(__name__)


class InviteLinkError(RuntimeError):
    pass


class InviteDeliveryError(RuntimeError):
    pass


class TelegramService:
    def __init__(self, bot: Bot, settings: Settings):
        self.bot = bot
        self.settings = settings

    async def create_one_time_invite_link(self, payment_id: str) -> tuple[str, datetime]:
        expires_at = datetime.now(UTC) + timedelta(hours=self.settings.invite_ttl_hours)
        try:
            invite = await self.bot.create_chat_invite_link(
                chat_id=self.settings.channel_id,
                name=f"payment-{payment_id[:20]}",
                expire_date=expires_at,
                member_limit=1,
                creates_join_request=False,
            )
        except TelegramAPIError as exc:
            logger.exception(
                "Failed to create invite link for channel_id=%s. "
                "Check that the bot is an admin with invite-link rights.",
                self.settings.channel_id,
            )
            raise InviteLinkError("Telegram invite link creation failed") from exc
        return invite.invite_link, expires_at

    async def send_invite_link(self, telegram_id: int, invite_link: str) -> None:
        try:
            await self.bot.send_message(
                telegram_id,
                "Оплата прошла успешно.\n\n"
                "Ваша персональная ссылка для входа в канал:\n"
                f"{invite_link}\n\n"
                f"Ссылка действует {self.settings.invite_ttl_hours} часа "
                "и рассчитана на одно вступление.",
            )
        except TelegramAPIError as exc:
            raise InviteDeliveryError("Telegram invite delivery failed") from exc

    async def send_payment_reminder(self, telegram_id: int, payment_url: str, final: bool) -> None:
        prefix = "Последнее напоминание" if final else "Небольшое напоминание"
        try:
            await self.bot.send_message(
                telegram_id,
                f"{prefix}: оплата доступа ещё не завершена.\n\n"
                f"Продолжить оплату: {payment_url}\n\n"
                "Если доступ уже не нужен, просто проигнорируйте это сообщение.",
            )
        except TelegramAPIError as exc:
            raise InviteDeliveryError("Telegram reminder delivery failed") from exc

    async def is_channel_member(self, telegram_id: int) -> bool:
        try:
            member = await self.bot.get_chat_member(self.settings.channel_id, telegram_id)
        except TelegramAPIError:
            logger.exception("Failed to check channel membership for telegram_id=%s", telegram_id)
            return False
        if member.status == ChatMemberStatus.RESTRICTED:
            return bool(getattr(member, "is_member", False))
        return member.status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }

    async def notify_admins(self, text: str) -> None:
        for admin_id in self.settings.admin_ids:
            try:
                await self.bot.send_message(admin_id, text)
            except TelegramAPIError:
                logger.exception("Failed to notify admin_id=%s", admin_id)
