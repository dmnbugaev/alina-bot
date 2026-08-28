import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot.config import Settings

logger = logging.getLogger(__name__)


class InviteLinkError(RuntimeError):
    pass


class TelegramService:
    def __init__(self, bot: Bot, settings: Settings):
        self.bot = bot
        self.settings = settings

    async def create_one_time_invite_link(self) -> str:
        try:
            invite = await self.bot.create_chat_invite_link(
                chat_id=self.settings.channel_id,
                member_limit=1,
                creates_join_request=False,
            )
        except TelegramAPIError as exc:
            logger.exception(
                "Failed to create invite link for channel_id=%s. "
                "Check that CHANNEL_ID is correct and the bot is an admin with invite-link rights.",
                self.settings.channel_id,
            )
            raise InviteLinkError("Telegram invite link creation failed") from exc
        logger.info("Created one-time invite link for channel_id=%s", self.settings.channel_id)
        return invite.invite_link

    async def send_invite_link(self, telegram_id: int, invite_link: str) -> None:
        await self.bot.send_message(
            telegram_id,
            "Оплата прошла успешно.\n\nВаша одноразовая ссылка для входа в канал:\n"
            f"{invite_link}",
        )
