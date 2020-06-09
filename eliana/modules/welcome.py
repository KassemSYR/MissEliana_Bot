from html import escape
from typing import Optional, List
import html, time
import re

from telegram import Message, Chat, Update, Bot, User, CallbackQuery
from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import BadRequest
from telegram.ext import MessageHandler, Filters, CommandHandler, run_async, CallbackQueryHandler
from telegram.utils.helpers import mention_html

import eliana.modules.sql.welcome_sql as sql
import eliana.modules.sql.antispam_sql as gbansql
import eliana.modules.helper_funcs.cas_api as cas

from eliana.modules.sql.antispam_sql import is_user_gbanned
from eliana import dispatcher, OWNER_ID, LOGGER, MESSAGE_DUMP, sw
from eliana.modules.helper_funcs.chat_status import user_admin, is_user_ban_protected
from eliana.modules.helper_funcs.misc import build_keyboard, revert_buttons
from eliana.modules.helper_funcs.msg_types import get_welcome_type
from eliana.modules.helper_funcs.string_handling import markdown_parser, \
    escape_invalid_curly_brackets, extract_time, markdown_to_html
from eliana.modules.helper_funcs.msg_types import get_welcome_type
from eliana.modules.helper_funcs.extraction import extract_user
from eliana.modules.helper_funcs.filters import CustomFilters
from eliana.modules.disable import DisableAbleCommandHandler
from eliana.modules.log_channel import loggable
from eliana.modules.tr_engine.strings import tld

VALID_WELCOME_FORMATTERS = [
    'first', 'last', 'fullname', 'username', 'id', 'count', 'chatname',
    'mention'
]

ENUM_FUNC_MAP = {
    sql.Types.TEXT.value: dispatcher.bot.send_message,
    sql.Types.BUTTON_TEXT.value: dispatcher.bot.send_message,
    sql.Types.STICKER.value: dispatcher.bot.send_sticker,
    sql.Types.DOCUMENT.value: dispatcher.bot.send_document,
    sql.Types.PHOTO.value: dispatcher.bot.send_photo,
    sql.Types.AUDIO.value: dispatcher.bot.send_audio,
    sql.Types.VOICE.value: dispatcher.bot.send_voice,
    sql.Types.VIDEO.value: dispatcher.bot.send_video
}


# do not async
def send(update, message, keyboard, backup_message):
    chat = update.effective_chat
    cleanserv = sql.clean_service(chat.id)
    reply = update.message.message_id
    # Clean service welcome
    if cleanserv:
        try:
            dispatcher.bot.delete_message(chat.id, update.message.message_id)
        except BadRequest:
            pass
        reply = False
    try:
        msg = update.effective_message.reply_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            reply_to_message_id=reply,
            disable_web_page_preview=True)
    except IndexError:
        msg = update.effective_message.reply_text(
            markdown_parser(backup_message + "\nNote: the current message was "
                            "invalid due to markdown issues. Could be "
                            "due to the user's name."),
            parse_mode=ParseMode.MARKDOWN,
            reply_to_message_id=reply)
    except KeyError:
        msg = update.effective_message.reply_text(
            markdown_parser(backup_message + "\nNote: the current message is "
                            "invalid due to an issue with some misplaced "
                            "curly brackets. Please update"),
            parse_mode=ParseMode.MARKDOWN,
            reply_to_message_id=reply)
    except BadRequest as excp:
        if excp.message == "Button_url_invalid":
            msg = update.effective_message.reply_text(
                markdown_parser(
                    backup_message +
                    "\nNote: the current message has an invalid url "
                    "in one of its buttons. Please update."),
                parse_mode=ParseMode.MARKDOWN,
                reply_to_message_id=reply)
        elif excp.message == "Unsupported url protocol":
            msg = update.effective_message.reply_text(
                markdown_parser(
                    backup_message +
                    "\nNote: the current message has buttons which "
                    "use url protocols that are unsupported by "
                    "telegram. Please update."),
                parse_mode=ParseMode.MARKDOWN,
                reply_to_message_id=reply)
        elif excp.message == "Wrong url host":
            msg = update.effective_message.reply_text(
                markdown_parser(
                    backup_message +
                    "\nNote: the current message has some bad urls. "
                    "Please update."),
                parse_mode=ParseMode.MARKDOWN,
                reply_to_message_id=reply)
            LOGGER.warning(message)
            LOGGER.warning(keyboard)
            LOGGER.exception("Could not parse! got invalid url host errors")
        else:
            try:
                msg = update.effective_message.reply_text(
                    markdown_parser(
                        backup_message +
                        "\nNote: An error occured when sending the "
                        "custom message. Please update."),
                    reply_to_message_id=reply,
                    parse_mode=ParseMode.MARKDOWN)
            except BadRequest:
                return ""
    return msg


