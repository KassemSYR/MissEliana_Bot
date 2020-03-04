import threading
from typing import Union

from sqlalchemy import Column, String, Boolean, UnicodeText, Integer, BigInteger

from tg_bot.modules.helper_funcs.msg_types import Types
from tg_bot.modules.sql import SESSION, BASE

DEFAULT_WELCOME = "Hey {first}, how are you?"
DEFAULT_GOODBYE = "Nice knowing ya!"

class Welcome(BASE):
    __tablename__ = "welcome_pref"
    chat_id = Column(String(14), primary_key=True)
    should_welcome = Column(Boolean, default=True)
    should_goodbye = Column(Boolean, default=True)

    custom_content = Column(UnicodeText, default=None)
    custom_welcome = Column(UnicodeText, default=DEFAULT_WELCOME)
    welcome_type = Column(Integer, default=Types.TEXT.value)

    custom_content_leave = Column(UnicodeText, default=None)
    custom_leave = Column(UnicodeText, default=DEFAULT_GOODBYE)
    leave_type = Column(Integer, default=Types.TEXT.value)

    clean_welcome = Column(BigInteger)

    def __init__(self, chat_id, should_welcome=True, should_goodbye=True):
        self.chat_id = chat_id
        self.should_welcome = should_welcome
        self.should_goodbye = should_goodbye

    def __repr__(self):
        return "<Chat {} should Welcome new users: {}>".format(self.chat_id, self.should_welcome)


class WelcomeButtons(BASE):
    __tablename__ = "welcome_urls"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(14), primary_key=True)
    name = Column(UnicodeText, nullable=False)
    url = Column(UnicodeText, nullable=False)
    same_line = Column(Boolean, default=False)

    def __init__(self, chat_id, name, url, same_line=False):
        self.chat_id = str(chat_id)
        self.name = name
        self.url = url
        self.same_line = same_line


class GoodbyeButtons(BASE):
    __tablename__ = "leave_urls"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(14), primary_key=True)
    name = Column(UnicodeText, nullable=False)
    url = Column(UnicodeText, nullable=False)
    same_line = Column(Boolean, default=False)

    def __init__(self, chat_id, name, url, same_line=False):
        self.chat_id = str(chat_id)
        self.name = name
        self.url = url
        self.same_line = same_line


class CleanServiceSetting(BASE):
    __tablename__ = "clean_service"
    chat_id = Column(String(14), primary_key=True)
    clean_service = Column(Boolean, default=True)

    def __init__(self, chat_id):
        self.chat_id = str(chat_id)

    def __repr__(self):
        return "<Chat used clean service ({})>".format(self.chat_id)


class WelcomeSecurity(BASE):
    __tablename__ = "welcome_security"
    chat_id = Column(String(14), primary_key=True)
    security = Column(Boolean, default=False)
    mute_time = Column(UnicodeText, default="0")
    custom_text = Column(UnicodeText, default="Klik disini untuk mensuarakan")

    def __init__(self, chat_id, security=False, mute_time="0", custom_text="Klik disini untuk mensuarakan"):
        self.chat_id = str(chat_id) # ensure string
        self.security = security
        self.mute_time = mute_time
        self.custom_text = custom_text

class UserRestirect(BASE):
    __tablename__ = "welcome_restirectlist"
    chat_id = Column(String(14), primary_key=True)
    user_id = Column(Integer, primary_key=True, nullable=False)

    def __init__(self, chat_id, user_id):
        self.chat_id = str(chat_id)  # ensure string
        self.user_id = user_id

    def __repr__(self):
        return "<User restirect '%s' in %s>" % (self.user_id, self.chat_id)

    def __eq__(self, other):
        return bool(isinstance(other, UserRestirect)
                    and self.chat_id == other.chat_id
                    and self.user_id == other.user_id)

class CombotCASStatus(BASE):
    __tablename__ = "cas_stats"
    chat_id = Column(String(14), primary_key=True)
    status = Column(Boolean, default=True)
    autoban = Column(Boolean, default=False)
    
    def __init__(self, chat_id, status, autoban):
        self.chat_id = str(chat_id) #chat_id is int, make sure it's string
        self.status = status
        self.autoban = autoban
        
class DefenseMode(BASE):
    __tablename__ = "defense_mode"
    chat_id = Column(String(14), primary_key=True)
    status = Column(Boolean, default=False)

    def __init__(self, chat_id, status):
       self.chat_id = str(chat_id)
       self.status = status
       
