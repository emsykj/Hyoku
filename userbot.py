import os
import sys
import time
import random
import logging
import threading
import sqlite3
from telethon import TelegramClient, events
from telethon.tl.functions.account import UpdateProfileRequest
import psutil
import asyncio
from datetime import datetime
import codecs
from telethon.errors import MessageIdInvalidError, SessionPasswordNeededError
import re
import json
import warnings
import requests
import platform

warnings.filterwarnings("ignore", category=SyntaxWarning)

VERSION = "1.0.0"

if os.name == 'nt':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.ERROR, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("userbot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logging.getLogger('telethon').setLevel(logging.ERROR)
logging.getLogger('__main__').setLevel(logging.ERROR)
logging.getLogger('userbot').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

os.environ['SQLITE_TMPDIR'] = os.path.abspath(os.path.dirname(__file__))  

sqlite3.enable_callback_tracebacks(True)  

try:
    session_file = 'userbot_new.session'
    if os.path.exists(session_file):
        import shutil
        backup_file = f"{session_file}.backup"
        shutil.copy2(session_file, backup_file)
        
        conn = sqlite3.connect(session_file, timeout=60.0)
        conn.execute("PRAGMA journal_mode = WAL;")  
        conn.execute("PRAGMA synchronous = NORMAL;")  
        conn.execute("PRAGMA temp_store = MEMORY;")  
        conn.execute("PRAGMA busy_timeout = 30000;")  
        conn.close()
except Exception as e:
    logger.warning(f"Failed to optimize session file: {e}")

old_connect = sqlite3.connect

def patched_connect(*args, **kwargs):
    kwargs['timeout'] = 60.0  
    kwargs['isolation_level'] = None 
    conn = old_connect(*args, **kwargs)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn

sqlite3.connect = patched_connect

def clear_screen():
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')

def get_credentials():
    env_exists = os.path.exists('.env')
    
    if env_exists:
        from dotenv import load_dotenv
        load_dotenv()
        
        api_id = os.getenv('API_ID')
        api_hash = os.getenv('API_HASH')
        phone = os.getenv('PHONE')
        owner_id = os.getenv('OWNER_ID')  
        
        if api_id and api_hash and phone:
            return api_id, api_hash, phone, owner_id
    
    clear_screen()
    print("""
 _   _ __  __ ____  __  __  __ __ 
| |_| |\\ \\/ // () \\|  |/  /|  |  |
|_| |_| |__| \\____/|__|\\__\\ \\___/ 
""")
    
    print("\nВам необходимо указать API данные Telegram:")
    api_id = input("API ID: ")
    api_hash = input("API HASH: ")
    phone = input("Номер телефона: ")
    owner_id = None  
    
    with open('.env', 'w') as f:
        f.write(f"API_ID={api_id}\n")
        f.write(f"API_HASH={api_hash}\n")
        f.write(f"PHONE={phone}\n")
        if owner_id:
            f.write(f"OWNER_ID={owner_id}\n")
    
    print("\nДанные сохранены. Запуск бота...")
    return api_id, api_hash, phone, owner_id

API_ID, API_HASH, PHONE, ENV_OWNER_ID = get_credentials()

client = TelegramClient('userbot', API_ID, API_HASH, device_model="Hyoku", app_version=VERSION)

client.flood_sleep_threshold = 60  
client.retry_delay = 1  
client.auto_reconnect = True  
client.connection_retries = 10
client.takeout = False
client.use_ipv6 = False
client.request_retries = 10

start_time = time.time()

connection_retries = 0
last_activity_time = time.time()
keep_alive_running = False

OWNER_ID = ENV_OWNER_ID if ENV_OWNER_ID else None
OWNER_INIT_DONE = False if not ENV_OWNER_ID else True

async def is_owner(event):
    global OWNER_ID, OWNER_INIT_DONE
    
    try:
        if event.out:
            return True
            
        if OWNER_ID is None:
            if not client.is_connected():
                try:
                    await client.connect()
                except Exception as e:
                    logger.error(f"Failed to connect in is_owner: {e}")
                    return True
            
            try:
                me = await client.get_me()
                OWNER_ID = me.id
                
                if not ENV_OWNER_ID:
                    from dotenv import load_dotenv, set_key
                    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
                    load_dotenv(dotenv_path)
                    set_key(dotenv_path, "OWNER_ID", str(OWNER_ID))
                
                if not OWNER_INIT_DONE:
                    OWNER_INIT_DONE = True
            except Exception as e:
                logger.error(f"Failed to get_me in is_owner: {e}")
                return True
        
        sender_id = event.sender_id
        is_owner_result = sender_id == OWNER_ID
        
        return is_owner_result
    except Exception as e:
        logger.error(f"Error in is_owner check: {e}")
        return True

def get_uptime():
    uptime = time.time() - start_time
    days = int(uptime // 86400)
    hours = int((uptime % 86400) // 3600)
    minutes = int((uptime % 3600) // 60)
    seconds = int(uptime % 60)
    
    if days > 0:
        return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def get_cpu_usage():
    return psutil.cpu_percent()

def get_ram_usage():
    return psutil.Process().memory_info().rss / 1024 / 1024

def detect_platform():
    system = platform.system()
    
    if os.path.exists("/data/data/com.termux"):
        return "ᴛᴇʀᴍᴜx"
    
    if system == "Linux":
        with open("/proc/1/cgroup", "r") as f:
            if "docker" in f.read() or "lxc" in f.read():
                return "ᴠᴅs"
        
        try:
            with open("/proc/cpuinfo", "r") as f:
                cpuinfo = f.read().lower()
                if "kvm" in cpuinfo or "qemu" in cpuinfo or "vmware" in cpuinfo or "xen" in cpuinfo:
                    return "ᴠᴅs"
        except:
            pass
            
        return "ʟɪɴᴜx"
    
    elif system == "Windows":
        return "ᴡɪɴᴅᴏᴡs"
    
    return f"{system}"

def create_pattern(command, with_args=False):
    """
    Создаёт регулярное выражение для команды с учётом префикса
    """
    prefix = "."
    
    if with_args:
        return re.compile(f"^{re.escape(prefix)}{command}(?:\\s+(.+))?$")
    else:
        return re.compile(f"^{re.escape(prefix)}{command}$")

async def safe_edit(event, text, **kwargs):
    """
    Безопасно редактирует сообщение, а в случае ошибки отправляет новое
    и удаляет оригинальное сообщение, если есть права на удаление.
    """
    try:
        return await event.edit(text, **kwargs)
    except MessageIdInvalidError:
        new_message = await event.respond(text, **kwargs)
        try:
            if event.out:
                await event.delete()
        except Exception as e:
            logger.warning(f"Failed to delete original message: {e}")
        return new_message
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        return await event.respond(text, **kwargs)

def read_module_info(file_path):
    dev = "unknown"
    desc = "No description"
    commands = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
            for i, line in enumerate(lines):
                line = line.strip()
                if line.startswith('# meta developer:'):
                    dev = line.replace('# meta developer:', '').strip()
                    if dev == "@qveroz":
                        dev = "@qveroz"
                elif line.startswith('# description:'):
                    desc = line.replace('# description:', '').strip()
                elif line.startswith('# command:'):
                    cmd = line.replace('# command:', '').strip()
                    commands.append(cmd)
    except Exception as e:
        logger.error(f"Error reading module info from {file_path}: {str(e)}")
        
    return dev, desc, commands

async def keep_alive():
    global keep_alive_running, last_activity_time
    
    if keep_alive_running:
        return
        
    keep_alive_running = True
    
    try:
        while True:
            try:
                if time.time() - last_activity_time > 45:  
                    last_activity_time = time.time()
                    
                    if not client.is_connected():
                        logger.info("Reconnecting due to disconnection detected in keep_alive")
                        await ensure_connection()
                    else:
                        try:
                            await client.get_dialogs(limit=1)
                            logger.debug("Keep-alive: Connection maintained")
                        except Exception as e:
                            if "database is locked" in str(e):
                                logger.debug(f"Database locked in keep-alive, waiting...")
                                await asyncio.sleep(2)
                                await ensure_connection()
                            else:
                                logger.warning(f"Keep-alive ping failed: {e}")
                                await ensure_connection()
            except Exception as e:
                logger.error(f"Error in keep_alive: {e}")
                
            await asyncio.sleep(20)  
    finally:
        keep_alive_running = False

async def ensure_connection():
    global connection_retries
    
    if not client.is_connected():
        try:
            logger.info(f"Attempting to reconnect (attempt {connection_retries + 1})")
            await client.connect()
            await asyncio.sleep(0.5)  
            
            if client.is_connected():
                connection_retries = 0
                logger.info("Successfully reconnected")
                return True
            else:
                connection_retries += 1
                if connection_retries > 10:
                    logger.warning("Too many failed reconnection attempts, restarting client")
                    await client.disconnect()
                    await asyncio.sleep(1)  
                    await client.connect()
                    connection_retries = 0
                return False
        except Exception as e:
            logger.error(f"Error reconnecting: {e}")
            connection_retries += 1
            return False
    return True

@client.on(events.NewMessage)
async def activity_tracker(event):
    global last_activity_time
    last_activity_time = time.time()

modules = {}
module_dir = 'modules'

if not os.path.exists(module_dir):
    os.makedirs(module_dir)

for filename in os.listdir(module_dir):
    if filename.endswith('.py'):
        module_name = filename[:-3]
        try:
            module = __import__(f'modules.{module_name}', fromlist=['*'])
            module_path = os.path.join(module_dir, filename)
            
            if hasattr(module, 'register_handlers'):
                try:
                    handlers = module.register_handlers(client)
                    
                    module.handlers = handlers
                    logger.info(f"Registered handlers for {module_name}")
                except Exception as e:
                    logger.error(f"Error registering handlers for {module_name}: {str(e)}")
                
            modules[module_name] = module
            logger.info(f"Successfully loaded module: {module_name}")
        except Exception as e:
            logger.error(f"Error loading module {module_name}: {str(e)}")

class HelpModule:
    pass

class InfoModule:
    pass

modules['help'] = HelpModule
modules['info'] = InfoModule

if 'userbot' not in modules and os.path.exists(os.path.join(module_dir, 'userbot.py')):
    try:
        userbot_module = __import__('modules.userbot', fromlist=['*'])
        modules['userbot'] = userbot_module
        logger.info("Manually loaded 'userbot' module")
    except Exception as e:
        logger.error(f"Error manually loading 'userbot' module: {str(e)}")

@client.on(events.NewMessage(pattern=r'\.help'))
async def help_handler(event):
    if not await is_owner(event):
        return  
    
    args = event.message.text.split(' ', 1)
    if len(args) > 1 and args[1].strip():
        module_name = args[1].strip()
        
        if module_name == 'userbot' and module_name not in modules:
            try:
                module_path = os.path.join(module_dir, f"{module_name}.py")
                if os.path.exists(module_path):
                    developer, description, commands = read_module_info(module_path)
                    response = f"<blockquote>⚝ ʍодуᴧь: {module_name}</blockquote>\n\n"
                    response += f"<blockquote>⚝ ᴩᴀзᴩᴀбоᴛчиᴋ: {developer}</blockquote>\n"
                    response += f"<blockquote>⚝ оᴨиᴄᴀниᴇ: {description}</blockquote>\n"
                    
                    if commands:
                        response += "<blockquote>⚝ ᴋоʍᴀнды:</blockquote>\n"
                        for i, cmd in enumerate(commands):
                            cmd = cmd.replace('`', '</code>')
                            cmd = cmd.replace(' - </code>', ' - <code>')
                            if '<code>' not in cmd:
                                cmd = f"<code>{cmd}</code>"
                            
                            response += f"<blockquote>{cmd}</blockquote>"
                            if i < len(commands) - 1:
                                response += "\n"
                    
                    await safe_edit(event, response, parse_mode='html')
                    return
            except Exception as e:
                logger.error(f"Error handling userbot module request: {str(e)}")
        
        if module_name in modules:
            module = modules[module_name]
            
            if module_name == 'userbot':
                module_path = os.path.join(module_dir, f"{module_name}.py")
                developer, description, commands = read_module_info(module_path)
            elif module_name in ['help', 'info']:
                await safe_edit(event, f"<blockquote>⚝ для ᴨᴩоᴄʍоᴛᴩᴀ ʙᴄᴛᴩоᴇнных ᴋоʍᴀнд иᴄᴨоᴧьзуйᴛᴇ <code>.help userbot</code></blockquote>", parse_mode='html')
                return
            else:
                module_path = os.path.join(module_dir, f"{module_name}.py")
                developer, description, commands = read_module_info(module_path)
            
            response = f"<blockquote>⚝ ʍодуᴧь: {module_name}</blockquote>\n\n"
            response += f"<blockquote>⚝ ᴩᴀзᴩᴀбоᴛчиᴋ: {developer}</blockquote>\n"
            response += f"<blockquote>⚝ оᴨиᴄᴀниᴇ: {description}</blockquote>\n"
            
            if commands:
                response += "<blockquote>⚝ ᴋоʍᴀнды:</blockquote>\n"
                for i, cmd in enumerate(commands):
                    cmd = cmd.replace('`', '</code>')
                    cmd = cmd.replace(' - </code>', ' - <code>')
                    if '<code>' not in cmd:
                        cmd = f"<code>{cmd}</code>"
                    
                    response += f"<blockquote>{cmd}</blockquote>"
                    if i < len(commands) - 1:
                        response += "\n"
            
            await safe_edit(event, response, parse_mode='html')
        else:
            await safe_edit(event, f"<blockquote>⚝ ʍодуᴧь {module_name} нᴇ нᴀйдᴇн</blockquote>", parse_mode='html')
    else:
        module_list = "<blockquote>⚝ ᴄᴨиᴄоᴋ ʍодуᴧᴇй:</blockquote>\n\n"
        
        hidden_modules = ['help', 'info']
        sorted_modules = sorted([m for m in modules.keys() if m not in hidden_modules])
        
        if 'userbot' in modules:
            sorted_modules = ['userbot'] + [m for m in sorted_modules if m != 'userbot']
        else:
            sorted_modules = ['userbot'] + sorted_modules
        
        modules_text = "<blockquote>"
        for i, module_name in enumerate(sorted_modules):
            modules_text += f"⚝ {module_name}"
            if i < len(sorted_modules) - 1:
                modules_text += "\n"
        modules_text += "</blockquote>"
        
        module_list += modules_text
        
        await safe_edit(event, module_list, parse_mode='html')

@client.on(events.NewMessage(pattern=r'\.info'))
async def info_handler(event):
    if not await is_owner(event):
        return  
    
    start = time.time()
    message = await safe_edit(event, "<blockquote>⚝ инфо...</blockquote>", parse_mode="html")
    end = time.time()
    
    ping = round((end - start) * 1000, 2)
    
    me = await client.get_me()
    uptime = get_uptime()
    cpu_usage = get_cpu_usage()
    ram_usage = round(get_ram_usage(), 2)
    platform_name = detect_platform()
    
    info_text = f"<blockquote>⚝ ᴏᴡɴᴇʀ: {me.first_name}</blockquote>\n\n"
    
    info_text += "<blockquote>"
    info_text += f"⚝ ᴠᴇʀsɪᴏɴ: {VERSION}\n"
    info_text += f"⚝ ʙʀᴀɴᴄʜ: master\n"
    info_text += f"⚝ ᴘɪɴɢ: {ping}ms\n"
    info_text += f"⚝ ᴜᴘᴛɪᴍᴇ: {uptime}\n"
    info_text += f"⚝ ᴄᴘᴜ ᴜsᴀɢᴇ: {cpu_usage}%\n"
    info_text += f"⚝ ʀᴀᴍ ᴜsᴀɢᴇ: {ram_usage}MB\n"
    info_text += f"⚝ ʜᴏsᴛ: {platform_name}"
    info_text += "</blockquote>"
    
    await event.delete()
    await event.respond(info_text, file="https://envs.sh/7IO.jpg", parse_mode='html')

@client.on(events.NewMessage(pattern=r'\.restart'))
async def restart_handler_main(event):
    """Резервный обработчик для перезапуска юзербота"""
    if not await is_owner(event):
        return
    
    restart_msg = "<blockquote>⚝ ᴨᴇᴩᴇзᴀᴨуᴄᴋ юзᴇᴩбоᴛᴀ...</blockquote>"
    
    try:
        if event.out:
            msg = await event.edit(restart_msg, parse_mode="html")
        else:
            msg = await event.respond(restart_msg, parse_mode="html")
        
        with open('restart_info.json', 'w') as f:
            json.dump({
                'chat_id': event.chat_id,
                'message_id': msg.id,
                'time': time.time()
            }, f)
            
        os.execl(sys.executable, sys.executable, *sys.argv)
    except Exception as e:
        logger.error(f"Error in main restart handler: {e}")
        try:
            error_msg = f"<blockquote>⚝ ошибᴋᴀ ᴨᴩи ᴨᴇᴩᴇзᴀᴨуᴄᴋᴇ: <code>{str(e)}</code></blockquote>"
            await event.respond(error_msg, parse_mode="html")
        except Exception:
            pass

@client.on(events.NewMessage(pattern=r'\.modules'))
async def modules_handler(event):
    """Отображает информацию о модулях"""
    if not await is_owner(event):
        return
    
    try:
        modules_text = "<blockquote>⚝ ᴄᴨиᴄоᴋ ʍодуᴧᴇй: <a href='https://hymodules.arioncheck.ru'>ᴄᴀйᴛ</a></blockquote>"
        
        await safe_edit(event, modules_text, parse_mode="html")
    
    except Exception as e:
        logger.error(f"Error in modules handler: {str(e)}")
        await event.respond(f"<blockquote>⚝ оɯибᴋᴀ: {str(e)}</blockquote>", parse_mode="html")

@client.on(events.NewMessage(pattern=r'\.dlm (.+)'))
async def module_install_handler(event):
    """Устанавливает указанный модуль"""
    if not await is_owner(event):
        return
    
    try:
        module_name = event.pattern_match.group(1).strip()
        
        if not module_name:
            await event.edit("<blockquote>⚝ уᴋᴀжиᴛᴇ нᴀзʙᴀниᴇ ʍодуᴧя</blockquote>", parse_mode="html")
            return
        
        module_path = os.path.join(module_dir, f"{module_name}.py")
        if os.path.exists(module_path):
            await event.edit(f"<blockquote>⚝ ʍодуᴧь {module_name} ужᴇ уᴄᴛᴀноʙᴧᴇн</blockquote>", parse_mode="html")
            return
        
        loading_msg = await event.edit(f"<blockquote>⚝ идᴇᴛ зᴀᴦᴩузᴋᴀ ʍодуᴧя {module_name}...</blockquote>", parse_mode="html")
        
        file_url = f"https://raw.githubusercontent.com/arioncheck/HYModules/main/{module_name}.py"
        
        try:
            response = requests.get(file_url)
            if response.status_code == 200:
                if not os.path.exists(module_dir):
                    os.makedirs(module_dir)
                
                content = response.text.rstrip('\n')
                
                with open(module_path, 'w', encoding='utf-8', newline='') as f:
                    f.write(content)
                
                await loading_msg.edit(f"<blockquote>⚝ ʍодуᴧь {module_name} уᴄᴨᴇɯно уᴄᴛᴀноʙᴧᴇн</blockquote>\n<blockquote>⚝ нᴀᴨиɯиᴛᴇ <code>.restart</code> дᴧя ᴄохᴩᴀнᴇния</blockquote>", parse_mode="html")
            else:
                await loading_msg.edit(f"<blockquote>⚝ ʍодуᴧь {module_name} нᴇ нᴀйдᴇн</blockquote>", parse_mode="html")
        except Exception as e:
            await loading_msg.edit(f"<blockquote>⚝ оɯибᴋᴀ ᴨᴩи зᴀᴦᴩузᴋᴇ ʍодуᴧя: {str(e)}</blockquote>", parse_mode="html")
    
    except Exception as e:
        logger.error(f"Error in module install handler: {str(e)}")
        await event.respond(f"<blockquote>⚝ оɯибᴋᴀ: {str(e)}</blockquote>", parse_mode="html")

@client.on(events.NewMessage(pattern=r'\.ulm (.+)'))
async def module_remove_handler(event):
    """Удаляет указанный модуль"""
    if not await is_owner(event):
        return
    
    try:
        module_name = event.pattern_match.group(1).strip()
        
        if not module_name:
            await event.edit("<blockquote>⚝ уᴋᴀжиᴛᴇ нᴀзʙᴀниᴇ ʍодуᴧя</blockquote>", parse_mode="html")
            return
        
        protected_modules = ['userbot']
        if module_name in protected_modules:
            await event.edit(f"<blockquote>⚝ ʍодуᴧь {module_name} яʙᴧяᴇᴛᴄя ᴄиᴄᴛᴇʍныʍ и нᴇ ʍожᴇᴛ быᴛь удᴀᴧᴇн</blockquote>", parse_mode="html")
            return
        
        module_path = os.path.join(module_dir, f"{module_name}.py")
        if not os.path.exists(module_path):
            await event.edit(f"<blockquote>⚝ ʍодуᴧь {module_name} нᴇ уᴄᴛᴀноʙᴧᴇн</blockquote>", parse_mode="html")
            return
        
        loading_msg = await event.edit(f"<blockquote>⚝ удᴀᴧᴇниᴇ ʍодуᴧя {module_name}...</blockquote>", parse_mode="html")
        
        try:
            os.remove(module_path)
            
            await loading_msg.edit(f"<blockquote>⚝ ʍодуᴧь {module_name} уᴄᴨᴇɯно удᴀᴧᴇн</blockquote>\n<blockquote>⚝ нᴀᴨиɯиᴛᴇ <code>.restart</code> дᴧя ᴄохᴩᴀнᴇния</blockquote>", parse_mode="html")
        except Exception as e:
            await loading_msg.edit(f"<blockquote>⚝ оɯибᴋᴀ ᴨᴩи удᴀᴧᴇнии ʍодуᴧя: {str(e)}</blockquote>", parse_mode="html")
    
    except Exception as e:
        logger.error(f"Error in module remove handler: {str(e)}")
        await event.respond(f"<blockquote>⚝ оɯибᴋᴀ: {str(e)}</blockquote>", parse_mode="html")

@client.on(events.NewMessage(pattern=r'\.lm$'))
async def module_install_from_file_handler(event):
    """Устанавливает модуль из файла"""
    if not await is_owner(event):
        return
    
    try:
        if not event.is_reply:
            await event.edit("<blockquote>⚝ ᴋоʍᴀндᴀ доᴧжнᴀ быᴛь оᴛʙᴇᴛоʍ нᴀ ᴄообщᴇниᴇ ᴄ фᴀйᴧоʍ</blockquote>", parse_mode="html")
            return
        
        reply_msg = await event.get_reply_message()
        
        if not reply_msg.file or not reply_msg.file.name.endswith('.py'):
            await event.edit("<blockquote>⚝ фᴀйᴧ доᴧжᴇн иʍᴇᴛь ᴩᴀᴄɯиᴩᴇниᴇ .py</blockquote>", parse_mode="html")
            return
        
        module_name = os.path.splitext(reply_msg.file.name)[0]
        module_path = os.path.join(module_dir, f"{module_name}.py")
        
        if os.path.exists(module_path):
            await event.edit(f"<blockquote>⚝ ʍодуᴧь {module_name} ужᴇ уᴄᴛᴀноʙᴧᴇн</blockquote>", parse_mode="html")
            return
        
        loading_msg = await event.edit(f"<blockquote>⚝ идᴇᴛ зᴀᴦᴩузᴋᴀ ʍодуᴧя {module_name}...</blockquote>", parse_mode="html")
        
        try:
            file_content = await client.download_media(reply_msg, bytes)
            
            if not os.path.exists(module_dir):
                os.makedirs(module_dir)
            
            with open(module_path, 'wb') as f:
                f.write(file_content)
            
            await loading_msg.edit(f"<blockquote>⚝ ʍодуᴧь {module_name} уᴄᴨᴇɯно уᴄᴛᴀноʙᴧᴇн</blockquote>\n<blockquote>⚝ нᴀᴨиɯиᴛᴇ <code>.restart</code> дᴧя ᴄохᴩᴀнᴇния</blockquote>", parse_mode="html")
        except Exception as e:
            await loading_msg.edit(f"<blockquote>⚝ оɯибᴋᴀ ᴨᴩи зᴀᴦᴩузᴋᴇ ʍодуᴧя: {str(e)}</blockquote>", parse_mode="html")
    
    except Exception as e:
        logger.error(f"Error in module install from file handler: {str(e)}")
        await event.respond(f"<blockquote>⚝ оɯибᴋᴀ: {str(e)}</blockquote>", parse_mode="html")

async def main():
    try:
        print("Запуск авторизации...")
        print("\nПодключение к Telegram...")
        
        client.device_model = "Hyoku"
        client.app_version = VERSION
        
        await client.start(phone=PHONE)
        
        if hasattr(client, 'session') and hasattr(client.session, 'save'):
            client.session.save()
        
        restart_file = 'restart_info.json'
        if os.path.exists(restart_file):
            try:
                with open(restart_file, 'r') as f:
                    restart_info = json.load(f)
                
                chat_id = restart_info.get('chat_id')
                message_id = restart_info.get('message_id')
                was_update = restart_info.get('update', False)
                
                if chat_id and message_id:
                    try:
                        if was_update:
                            commit = restart_info.get('commit', '')
                            commit_msg = restart_info.get('commit_msg', '')
                            update_text = "<blockquote>⚝ юзᴇᴩбоᴛ уᴄᴨᴇɯно обноʙᴧᴇн</blockquote>"
                            
                            if commit:
                                update_text += f"\n<blockquote>⚝ ᴋоʍʍиᴛ: <code>{commit}</code></blockquote>"
                            
                            if commit_msg:
                                update_text += f"\n<blockquote>⚝ ᴄообщᴇниᴇ: {commit_msg}</blockquote>"
                                
                            await client.edit_message(
                                chat_id, 
                                message_id, 
                                update_text,
                                parse_mode="html"
                            )
                        else:
                            await client.edit_message(
                                chat_id, 
                                message_id, 
                                "<blockquote>⚝ юзᴇᴩбоᴛ уᴄᴨᴇɯно ᴨᴇᴩᴇзᴀᴨущᴇн</blockquote>",
                                parse_mode="html"
                            )
                    except Exception as e:
                        logger.error(f"Failed to update restart message: {e}")
                
                os.remove(restart_file)
            except Exception as e:
                logger.error(f"Failed to process restart info: {e}")
        
        try:
            startup_message = "<blockquote>⚝ Юзербот успешно запущен</blockquote>\n<blockquote>⚝ Защита от блокировки аккаунта активна</blockquote>"
            
            try:
                await client.send_message('me', startup_message, file="https://envs.sh/7Ri.png", parse_mode="html")
            except Exception as img_error:
                logger.warning(f"Failed to send startup message with image: {img_error}")
                await client.send_message('me', startup_message, parse_mode="html")
        except Exception as e:
            logger.error(f"Failed to send startup message: {e}")
            
        clear_screen()
        print("""
 _   _ __  __ ____  __  __  __ __ 
| |_| |\\ \\/ // () \\|  |/  /|  |  |
|_| |_| |__| \\____/|__|\\__\\ \\___/ 
""")
            
        print("\nUserbot started")
        
        client.loop.create_task(keep_alive())
        
        await client.run_until_disconnected()
    except KeyboardInterrupt:
        print("\nUserbot остановлен.")
        sys.exit(0)
    except Exception as e:
        print(f"\nОшибка: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    try:
        client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\nUserbot остановлен.")
        sys.exit(0)
    except Exception as e:
        print(f"\nОшибка: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 