@run_async
def new_member(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message # type: Optional[Message]
    chat_name = chat.title or chat.first or chat.username # type: Optional:[chat name]

    should_welc, cust_welcome, cust_content, welc_type = sql.get_welc_pref(
        chat.id)
    cust_welcome = markdown_to_html(cust_welcome)

    casPrefs = sql.get_cas_status(str(chat.id)) #check if enabled, obviously
    autoban = sql.get_cas_autoban(str(chat.id))
    defense = sql.getDefenseStatus(str(chat.id))
    if casPrefs and not autoban and cas.banchecker(user.id):
        bot.restrict_chat_member(chat.id, user.id, 
                                         can_send_messages=False,
                                         can_send_media_messages=False, 
                                         can_send_other_messages=False, 
                                         can_add_web_page_previews=False)
        msg.reply_text("Warning! This user is CAS Banned. I have muted them to avoid spam. Ban is advised.")
        isUserGbanned = gbansql.is_user_gbanned(user.id)
        if not isUserGbanned:
            report = "CAS Banned user detected: <code>{}</code>".format(user.id)
            bot.send_message(MESSAGE_DUMP, report, html=True)
        if defense:
            bantime = int(time.time()) + 60
            chat.kick_member(new_mem.id, until_date=bantime)
    elif casPrefs and autoban and cas.banchecker(user.id):
        chat.kick_member(user.id)
        msg.reply_text("CAS banned user detected! User has been automatically banned!")
        isUserGbanned = gbansql.is_user_gbanned(user.id)
        if not isUserGbanned:
            report = "CAS Banned user detected: <code>{}</code>".format(user.id)
            bot.send_message(MESSAGE_DUMP, report, html=True)
    elif defense and (user.id not in SUDO_USERS + SUPPORT_USERS):
        bantime = int(time.time()) + 60
        chat.kick_member(user.id, until_date=bantime)
    elif should_welc:
        sent = None
        new_members = update.effective_message.new_chat_members
        for new_mem in new_members:
            # Give start information when add bot to group

            if is_user_gbanned(new_mem.id):
                return

            if sw != None:
                sw_ban = sw.get_ban(new_mem.id)
                if sw_ban:
                    return

            if new_mem.id == bot.id:
                bot.send_message(chat.id, tld(chat.id, 'welcome_added_to_grp'))
                bot.send_message(MESSAGE_DUMP, "I have been added to {} with ID: <pre>{}</pre>".format(chat.title, chat.id), parse_mode=ParseMode.HTML)

            else:
                if is_user_gbanned(new_mem.id):
                    return
                # If welcome message is media, send with appropriate function
                if welc_type != sql.Types.TEXT and welc_type != sql.Types.BUTTON_TEXT:
                    reply = update.message.message_id
                    cleanserv = sql.clean_service(chat.id)
                    # Clean service welcome
                    if cleanserv:
                        try:
                            dispatcher.bot.delete_message(
                                chat.id, update.message.message_id)
                        except BadRequest:
                            pass
                        reply = False
                    # Formatting text
                    first_name = new_mem.first_name or "PersonWithNoName"  # edge case of empty name - occurs for some bugs.
                    if new_mem.last_name:
                        fullname = "{} {}".format(first_name,
                                                  new_mem.last_name)
                    else:
                        fullname = first_name
                    count = chat.get_members_count()
                    mention = mention_html(new_mem.id, first_name)
                    if new_mem.username:
                        username = "@" + escape(new_mem.username)
                    else:
                        username = mention
                    formatted_text = cust_welcome.format(
                        first=escape(first_name),
                        last=escape(new_mem.last_name or first_name),
                        fullname=escape(fullname),
                        username=username,
                        mention=mention,
                        count=count,
                        chatname=escape(chat.title),
                        id=new_mem.id)
                    # Build keyboard
                    buttons = sql.get_welc_buttons(chat.id)
                    keyb = build_keyboard(buttons)
                    getsec, mutetime, custom_text = sql.welcome_security(
                        chat.id)

                    member = chat.get_member(new_mem.id)
                    # If user ban protected don't apply security on him
                    if is_user_ban_protected(chat, new_mem.id,
                                             chat.get_member(new_mem.id)):
                        pass
                    elif getsec:
                        # If mute time is turned on
                        if mutetime:
                            if mutetime[:1] == "0":
                                if member.can_send_messages is None or member.can_send_messages:
                                    try:
                                        bot.restrict_chat_member(
                                            chat.id,
                                            new_mem.id,
                                            can_send_messages=False)
                                        canrest = True
                                    except BadRequest:
                                        canrest = False
                                else:
                                    canrest = False

                            else:
                                mutetime = extract_time(
                                    update.effective_message, mutetime)

                                if member.can_send_messages is None or member.can_send_messages:
                                    try:
                                        bot.restrict_chat_member(
                                            chat.id,
                                            new_mem.id,
                                            until_date=mutetime,
                                            can_send_messages=False)
                                        canrest = True
                                    except BadRequest:
                                        canrest = False
                                else:
                                    canrest = False

                        # If security welcome is turned on
                        if canrest:
                            sql.add_to_userlist(chat.id, new_mem.id)
                            keyb.append([
                                InlineKeyboardButton(
                                    text=str(custom_text),
                                    callback_data="check_bot_({})".format(
                                        new_mem.id))
                            ])
                    keyboard = InlineKeyboardMarkup(keyb)
                    # Send message
                    ENUM_FUNC_MAP[welc_type](chat.id,
                                             cust_content,
                                             caption=formatted_text,
                                             reply_markup=keyboard,
                                             parse_mode="html",
                                             reply_to_message_id=reply)
                    return
                # else, move on
                first_name = new_mem.first_name or "PersonWithNoName"  # edge case of empty name - occurs for some bugs.

                if cust_welcome:
                    if new_mem.last_name:
                        fullname = "{} {}".format(first_name,
                                                  new_mem.last_name)
                    else:
                        fullname = first_name
                    count = chat.get_members_count()
                    mention = mention_html(new_mem.id, first_name)
                    if new_mem.username:
                        username = "@" + escape(new_mem.username)
                    else:
                        username = mention

                    valid_format = escape_invalid_curly_brackets(
                        cust_welcome, VALID_WELCOME_FORMATTERS)
                    res = valid_format.format(first=escape(first_name),
                                              last=escape(new_mem.last_name
                                                          or first_name),
                                              fullname=escape(fullname),
                                              username=username,
                                              mention=mention,
                                              count=count,
                                              chatname=escape(chat.title),
                                              id=new_mem.id)
                    buttons = sql.get_welc_buttons(chat.id)
                    keyb = build_keyboard(buttons)
                else:
                    res = sql.DEFAULT_WELCOME.format(first=first_name)
                    keyb = []

                getsec, mutetime, custom_text = sql.welcome_security(chat.id)
                member = chat.get_member(new_mem.id)
                # If user ban protected don't apply security on him
                if is_user_ban_protected(chat, new_mem.id,
                                         chat.get_member(new_mem.id)):
                    pass
                elif getsec:
                    if mutetime:
                        if mutetime[:1] == "0":

                            if member.can_send_messages is None or member.can_send_messages:
                                try:
                                    bot.restrict_chat_member(
                                        chat.id,
                                        new_mem.id,
                                        can_send_messages=False)
                                    canrest = True
                                except BadRequest:
                                    canrest = False
                            else:
                                canrest = False

                        else:
                            mutetime = extract_time(update.effective_message,
                                                    mutetime)

                            if member.can_send_messages is None or member.can_send_messages:
                                try:
                                    bot.restrict_chat_member(
                                        chat.id,
                                        new_mem.id,
                                        until_date=mutetime,
                                        can_send_messages=False)
                                    canrest = True
                                except BadRequest:
                                    canrest = False
                            else:
                                canrest = False

                    if canrest:
                        sql.add_to_userlist(chat.id, new_mem.id)
                        keyb.append([
                            InlineKeyboardButton(
                                text=str(custom_text),
                                callback_data="check_bot_({})".format(
                                    new_mem.id))
                        ])
                keyboard = InlineKeyboardMarkup(keyb)

                sent = send(update, res, keyboard,
                            sql.DEFAULT_WELCOME.format(
                                first=first_name))  # type: Optional[Message]

            prev_welc = sql.get_clean_pref(chat.id)
            if prev_welc:
                try:
                    bot.delete_message(chat.id, prev_welc)
                except BadRequest as excp:
                    pass

            if sent:
                sql.set_clean_welcome(chat.id, sent.message_id)


@run_async
def check_bot_button(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    query = update.callback_query  # type: Optional[CallbackQuery]
    getalluser = sql.get_chat_userlist(chat.id)
    if user.id in getalluser:
        query.answer(text=tld(chat.id, 'welcome_mute_btn_unmuted'))
        # Unmute user
        bot.restrict_chat_member(chat.id,
                                 user.id,
                                 can_send_messages=True,
                                 can_send_media_messages=True,
                                 can_send_other_messages=True,
                                 can_add_web_page_previews=True)
        sql.rm_from_userlist(chat.id, user.id)
    else:
        try:
            query.answer(text=tld(chat.id, 'welcome_mute_btn_old_user'))
        except Exception:
            print("Nut")


@run_async
def left_member(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    should_goodbye, cust_goodbye, cust_content, goodbye_type = sql.get_gdbye_pref(
        chat.id)
    cust_goodbye = markdown_to_html(cust_goodbye)

    if should_goodbye:
        left_mem = update.effective_message.left_chat_member
        if left_mem:

            if is_user_gbanned(left_mem.id):
                return

            if sw != None:
                sw_ban = sw.get_ban(left_mem.id)
                if sw_ban:
                    return

            # Ignore bot being kicked
            if left_mem.id == bot.id:
                return

            # Give the owner a special goodbye
            if left_mem.id == OWNER_ID:
                update.effective_message.reply_text(
                    tld(chat.id, 'welcome_bot_owner_left'))
                return

            # if media goodbye, use appropriate function for it
            if goodbye_type != sql.Types.TEXT and goodbye_type != sql.Types.BUTTON_TEXT:
                reply = update.message.message_id
                cleanserv = sql.clean_service(chat.id)
                # Clean service welcome
                if cleanserv:
                    try:
                        dispatcher.bot.delete_message(
                            chat.id, update.message.message_id)
                    except BadRequest:
                        pass
                    reply = False
                # Formatting text
                first_name = left_mem.first_name or "PersonWithNoName"  # edge case of empty name - occurs for some bugs.
                if left_mem.last_name:
                    fullname = "{} {}".format(first_name, left_mem.last_name)
                else:
                    fullname = first_name
                count = chat.get_members_count()
                mention = mention_html(left_mem.id, first_name)
                if left_mem.username:
                    username = "@" + escape(left_mem.username)
                else:
                    username = mention

                formatted_text = cust_goodbye.format(
                    first=escape(first_name),
                    last=escape(left_mem.last_name or first_name),
                    fullname=escape(fullname),
                    username=username,
                    mention=mention,
                    count=count,
                    chatname=escape(chat.title),
                    id=left_mem.id)

                # Build keyboard
                buttons = sql.get_gdbye_buttons(chat.id)
                keyb = build_keyboard(buttons)
                keyboard = InlineKeyboardMarkup(keyb)

                # Send message
                ENUM_FUNC_MAP[goodbye_type](chat.id,
                                            cust_content,
                                            caption=formatted_text,
                                            reply_markup=keyboard,
                                            parse_mode="html",
                                            reply_to_message_id=reply)
                return

            first_name = left_mem.first_name or "PersonWithNoName"  # edge case of empty name - occurs for some bugs.
            if cust_goodbye:
                if left_mem.last_name:
                    fullname = "{} {}".format(first_name, left_mem.last_name)
                else:
                    fullname = first_name
                count = chat.get_members_count()
                mention = mention_html(left_mem.id, first_name)
                if left_mem.username:
                    username = "@" + escape(left_mem.username)
                else:
                    username = mention

                valid_format = escape_invalid_curly_brackets(
                    cust_goodbye, VALID_WELCOME_FORMATTERS)
                res = valid_format.format(first=escape(first_name),
                                          last=escape(left_mem.last_name
                                                      or first_name),
                                          fullname=escape(fullname),
                                          username=username,
                                          mention=mention,
                                          count=count,
                                          chatname=escape(chat.title),
                                          id=left_mem.id)
                buttons = sql.get_gdbye_buttons(chat.id)
                keyb = build_keyboard(buttons)

            else:
                res = sql.DEFAULT_GOODBYE
                keyb = []

            keyboard = InlineKeyboardMarkup(keyb)

            send(update, res, keyboard, sql.DEFAULT_GOODBYE)


@run_async
@user_admin
def security(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    getcur, cur_value, cust_text = sql.welcome_security(chat.id)
    if len(args) >= 1:
        var = args[0].lower()
        if (var == "yes" or var == "y" or var == "on"):
            check = bot.getChatMember(chat.id, bot.id)
            if check.status == 'member' or check[
                    'can_restrict_members'] == False:
                text = tld(chat.id, 'welcome_mute_bot_cant_mute')
                update.effective_message.reply_text(text,
                                                    parse_mode="markdown")
                return ""
            sql.set_welcome_security(chat.id, True, str(cur_value), cust_text)
            update.effective_message.reply_text(
                tld(chat.id, 'welcome_mute_enabled'))
        elif (var == "no" or var == "n" or var == "off"):
            sql.set_welcome_security(chat.id, False, str(cur_value), cust_text)
            update.effective_message.reply_text(
                tld(chat.id, 'welcome_mute_disabled'))
        else:
            update.effective_message.reply_text(tld(chat.id,
                                                    'common_invalid_arg'),
                                                parse_mode=ParseMode.MARKDOWN)
    else:
        getcur, cur_value, cust_text = sql.welcome_security(chat.id)
        if getcur:
            getcur = "True"
        else:
            getcur = "False"
        if cur_value[:1] == "0":
            cur_value = "None"
        text = tld(chat.id, 'welcome_mute_curr_settings').format(
            getcur, cur_value, cust_text)
        update.effective_message.reply_text(text, parse_mode="markdown")


@run_async
@user_admin
def security_mute(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]
    getcur, cur_value, cust_text = sql.welcome_security(chat.id)
    if len(args) >= 1:
        var = args[0]
        if var[:1] == "0":
            mutetime = "0"
            sql.set_welcome_security(chat.id, getcur, "0", cust_text)
            text = tld(chat.id, 'welcome_mute_time_none')
        else:
            mutetime = extract_time(message, var)
            if mutetime == "":
                return
            sql.set_welcome_security(chat.id, getcur, str(var), cust_text)
            text = tld(chat.id, 'welcome_mute_time').format(var)
        update.effective_message.reply_text(text)
    else:
        if str(cur_value) == "0":
            update.effective_message.reply_text(
                tld(chat.id, 'welcome_mute_time_settings_none'))
        else:
            update.effective_message.reply_text(
                tld(chat.id, 'welcome_mute_time_settings').format(cur_value))


@run_async
@user_admin
def security_text(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    getcur, cur_value, cust_text = sql.welcome_security(chat.id)
    if len(args) >= 1:
        text = " ".join(args)
        sql.set_welcome_security(chat.id, getcur, cur_value, text)
        text = tld(chat.id, 'welcome_mute_btn_text_changed').format(text)
        update.effective_message.reply_text(text, parse_mode="markdown")
    else:
        update.effective_message.reply_text(tld(
            chat.id, 'welcome_mute_btn_curr_text').format(cust_text),
                                            parse_mode="markdown")


@run_async
@user_admin
def security_text_reset(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    getcur, cur_value, cust_text = sql.welcome_security(chat.id)
    sql.set_welcome_security(chat.id, getcur, cur_value,
                             tld(chat.id, 'welcome_mute_btn_default_text'))
    update.effective_message.reply_text(tld(
        chat.id, 'welcome_mute_btn_text_reset').format(
            tld(chat.id, 'welcome_mute_btn_default_text')),
                                        parse_mode="markdown")


@run_async
@user_admin
def cleanservice(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    if chat.type != chat.PRIVATE:
        if len(args) >= 1:
            var = args[0]
            if (var == "no" or var == "off"):
                sql.set_clean_service(chat.id, False)
                update.effective_message.reply_text(
                    tld(chat.id, 'welcome_clean_service_off'))
            elif (var == "yes" or var == "on"):
                sql.set_clean_service(chat.id, True)
                update.effective_message.reply_text(
                    tld(chat.id, 'welcome_clean_service_on'))
            else:
                update.effective_message.reply_text(
                    tld(chat.id, 'common_invalid_arg'),
                    parse_mode=ParseMode.MARKDOWN)
        else:
            update.effective_message.reply_text(tld(chat.id,
                                                    'common_invalid_arg'),
                                                parse_mode=ParseMode.MARKDOWN)
    else:
        curr = sql.clean_service(chat.id)
        if curr:
            update.effective_message.reply_text(tld(
                chat.id, 'welcome_clean_service_on'),
                                                parse_mode=ParseMode.MARKDOWN)
        else:
            update.effective_message.reply_text(tld(
                chat.id, 'welcome_clean_service_off'),
                                                parse_mode=ParseMode.MARKDOWN)


@run_async
@user_admin
def welcome(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat  # type: Optional[Chat]
    # if no args, show current replies.
    if len(args) == 0 or args[0].lower() == "noformat":
        noformat = args and args[0].lower() == "noformat"
        pref, welcome_m, cust_content, welcome_type = sql.get_welc_pref(
            chat.id)
        prev_welc = sql.get_clean_pref(chat.id)
        if prev_welc:
            prev_welc = True
        else:
            prev_welc = False
        cleanserv = sql.clean_service(chat.id)
        getcur, cur_value, cust_text = sql.welcome_security(chat.id)
        if getcur:
            welcsec = "True "
        else:
            welcsec = "False "
        if cur_value[:1] == "0":
            welcsec += tld(chat.id, 'welcome_mute_time_short_none')
        else:
            welcsec += tld(chat.id,
                           'welcome_mute_time_short').format(cur_value)

        text = tld(chat.id,
                   'welcome_settings').format(pref, prev_welc, cleanserv,
                                              welcsec, cust_text)
        update.effective_message.reply_text(text,
                                            parse_mode=ParseMode.MARKDOWN)

        if welcome_type == sql.Types.BUTTON_TEXT or welcome_type == sql.Types.TEXT:
            buttons = sql.get_welc_buttons(chat.id)
            if noformat:
                welcome_m += revert_buttons(buttons)
                update.effective_message.reply_text(welcome_m)

            else:
                keyb = build_keyboard(buttons)
                keyboard = InlineKeyboardMarkup(keyb)

                send(update, welcome_m, keyboard, sql.DEFAULT_WELCOME)

        else:
            buttons = sql.get_welc_buttons(chat.id)
            if noformat:
                welcome_m += revert_buttons(buttons)
                ENUM_FUNC_MAP[welcome_type](chat.id,
                                            cust_content,
                                            caption=welcome_m)

            else:
                keyb = build_keyboard(buttons)
                keyboard = InlineKeyboardMarkup(keyb)
                ENUM_FUNC_MAP[welcome_type](chat.id,
                                            cust_content,
                                            caption=welcome_m,
                                            reply_markup=keyboard,
                                            parse_mode=ParseMode.HTML,
                                            disable_web_page_preview=True)

    elif len(args) >= 1:
        if args[0].lower() in ("on", "yes"):
            sql.set_welc_preference(str(chat.id), True)
            update.effective_message.reply_text(
                tld(chat.id, 'welcome_greet_set_on'))

        elif args[0].lower() in ("off", "no"):
            sql.set_welc_preference(str(chat.id), False)
            update.effective_message.reply_text(
                tld(chat.id, 'welcome_greet_set_off'))

        else:
            # idek what you're writing, say yes or no
            update.effective_message.reply_text(
                tld(chat.id, 'common_invalid_arg'))


@run_async
@user_admin
def goodbye(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat  # type: Optional[Chat]

    if len(args) == 0 or args[0] == "noformat":
        noformat = args and args[0] == "noformat"
        pref, goodbye_m, cust_content, goodbye_type = sql.get_gdbye_pref(
            chat.id)
        if cust_content == None:
            cust_content = goodbye_m

        update.effective_message.reply_text(tld(
            chat.id, 'welcome_goodbye_settings').format(pref),
                                            parse_mode=ParseMode.MARKDOWN)

        if goodbye_type == sql.Types.BUTTON_TEXT:
            buttons = sql.get_gdbye_buttons(chat.id)
            if noformat:
                goodbye_m += revert_buttons(buttons)
                update.effective_message.reply_text(goodbye_m)

            else:
                keyb = build_keyboard(buttons)
                keyboard = InlineKeyboardMarkup(keyb)

                send(update, goodbye_m, keyboard, sql.DEFAULT_GOODBYE)

        else:
            buttons = sql.get_gdbye_buttons(chat.id)
            if noformat:
                goodbye_m += revert_buttons(buttons)
                ENUM_FUNC_MAP[goodbye_type](chat.id,
                                            cust_content,
                                            caption=goodbye_m)

            else:
                keyb = build_keyboard(buttons)
                keyboard = InlineKeyboardMarkup(keyb)
                ENUM_FUNC_MAP[goodbye_type](chat.id,
                                            cust_content,
                                            caption=goodbye_m,
                                            reply_markup=keyboard,
                                            parse_mode=ParseMode.HTML,
                                            disable_web_page_preview=True)

    elif len(args) >= 1:
        if args[0].lower() in ("on", "yes"):
            sql.set_gdbye_preference(str(chat.id), True)
            try:
                update.effective_message.reply_text(
                    tld(chat.id, 'welcome_goodbye_set_on'))
            except Exception:
                print("Nut")

        elif args[0].lower() in ("off", "no"):
            sql.set_gdbye_preference(str(chat.id), False)
            update.effective_message.reply_text(
                tld(chat.id, 'welcome_goodbye_set_off'))

        else:
            # idek what you're writing, say yes or no
            update.effective_message.reply_text(tld(chat.id,
                                                    'common_invalid_arg'),
                                                parse_mode=ParseMode.MARKDOWN)


@run_async
@user_admin
@loggable
def set_welcome(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]

    # If user is not set text and not reply a message
    if not msg.reply_to_message:
        if len(msg.text.split()) == 1:
            msg.reply_text(tld(chat.id, 'welcome_set_welcome_no_text'),
                           parse_mode="markdown")
            return ""

    text, data_type, content, buttons = get_welcome_type(msg)

    if data_type is None:
        msg.reply_text(tld(chat.id, "welcome_set_welcome_no_datatype"))
        return ""

    sql.set_custom_welcome(chat.id, content, text, data_type, buttons)
    msg.reply_text(tld(chat.id, 'welcome_set_welcome_success'))

    return "<b>{}:</b>" \
           "\n#SET_WELCOME" \
           "\n<b>Admin:</b> {}" \
           "\nSet the welcome message.".format(escape(chat.title),
                                               mention_html(user.id, user.first_name))


@run_async
@user_admin
@loggable
def reset_welcome(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    sql.set_custom_welcome(chat.id, None, sql.DEFAULT_WELCOME, sql.Types.TEXT)
    update.effective_message.reply_text(
        tld(chat.id, 'welcome_reset_welcome_success'))
    return "<b>{}:</b>" \
           "\n#RESET_WELCOME" \
           "\n<b>Admin:</b> {}" \
           "\nReset the welcome message to default.".format(escape(chat.title),
                                                            mention_html(user.id, user.first_name))


@run_async
@user_admin
@loggable
def set_goodbye(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]
    text, data_type, content, buttons = get_welcome_type(msg)

    # If user is not set text and not reply a message
    if not msg.reply_to_message:
        if len(msg.text.split()) == 1:
            msg.reply_text(tld(chat.id, 'welcome_set_welcome_no_text'),
                           parse_mode="markdown")
            return ""

    if data_type is None:
        msg.reply_text(tld(chat.id, 'welcome_set_welcome_no_datatype'))
        return ""

    sql.set_custom_gdbye(chat.id, content, text, data_type, buttons)
    msg.reply_text(tld(chat.id, 'welcome_set_goodbye_success'))
    return "<b>{}:</b>" \
           "\n#SET_GOODBYE" \
           "\n<b>Admin:</b> {}" \
           "\nSet the goodbye message.".format(escape(chat.title),
                                               mention_html(user.id, user.first_name))


@run_async
@user_admin
@loggable
def reset_goodbye(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    sql.set_custom_gdbye(chat.id, None, sql.DEFAULT_GOODBYE, sql.Types.TEXT)
    update.effective_message.reply_text(
        tld(chat.id, 'welcome_reset_goodbye_success'))
    return "<b>{}:</b>" \
           "\n#RESET_GOODBYE" \
           "\n<b>Admin:</b> {}" \
           "\nReset the goodbye message.".format(escape(chat.title),
                                                 mention_html(user.id, user.first_name))


@run_async
@user_admin
@loggable
def clean_welcome(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]

    if not args:
        clean_pref = sql.get_clean_pref(chat.id)
        if clean_pref:
            update.effective_message.reply_text(
                tld(chat.id, 'welcome_clean_curr_on'))
        else:
            update.effective_message.reply_text(
                tld(chat.id, 'welcome_clean_curr_off'))
        return ""

    if args[0].lower() in ("on", "yes"):
        sql.set_clean_welcome(str(chat.id), True)
        update.effective_message.reply_text(
            tld(chat.id, 'welcome_clean_set_on'))
        return "<b>{}:</b>" \
               "\n#CLEAN_WELCOME" \
               "\n<b>Admin:</b> {}" \
               "\nHas toggled clean welcomes to <code>ON</code>.".format(escape(chat.title),
                                                                         mention_html(user.id, user.first_name))
    elif args[0].lower() in ("off", "no"):
        sql.set_clean_welcome(str(chat.id), False)
        update.effective_message.reply_text(
            tld(chat.id, 'welcome_clean_set_off'))
        return "<b>{}:</b>" \
               "\n#CLEAN_WELCOME" \
               "\n<b>Admin:</b> {}" \
               "\nHas toggled clean welcomes to <code>OFF</code>.".format(escape(chat.title),
                                                                                   mention_html(user.id, user.first_name))
    else:
        # idek what you're writing, say yes or no
        update.effective_message.reply_text(
            "I understand 'on/yes' or 'off/no' only!")
        return ""

@run_async
@user_admin
def setcas(bot: Bot, update: Update):
    chat = update.effective_chat
    msg = update.effective_message
    split_msg = msg.text.split(' ')
    if len(split_msg)!= 2:
        msg.reply_text("Invalid arguments!")
        return
    param = split_msg[1]
    if param == "on" or param == "true":
        sql.set_cas_status(chat.id, True)
        msg.reply_text("Successfully updated configuration.")
        return
    elif param == "off" or param == "false":
        sql.set_cas_status(chat.id, False)
        msg.reply_text("Successfully updated configuration.")
        return
    else:
        msg.reply_text("Invalid status to set!") #on or off ffs
        return

@run_async
@user_admin
def setban(bot: Bot, update: Update):
    chat = update.effective_chat
    msg = update.effective_message
    split_msg = msg.text.split(' ')
    if len(split_msg)!= 2:
        msg.reply_text("Invalid arguments!")
        return
    param = split_msg[1]
    if param == "on" or param == "true":
        sql.set_cas_autoban(chat.id, True)
        msg.reply_text("Successfully updated configuration.")
        return
    elif param == "off" or param == "false":
        sql.set_cas_autoban(chat.id, False)
        msg.reply_text("Successfully updated configuration.")
        return
    else:
        msg.reply_text("Invalid autoban definition to set!") #on or off ffs
        return

@run_async
@user_admin
def get_current_setting(bot: Bot, update: Update):
    chat = update.effective_chat
    msg = update.effective_message
    stats = sql.get_cas_status(chat.id)
    autoban = sql.get_cas_autoban(chat.id)
    rtext = "<b>CAS Preferences</b>\n\nCAS Checking: {}\nAutoban: {}".format(stats, autoban)
    msg.reply_text(rtext, parse_mode=ParseMode.HTML)
    return

@run_async
def caschecker(bot: Bot, update: Update, args: List[str]):
    #/info logic
    msg = update.effective_message  # type: Optional[Message]
    user_id = extract_user(update.effective_message, args)
    if user_id and int(user_id) != 777000:
        user = bot.get_chat(user_id)
    elif user_id and int(user_id) == 777000:
        msg.reply_text("This is Telegram. Unless you manually entered this reserved account's ID, it is likely a broadcast from a linked channel.")
        return
    elif not msg.reply_to_message and not args:
        user = msg.from_user
    elif not msg.reply_to_message and (not args or (
            len(args) >= 1 and not args[0].startswith("@") and not args[0].isdigit() and not msg.parse_entities(
        [MessageEntity.TEXT_MENTION]))):
        msg.reply_text("I can't extract a user from this.")
        return
    else:
        return

    text = "<b>CAS Check</b>:" \
           "\nID: <code>{}</code>" \
           "\nFirst Name: {}".format(user.id, html.escape(user.first_name))
    if user.last_name:
        text += "\nLast Name: {}".format(html.escape(user.last_name))
    if user.username:
        text += "\nUsername: @{}".format(html.escape(user.username))
    text += "\n\nCAS Banned: "
    result = cas.banchecker(user.id)
    text += str(result)
    if result:
        parsing = cas.offenses(user.id)
        if parsing:
            text += "\nTotal of Offenses: "
            text += str(parsing)
        parsing = cas.timeadded(user.id)
        if parsing:
            parseArray=str(parsing).split(", ")
            text += "\nDay added: "
            text += str(parseArray[1])
            text += "\nTime added: "
            text += str(parseArray[0])
            text += "\n\nAll times are in UTC"
    update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

#this sends direct request to combot server. Will return true if user is banned, false if
#id invalid or user not banned
@run_async
def casquery(bot: Bot, update: Update, args: List[str]):
    msg = update.effective_message  # type: Optional[Message]
    try:
        user_id = msg.text.split(' ')[1]
    except:
        msg.reply_text("There was a problem parsing the query.")
        return
    text = "Your query returned: "
    result = cas.banchecker(user_id)
    text += str(result)
    msg.reply_text(text)
    
@run_async
@user_admin
def setDefense(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat
    msg = update.effective_message
    if len(args)!=1:
        stat = sql.getDefenseStatus(chat.id)
        text = "This group has the defense setting set to: <b>{}</b>\nUse On/off - yes/no to change settings.".format(stat)
        msg.reply_text(text, parse_mode=ParseMode.HTML)
        return
    param = args[0]
    if param == "on" or param == "true":
        sql.setDefenseStatus(chat.id, True)
        msg.reply_text("Defense mode has been turned on, this group is under attack. Every user that now joins will be auto kicked.")
        return
    elif param == "off" or param == "false":
        sql.setDefenseStatus(chat.id, False)
        msg.reply_text("Defense mode has been turned off, group is no longer under attack.")
        return
    else:
        msg.reply_text("Invalid status to set!") #on or off ffs
        return 
    
def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


__help__ = True

NEW_MEM_HANDLER = MessageHandler(Filters.status_update.new_chat_members,
                                 new_member)
LEFT_MEM_HANDLER = MessageHandler(Filters.status_update.left_chat_member,
                                  left_member)
WELC_PREF_HANDLER = CommandHandler("welcome",
                                   welcome,
                                   pass_args=True,
                                   filters=Filters.group)
GOODBYE_PREF_HANDLER = CommandHandler("goodbye",
                                      goodbye,
                                      pass_args=True,
                                      filters=Filters.group)
SET_WELCOME = CommandHandler("setwelcome", set_welcome, filters=Filters.group)
SET_GOODBYE = CommandHandler("setgoodbye", set_goodbye, filters=Filters.group)
RESET_WELCOME = CommandHandler("resetwelcome",
                               reset_welcome,
                               filters=Filters.group)
RESET_GOODBYE = CommandHandler("resetgoodbye",
                               reset_goodbye,
                               filters=Filters.group)
CLEAN_WELCOME = CommandHandler("cleanwelcome",
                               clean_welcome,
                               pass_args=True,
                               filters=Filters.group)
SECURITY_HANDLER = CommandHandler("welcomemute",
                                  security,
                                  pass_args=True,
                                  filters=Filters.group)
SECURITY_MUTE_HANDLER = CommandHandler("welcomemutetime",
                                       security_mute,
                                       pass_args=True,
                                       filters=Filters.group)
SECURITY_BUTTONTXT_HANDLER = CommandHandler("setmutetext",
                                            security_text,
                                            pass_args=True,
                                            filters=Filters.group)
SECURITY_BUTTONRESET_HANDLER = CommandHandler("resetmutetext",
                                              security_text_reset,
                                              filters=Filters.group)
CLEAN_SERVICE_HANDLER = CommandHandler("cleanservice",
                                       cleanservice,
                                       pass_args=True,
                                       filters=Filters.group)

SETCAS_HANDLER = CommandHandler("setcas", setcas, filters=Filters.group)
GETCAS_HANDLER = CommandHandler("getcas", get_current_setting, filters=Filters.group)
CASCHECK_HANDLER = CommandHandler("cascheck", caschecker, pass_args=True)
CASQUERY_HANDLER = CommandHandler("casquery", casquery, pass_args=True ,filters=CustomFilters.sudo_filter)
SETBAN_HANDLER = CommandHandler("setban", setban, filters=Filters.group)
DEFENSE_HANDLER = CommandHandler("defense", setDefense, pass_args=True)                           
                                       
help_callback_handler = CallbackQueryHandler(check_bot_button,
                                             pattern=r"check_bot_")

dispatcher.add_handler(NEW_MEM_HANDLER)
dispatcher.add_handler(LEFT_MEM_HANDLER)
dispatcher.add_handler(WELC_PREF_HANDLER)
dispatcher.add_handler(GOODBYE_PREF_HANDLER)
dispatcher.add_handler(SET_WELCOME)
dispatcher.add_handler(SET_GOODBYE)
dispatcher.add_handler(RESET_WELCOME)
dispatcher.add_handler(RESET_GOODBYE)
dispatcher.add_handler(CLEAN_WELCOME)
dispatcher.add_handler(SECURITY_HANDLER)
dispatcher.add_handler(SECURITY_MUTE_HANDLER)
dispatcher.add_handler(SECURITY_BUTTONTXT_HANDLER)
dispatcher.add_handler(SECURITY_BUTTONRESET_HANDLER)
dispatcher.add_handler(CLEAN_SERVICE_HANDLER)
dispatcher.add_handler(SETCAS_HANDLER)
dispatcher.add_handler(GETCAS_HANDLER)
dispatcher.add_handler(CASCHECK_HANDLER)
dispatcher.add_handler(CASQUERY_HANDLER)
dispatcher.add_handler(SETBAN_HANDLER)
dispatcher.add_handler(DEFENSE_HANDLER)

dispatcher.add_handler(help_callback_handler)
