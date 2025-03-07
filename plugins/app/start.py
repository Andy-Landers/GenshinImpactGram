from typing import Optional

from telegram import Update, ReplyKeyboardRemove, Message, User, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler
from telegram.helpers import escape_markdown

from core.config import config
from core.plugin import handler, Plugin
from plugins.tools.challenge import ChallengeSystem, ChallengeSystemException
from plugins.tools.genshin import PlayerNotFoundError, CookiesNotFoundError, GenshinHelper
from plugins.tools.sign import SignSystem, NeedChallenge
from utils.log import logger


class StartPlugin(Plugin):
    def __init__(self, sign_system: SignSystem, challenge_system: ChallengeSystem, genshin_helper: GenshinHelper):
        self.challenge_system = challenge_system
        self.sign_system = sign_system
        self.genshin_helper = genshin_helper

    @handler.command("start", block=False)
    async def start(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        args = context.args
        if args is not None and len(args) >= 1:
            if args[0] == "inline_message":
                await message.reply_markdown_v2(
                    f"你好 {user.mention_markdown_v2()} {escape_markdown('！我是派蒙 ！')}\n"
                    f"{escape_markdown('发送 /help 命令即可查看命令帮助')}"
                )
            elif args[0] == "set_cookie":
                await message.reply_markdown_v2(
                    f"你好 {user.mention_markdown_v2()} {escape_markdown('！我是派蒙 ！')}\n"
                    f"{escape_markdown('发送 /setcookie 命令进入绑定账号流程')}"
                )
            elif args[0] == "set_uid":
                await message.reply_markdown_v2(
                    f"你好 {user.mention_markdown_v2()} {escape_markdown('！我是派蒙 ！')}\n"
                    f"{escape_markdown('发送 /setuid 或 /setcookie 命令进入绑定账号流程')}"
                )
            elif args[0] == "verify_verification":
                logger.info("用户 %s[%s] 通过start命令 获取认证信息", user.full_name, user.id)
                await self.process_validate(message, user, bot_username=context.bot.username)
            elif args[0] == "sign":
                logger.info("用户 %s[%s] 通过start命令 获取签到信息", user.full_name, user.id)
                await self.get_sign_button(message, user, bot_username=context.bot.username)
            elif args[0].startswith("challenge_"):
                _data = args[0].split("_")
                _command = _data[1]
                _challenge = _data[2]
                if _command == "sign":
                    logger.info("用户 %s[%s] 通过start命令 进入签到流程", user.full_name, user.id)
                    await self.process_sign_validate(message, user, _challenge)
            else:
                await message.reply_html(f"你好 {user.mention_html()} ！我是派蒙 ！\n请点击 /{args[0]} 命令进入对应流程")
            return
        logger.info("用户 %s[%s] 发出start命令", user.full_name, user.id)
        await message.reply_markdown_v2(f"你好 {user.mention_markdown_v2()} {escape_markdown('！我是派蒙 ！')}")

    @staticmethod
    async def unknown_command(update: Update, _: CallbackContext) -> None:
        await update.effective_message.reply_text("前面的区域，以后再来探索吧！")

    @staticmethod
    async def emergency_food(update: Update, _: CallbackContext) -> None:
        await update.effective_message.reply_text("派蒙才不是应急食品！")

    @handler(CommandHandler, command="ping", block=False)
    async def ping(self, update: Update, _: CallbackContext) -> None:
        await update.effective_message.reply_text("online! ヾ(✿ﾟ▽ﾟ)ノ")

    @handler(CommandHandler, command="reply_keyboard_remove", block=False)
    async def reply_keyboard_remove(self, update: Update, _: CallbackContext) -> None:
        await update.message.reply_text("移除远程键盘成功", reply_markup=ReplyKeyboardRemove())

    async def process_sign_validate(self, message: Message, user: User, validate: str):
        try:
            client = await self.genshin_helper.get_genshin_client(user.id)
            await message.reply_chat_action(ChatAction.TYPING)
            _, challenge = await self.sign_system.get_challenge(client.uid)
            if not challenge:
                await message.reply_text("验证请求已过期。", allow_sending_without_reply=True)
                return
            sign_text = await self.sign_system.start_sign(client, challenge=challenge, validate=validate)
            await message.reply_text(sign_text, allow_sending_without_reply=True)
        except (PlayerNotFoundError, CookiesNotFoundError):
            logger.warning("用户 %s[%s] 账号信息未找到", user.full_name, user.id)
        except NeedChallenge:
            await message.reply_text("回调错误，请重新签到", allow_sending_without_reply=True)

    async def process_validate(self, message: Message, user: User, bot_username: Optional[str] = None):
        await message.reply_text(
            "由于官方对第三方工具限制以及账户安全的考虑，频繁使用第三方工具会导致账号被风控并要求用过验证才能进行访问。\n"
            "如果出现频繁验证请求，建议暂停使用本Bot在内的第三方工具查询功能。\n"
            "在暂停使用期间依然出现频繁认证，建议修改密码以保护账号安全。"
        )
        try:
            uid, gt, challenge = await self.challenge_system.create_challenge(user.id, ajax=True)
        except ChallengeSystemException as exc:
            await message.reply_text(exc.message)
            return
        if gt == "ajax":
            await message.reply_text("验证成功")
            return
        url = (
            f"{config.pass_challenge_user_web}/webapp?"
            f"gt={gt}&username={bot_username}&command=verify&challenge={challenge}&uid={uid}"
        )
        await message.reply_text(
            "请尽快在10秒内完成手动验证\n或发送 /web_cancel 取消操作",
            reply_markup=ReplyKeyboardMarkup.from_button(
                KeyboardButton(
                    text="点我手动验证",
                    web_app=WebAppInfo(url=url),
                )
            ),
        )

    async def get_sign_button(self, message: Message, user: User, bot_username: str):
        try:
            client = await self.genshin_helper.get_genshin_client(user.id)
            await message.reply_chat_action(ChatAction.TYPING)
            button = await self.sign_system.get_challenge_button(bot_username, client.uid, user.id, callback=False)
            if not button:
                await message.reply_text("验证请求已过期。", allow_sending_without_reply=True)
                return
            await message.reply_text("请尽快点击下方按钮进行验证。", allow_sending_without_reply=True, reply_markup=button)
        except (PlayerNotFoundError, CookiesNotFoundError):
            logger.warning("用户 %s[%s] 账号信息未找到", user.full_name, user.id)