class BannedChat(BASE):
    __tablename__ = "chat_blacklists"
    chat_id = Column(String(14), primary_key=True)
    
    def __init__(self, chat_id):
        self.chat_id = str(chat_id) #chat_id is int, make sure it is string
               
Welcome.__table__.create(checkfirst=True)
WelcomeButtons.__table__.create(checkfirst=True)
GoodbyeButtons.__table__.create(checkfirst=True)
CleanServiceSetting.__table__.create(checkfirst=True)
WelcomeSecurity.__table__.create(checkfirst=True)
UserRestirect.__table__.create(checkfirst=True)
CombotCASStatus.__table__.create(checkfirst=True)
DefenseMode.__table__.create(checkfirst=True)
BannedChat.__table__.create(checkfirst=True)

INSERTION_LOCK = threading.RLock()
WELC_BTN_LOCK = threading.RLock()
LEAVE_BTN_LOCK = threading.RLock()
CAS_LOCK = threading.RLock()
DEFENSE_LOCK = threading.RLock()
CS_LOCK = threading.RLock()
WS_LOCK = threading.RLock()
UR_LOCK = threading.RLock()
BANCHATLOCK = threading.RLock()

BLACKLIST = set()


CHAT_USERRESTIRECT = {}


def add_to_userlist(chat_id, user_id):
    with UR_LOCK:
        user_filt = UserRestirect(str(chat_id), user_id)

        SESSION.merge(user_filt)  # merge to avoid duplicate key issues
        SESSION.commit()
        global CHAT_USERRESTIRECT
        if CHAT_USERRESTIRECT.get(str(chat_id), set()) == set():
            CHAT_USERRESTIRECT[str(chat_id)] = {user_id}
        else:
            CHAT_USERRESTIRECT.get(str(chat_id), set()).add(user_id)


def rm_from_userlist(chat_id, user_id):
    with UR_LOCK:
        user_filt = SESSION.query(UserRestirect).get((str(chat_id), user_id))
        if user_filt:
            if user_id in CHAT_USERRESTIRECT.get(str(chat_id), set()):  # sanity check
                CHAT_USERRESTIRECT.get(str(chat_id), set()).remove(user_id)

            SESSION.delete(user_filt)
            SESSION.commit()
            return True

        SESSION.close()
        return False

def get_chat_userlist(chat_id):
    return CHAT_USERRESTIRECT.get(str(chat_id), set())


def welcome_security(chat_id):
    try:
        security = SESSION.query(WelcomeSecurity).get(str(chat_id))
        if security:
            return security.security, security.mute_time, security.custom_text
        else:
            return False, "0", "Click here to prove you're human"
    finally:
        SESSION.close()


def set_welcome_security(chat_id, security, mute_time, custom_text):
    with WS_LOCK:
        curr_setting = SESSION.query(WelcomeSecurity).get((str(chat_id)))
        if not curr_setting:
            curr_setting = WelcomeSecurity(chat_id, security=security, mute_time=mute_time, custom_text=custom_text)

        curr_setting.security = bool(security)
        curr_setting.mute_time = str(mute_time)
        curr_setting.custom_text = str(custom_text)

        SESSION.add(curr_setting)
        SESSION.commit()


def clean_service(chat_id: Union[str, int]) -> bool:
    try:
        chat_setting = SESSION.query(CleanServiceSetting).get(str(chat_id))
        if chat_setting:
            return chat_setting.clean_service
        return False
    finally:
        SESSION.close()


def set_clean_service(chat_id: Union[int, str], setting: bool):
    with CS_LOCK:
        chat_setting = SESSION.query(CleanServiceSetting).get(str(chat_id))
        if not chat_setting:
            chat_setting = CleanServiceSetting(chat_id)

        chat_setting.clean_service = setting
        SESSION.add(chat_setting)
        SESSION.commit()


def get_welc_pref(chat_id):
    welc = SESSION.query(Welcome).get(str(chat_id))
    SESSION.close()
    if welc:
        return welc.should_welcome, welc.custom_welcome, welc.custom_content, welc.welcome_type
    else:
        # Welcome by default.
        return True, DEFAULT_WELCOME, None, Types.TEXT


def get_gdbye_pref(chat_id):
    welc = SESSION.query(Welcome).get(str(chat_id))
    SESSION.close()
    if welc:
        return welc.should_goodbye, welc.custom_leave, welc.custom_content_leave, welc.leave_type
    else:
        # Welcome by default.
        return True, DEFAULT_GOODBYE, None, Types.TEXT


