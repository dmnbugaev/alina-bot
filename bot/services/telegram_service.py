import logging

from aiogram import Bot

from bot.config import Settings

logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self, bot: Bot, settings: Settings):
        self.bot = bot
        self.settings = settings

    async def create_one_time_invite_link(self) -> str:
        invite = await self.bot.create_chat_invite_link(
            chat_id=self.settings.channel_id,
            member_limit=1,
            creates_join_request=False,
        )
        logger.info("Created one-time invite link for channel_id=%s", self.settings.channel_id)
        return invite.invite_link

    async def send_invite_link(self, telegram_id: int, invite_link: str) -> None:
        await self.bot.send_message(
            telegram_id,
            "Оплата прошла успешно.\n\nВаша одноразовая ссылка для входа в канал:\n"
            f"{invite_link}",
        )