def set_clean_welcome(chat_id, clean_welcome):
    with INSERTION_LOCK:
        curr = SESSION.query(Welcome).get(str(chat_id))
        if not curr:
            curr = Welcome(str(chat_id))

        curr.clean_welcome = int(clean_welcome)

        SESSION.add(curr)
        SESSION.commit()


def get_clean_pref(chat_id):
    welc = SESSION.query(Welcome).get(str(chat_id))
    SESSION.close()

    if welc:
        return welc.clean_welcome

    return False


def set_welc_preference(chat_id, should_welcome):
    with INSERTION_LOCK:
        curr = SESSION.query(Welcome).get(str(chat_id))
        if not curr:
            curr = Welcome(str(chat_id), should_welcome=should_welcome)
        else:
            curr.should_welcome = should_welcome

        SESSION.add(curr)
        SESSION.commit()


def set_gdbye_preference(chat_id, should_goodbye):
    with INSERTION_LOCK:
        curr = SESSION.query(Welcome).get(str(chat_id))
        if not curr:
            curr = Welcome(str(chat_id), should_goodbye=should_goodbye)
        else:
            curr.should_goodbye = should_goodbye

        SESSION.add(curr)
        SESSION.commit()


def set_custom_welcome(chat_id, custom_content, custom_welcome, welcome_type, buttons=None):
    if buttons is None:
        buttons = []

    with INSERTION_LOCK:
        welcome_settings = SESSION.query(Welcome).get(str(chat_id))
        if not welcome_settings:
            welcome_settings = Welcome(str(chat_id), True)

        if custom_welcome or custom_content:
            welcome_settings.custom_content = custom_content
            welcome_settings.custom_welcome = custom_welcome
            welcome_settings.welcome_type = welcome_type.value

        else:
            welcome_settings.custom_welcome = DEFAULT_WELCOME
            welcome_settings.welcome_type = Types.TEXT.value

        SESSION.add(welcome_settings)

        with WELC_BTN_LOCK:
            prev_buttons = SESSION.query(WelcomeButtons).filter(WelcomeButtons.chat_id == str(chat_id)).all()
            for btn in prev_buttons:
                SESSION.delete(btn)

            for b_name, url, same_line in buttons:
                button = WelcomeButtons(chat_id, b_name, url, same_line)
                SESSION.add(button)

        SESSION.commit()


def get_custom_welcome(chat_id):
    welcome_settings = SESSION.query(Welcome).get(str(chat_id))
    ret = DEFAULT_WELCOME
    if welcome_settings and welcome_settings.custom_welcome:
        ret = welcome_settings.custom_welcome

    SESSION.close()
    return ret


def set_custom_gdbye(chat_id, custom_content_leave, custom_goodbye, goodbye_type, buttons=None):
    if buttons is None:
        buttons = []

    with INSERTION_LOCK:
        welcome_settings = SESSION.query(Welcome).get(str(chat_id))
        if not welcome_settings:
            welcome_settings = Welcome(str(chat_id), True)

        if custom_goodbye:
            welcome_settings.custom_content_leave = custom_content_leave
            welcome_settings.custom_leave = custom_goodbye
            welcome_settings.leave_type = goodbye_type.value

        else:
            welcome_settings.custom_leave = DEFAULT_GOODBYE
            welcome_settings.leave_type = Types.TEXT.value

        SESSION.add(welcome_settings)

        with LEAVE_BTN_LOCK:
            prev_buttons = SESSION.query(GoodbyeButtons).filter(GoodbyeButtons.chat_id == str(chat_id)).all()
            for btn in prev_buttons:
                SESSION.delete(btn)

            for b_name, url, same_line in buttons:
                button = GoodbyeButtons(chat_id, b_name, url, same_line)
                SESSION.add(button)

        SESSION.commit()


def get_custom_gdbye(chat_id):
    welcome_settings = SESSION.query(Welcome).get(str(chat_id))
    ret = DEFAULT_GOODBYE
    if welcome_settings and welcome_settings.custom_leave:
        ret = welcome_settings.custom_leave

    SESSION.close()
    return ret


def get_welc_buttons(chat_id):
    try:
        return SESSION.query(WelcomeButtons).filter(WelcomeButtons.chat_id == str(chat_id)).order_by(
            WelcomeButtons.id).all()
    finally:
        SESSION.close()


def get_gdbye_buttons(chat_id):
    try:
        return SESSION.query(GoodbyeButtons).filter(GoodbyeButtons.chat_id == str(chat_id)).order_by(
            GoodbyeButtons.id).all()
    finally:
        SESSION.close()
        
def get_cas_status(chat_id):
    try:
        resultObj = SESSION.query(CombotCASStatus).get(str(chat_id))
        if resultObj:
            return resultObj.status
        return True
    finally:
        SESSION.close()

def set_cas_status(chat_id, status):
    with CAS_LOCK:
        ban = False
        prevObj = SESSION.query(CombotCASStatus).get(str(chat_id))
        if prevObj:
            ban = prevObj.autoban
            SESSION.delete(prevObj)
        newObj = CombotCASStatus(str(chat_id), status, ban)
        SESSION.add(newObj)
        SESSION.commit()

def get_cas_autoban(chat_id):
    try:
        resultObj = SESSION.query(CombotCASStatus).get(str(chat_id))
        if resultObj and resultObj.autoban:
            return resultObj.autoban
        return False
    finally:
        SESSION.close() 
        
def set_cas_autoban(chat_id, autoban):
    with CAS_LOCK:
        status = True
        prevObj = SESSION.query(CombotCASStatus).get(str(chat_id))
        if prevObj:
            status = prevObj.status
            SESSION.delete(prevObj)
        newObj = CombotCASStatus(str(chat_id), status, autoban)
        SESSION.add(newObj)
        SESSION.commit()
        
def getDefenseStatus(chat_id):
    try:
        resultObj = SESSION.query(DefenseMode).get(str(chat_id))
        if resultObj:
            return resultObj.status
        return False #default
    finally:
        SESSION.close()

def setDefenseStatus(chat_id, status):
    with DEFENSE_LOCK:
        prevObj = SESSION.query(DefenseMode).get(str(chat_id))
        if prevObj:
            SESSION.delete(prevObj)
        newObj = DefenseMode(str(chat_id), status)
        SESSION.add(newObj)
        SESSION.commit()  
        
def __load_blacklisted_chats_list(): #load shit to memory to be faster, and reduce disk access 
    global BLACKLIST
    try:
        BLACKLIST = {x.chat_id for x in SESSION.query(BannedChat).all()}
    finally:
        SESSION.close()

def blacklistChat(chat_id):
    with BANCHATLOCK:
        chat = SESSION.query(BannedChat).get(chat_id)
        if not chat:
            chat = BannedChat(chat_id)
            SESSION.merge(chat)
        SESSION.commit()
        __load_blacklisted_chats_list()
    
def unblacklistChat(chat_id):
    with BANCHATLOCK:
        chat = SESSION.query(BannedChat).get(chat_id)
        if chat:
            SESSION.delete(chat)
        SESSION.commit()
        __load_blacklisted_chats_list()

def isBanned(chat_id):
    return chat_id in BLACKLIST    
    
def migrate_chat(old_chat_id, new_chat_id):
    with INSERTION_LOCK:
        chat = SESSION.query(Welcome).get(str(old_chat_id))
        if chat:
            chat.chat_id = str(new_chat_id)

        with WELC_BTN_LOCK:
            chat_buttons = SESSION.query(WelcomeButtons).filter(WelcomeButtons.chat_id == str(old_chat_id)).all()
            for btn in chat_buttons:
                btn.chat_id = str(new_chat_id)

        with LEAVE_BTN_LOCK:
            chat_buttons = SESSION.query(GoodbyeButtons).filter(GoodbyeButtons.chat_id == str(old_chat_id)).all()
            for btn in chat_buttons:
                btn.chat_id = str(new_chat_id)

        SESSION.commit()

def __load_chat_userrestirect():
    global CHAT_USERRESTIRECT
    try:
        chats = SESSION.query(UserRestirect.chat_id).distinct().all()
        for (chat_id,) in chats:  # remove tuple by ( ,)
            CHAT_USERRESTIRECT[chat_id] = []

        all_filters = SESSION.query(UserRestirect).all()
        for x in all_filters:
            CHAT_USERRESTIRECT[x.chat_id] += [x.user_id]

        CHAT_USERRESTIRECT = {x: set(y) for x, y in CHAT_USERRESTIRECT.items()}

    finally:
        SESSION.close()

__load_chat_userrestirect()
__load_blacklisted_chats_list()
