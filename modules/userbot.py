# meta developer: @qveroz
# description: Основные команды юзербота
# command: .help [модуль] - `Показать список модулей или информацию о конкретном модуле`
# command: .info - `Показать информацию о боте и системе`
# command: .ping - `Проверить скорость отклика бота и время работы`
# command: .hyoku - `Показать информацию о юзерботе Hyoku`
# command: .restart - `Перезапустить юзербот`
# command: .modules - `Показать список доступных модулей для установки`
# command: .dlm название - `Установить указанный модуль с GitHub`
# command: .ulm название - `Удалить указанный модуль`
# command: .lm - `Установить модуль из файла (в ответ на сообщение с файлом .py)`
# command: .ml [название] - `Получить файл модуля и информацию (разработчик, описание)`
# command: .update - `Обновить юзербот до последней версии`

import logging
import time
import os
import re
import json
import platform
import sys
import asyncio
import subprocess
from telethon import events, __version__ as telethon_version
from telethon.errors import MessageIdInvalidError
from userbot import client, get_uptime, is_owner, create_pattern

logger = logging.getLogger(__name__)

PREFIX = "."

UPDATE_CONFIG_FILE = 'update_config.json'
DEFAULT_UPDATE_CONFIG = {
    'last_check_time': 0,
    'check_interval': 10,  
    'last_commit': None
}

def load_update_config():
    """Загрузить конфигурацию обновлений"""
    if os.path.exists(UPDATE_CONFIG_FILE):
        try:
            with open(UPDATE_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                for key in DEFAULT_UPDATE_CONFIG:
                    if key not in config:
                        config[key] = DEFAULT_UPDATE_CONFIG[key]
                return config
        except Exception as e:
            logger.error(f"Ошибка при загрузке конфигурации обновлений: {e}")
    
    return DEFAULT_UPDATE_CONFIG.copy()

def save_update_config(config):
    """Сохранить конфигурацию обновлений"""
    try:
        with open(UPDATE_CONFIG_FILE, 'w') as f:
            json.dump(config, f)
    except Exception as e:
        logger.error(f"Ошибка при сохранении конфигурации обновлений: {e}")

async def check_for_updates():
    """Проверка наличия обновлений на GitHub"""
    logger.info("Проверка обновлений...")
    repo_url = "https://github.com/emsykj/Hyoku.git"
    
    try:
        config = load_update_config()
        
        current_time = time.time()
        if current_time - config['last_check_time'] < config['check_interval']:
            logger.info("Слишком рано для проверки обновлений")
            return
        
        config['last_check_time'] = current_time
        save_update_config(config)
        
        process = subprocess.Popen(
            ["git", "status"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        _, stderr = process.communicate()
        
        if process.returncode != 0:
            subprocess.check_output(["git", "init"])
            subprocess.check_output(["git", "remote", "add", "origin", repo_url])
            try:
                subprocess.check_output(["git", "pull", "origin", "main"], stderr=subprocess.STDOUT)
                current_commit = subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    stderr=subprocess.STDOUT
                ).decode("utf-8").strip()
                config['last_commit'] = current_commit
                save_update_config(config)
            except Exception as e:
                logger.error(f"Ошибка при инициализации репозитория: {e}")
            return
        
        subprocess.check_output(["git", "fetch", "origin", "main"], stderr=subprocess.STDOUT)
        
        remote_commit = subprocess.check_output(
            ["git", "rev-parse", "origin/main"],
            stderr=subprocess.STDOUT
        ).decode("utf-8").strip()
        
        local_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.STDOUT
        ).decode("utf-8").strip()
        
        if not config['last_commit']:
            config['last_commit'] = local_commit
            save_update_config(config)
            return
        
        if remote_commit != local_commit:
            commit_msg = subprocess.check_output(
                ["git", "log", "--format=%B", "-n", "1", remote_commit],
                stderr=subprocess.STDOUT
            ).decode("utf-8").strip()
            
            if remote_commit == config['last_commit']:
                logger.info("Обновление уже было обнаружено ранее")
                return
            
            config['last_commit'] = remote_commit
            save_update_config(config)
            
            update_notification = f"<blockquote>⚝ ноʙоᴇ обноʙᴧᴇниᴇ юзᴇᴩбоᴛᴀ</blockquote>\n"
            update_notification += f"<blockquote>⚝ ᴋоʍʍиᴛ: <code>{remote_commit[:7]}</code></blockquote>\n"
            update_notification += f"<blockquote>⚝ ᴄообщᴇниᴇ: {commit_msg}</blockquote>\n\n"
            update_notification += "<blockquote>⚝ нᴀᴨиɯиᴛᴇ <code>.update</code> чᴛобы обноʙиᴛь юзᴇᴩбоᴛ</blockquote>"
            
            await client.send_file(
                'me',
                file="https://envs.sh/oSH.jpg",
                caption=update_notification,
                parse_mode="html"
            )
            logger.info(f"Отправлено уведомление о новом обновлении: {remote_commit[:7]}")
    except Exception as e:
        logger.error(f"Ошибка при проверке обновлений: {e}")

def get_module_info(module_path):
    """Извлекает мета-информацию из файла модуля"""
    info = {
        'developer': '@qveroz',
        'description': 'No description',
        'commands': []
    }
    
    try:
        with open(module_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('# meta developer:'):
                    info['developer'] = line.replace('# meta developer:', '').strip()
                elif line.startswith('# description:'):
                    info['description'] = line.replace('# description:', '').strip()
                elif line.startswith('# command:'):
                    cmd = line.replace('# command:', '').strip()
                    info['commands'].append(cmd)
                elif line.startswith('#'):
                    continue
                else:
                    break
    except Exception as e:
        logger.error(f"Error reading module info: {str(e)}")
    
    return info

def register_handlers(client):
    """
    Основные команды юзербота
    """
    
    async def start_update_checker():
        await asyncio.sleep(10)  
        while True:
            await check_for_updates()
            await asyncio.sleep(10)  
    
    client.loop.create_task(start_update_checker())
    
    @client.on(events.NewMessage(pattern=create_pattern('ping')))
    async def ping_handler(event):
        """Проверить скорость отклика бота"""
        try:
            if not await is_owner(event):
                return  
            
            start = time.time()
            
            if event.out:
                await event.edit("<blockquote>⚝ ᴨᴩоʙᴇᴩᴋᴀ ᴄᴋоᴩоᴄᴛи оᴛᴋᴧиᴋᴀ...</blockquote>", parse_mode="html")
                message = event
            else:
                message = await event.respond("<blockquote>⚝ ᴨᴩоʙᴇᴩᴋᴀ ᴄᴋоᴩоᴄᴛи оᴛᴋᴧиᴋᴀ...</blockquote>", parse_mode="html")
            
            end = time.time()
            
            ping = round((end - start) * 1000, 2)
            uptime = get_uptime()
            
            response = f"<blockquote>⚝ ᴨинᴦ: <code>{ping}ms</code></blockquote>\n"
            response += f"<blockquote>⚝ ᴀᴨᴛᴀйʍ: <code>{uptime}</code></blockquote>"
            
            await message.edit(response, parse_mode="html")
        except Exception as e:
            logger.error(f"Error in ping handler: {str(e)}")
            try:
                await event.respond(f"<blockquote>⚝ ошибᴋᴀ: <code>{str(e)}</code></blockquote>", parse_mode="html")
            except Exception:
                pass  
    
    @client.on(events.NewMessage(pattern=create_pattern('hyoku')))
    async def hyoku_handler(event):
        """Показать информацию о юзерботе Hyoku"""
        try:
            if not await is_owner(event):
                return
            
            python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            system_version = platform.system() + " " + platform.release()
            VERSION = "1.0.0"
            
            info_text = "<blockquote>⚝ ᴅᴇᴠᴇʟᴏᴘᴇʀ: @qveroz</blockquote>\n\n"
            info_text += "<blockquote>"
            info_text += f"⚝ ʙᴇᴩᴄия: {VERSION}\n"
            info_text += f"⚝ ᴛᴇʟᴇᴛʜᴏɴ: {telethon_version}\n"
            info_text += f"⚝ ᴘʏᴛʜᴏɴ: {python_version}\n"
            info_text += f"⚝ ᴄиᴄᴛᴇʍᴀ: {system_version}"
            info_text += "</blockquote>"
            
            if event.out:
                await event.delete()
                
            try:
                await event.respond(info_text, file="https://envs.sh/7Re.png", parse_mode="html")
            except Exception as img_error:
                logger.warning(f"Failed to send message with image: {img_error}")
                await event.respond(info_text, parse_mode="html")
                
        except Exception as e:
            logger.error(f"Error in hyoku handler: {str(e)}")
            try:
                await event.respond(f"<blockquote>⚝ ошибᴋᴀ: <code>{str(e)}</code></blockquote>", parse_mode="html")
            except Exception:
                pass
    
    @client.on(events.NewMessage(pattern=r'\.restart'))
    async def restart_handler(event):
        """Перезапустить юзербот"""
        try:
            if not await is_owner(event):
                return
                
            restart_msg = "<blockquote>⚝ ᴨᴇᴩᴇзᴀᴨуᴄᴋ юзᴇᴩбоᴛᴀ...</blockquote>"
            
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
                
            logger.info(f"Restarting userbot from chat {event.chat_id}")
            
            await asyncio.sleep(1)
            os.execl(sys.executable, sys.executable, *sys.argv)
                
        except Exception as e:
            logger.error(f"Error in restart handler: {str(e)}")
            try:
                error_msg = f"<blockquote>⚝ ошибᴋᴀ ᴨᴩи ᴨᴇᴩᴇзᴀᴨуᴄᴋᴇ: <code>{str(e)}</code></blockquote>"
                await event.respond(error_msg, parse_mode="html")
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")
    
    @client.on(events.NewMessage(pattern=r'\.ml\s+(.+)'))
    async def ml_handler(event):
        """Отправляет файл модуля и информацию о нем"""
        if not await is_owner(event):
            return
            
        module_name = event.pattern_match.group(1).strip()
        module_dir = 'modules'
        module_path = os.path.join(module_dir, f"{module_name}.py")
        
        if not os.path.exists(module_path):
            await event.edit(f"<blockquote>⚝ ʍодуᴧь <code>{module_name}</code> нᴇ нᴀйдᴇн</blockquote>", parse_mode="html")
            return
            
        try:
            info = get_module_info(module_path)
            
            response = [
                f"<blockquote>⚝ ʍодуᴧь <code>{module_name}</code></blockquote>",
                f"<blockquote>⚝ ᴩᴀзᴩᴀбоᴛчиᴋ: <code>{info['developer']}</code></blockquote>",
                f"<blockquote>⚝ oᴨиᴄᴀниᴇ: {info['description']}</blockquote>"
            ]
            
            await event.delete()
            await event.respond('\n'.join(response), file=module_path, parse_mode="html")
            
        except Exception as e:
            logger.error(f"Error in ml handler: {str(e)}")
            await event.edit(f"<blockquote>⚝ оɯибᴋᴀ: <code>{str(e)}</code></blockquote>", parse_mode="html")
    
    @client.on(events.NewMessage(pattern=create_pattern('update')))
    async def update_handler(event):
        """Обновить юзербот до последней версии"""
        try:
            if not await is_owner(event):
                return
                
            update_msg = "<blockquote>⚝ обноʙᴧᴇниᴇ юзᴇᴩбоᴛᴀ...</blockquote>"
            
            if event.out:
                msg = await event.edit(update_msg, parse_mode="html")
            else:
                msg = await event.respond(update_msg, parse_mode="html")
            
            repo_url = "https://github.com/arioncheck/Hyoku.git"
            
            try:
                process = subprocess.Popen(
                    ["git", "status"], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE
                )
                _, stderr = process.communicate()
                
                if process.returncode != 0:
                    subprocess.check_output(["git", "init"])
                    subprocess.check_output(["git", "remote", "add", "origin", repo_url])
                    subprocess.check_output(["git", "pull", "origin", "main"], stderr=subprocess.STDOUT)
                    
                    current_commit = subprocess.check_output(
                        ["git", "rev-parse", "HEAD"],
                        stderr=subprocess.STDOUT
                    ).decode("utf-8").strip()
                    
                    await msg.edit("<blockquote>⚝ юзᴇᴩбоᴛ уᴄᴨᴇɯно оᴛᴋᴧониᴩоʙᴀн, ᴨᴇᴩᴇзᴀᴨуᴄᴋ...</blockquote>", parse_mode="html")
                    
                    config = load_update_config()
                    config['last_commit'] = current_commit
                    save_update_config(config)
                    
                    with open('restart_info.json', 'w') as f:
                        json.dump({
                            'chat_id': event.chat_id,
                            'message_id': msg.id,
                            'time': time.time(),
                            'update': True,
                            'commit': current_commit[:7],
                            'commit_msg': "Первичная инициализация"
                        }, f)
                    
                    await asyncio.sleep(1)
                    os.execl(sys.executable, sys.executable, *sys.argv)
                    return
                
                current_commit = subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    stderr=subprocess.STDOUT
                ).decode("utf-8").strip()
                
                pull_output = subprocess.check_output(
                    ["git", "pull", "origin", "main"],
                    stderr=subprocess.STDOUT
                ).decode("utf-8").strip()
                
                new_commit = subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    stderr=subprocess.STDOUT
                ).decode("utf-8").strip()
                
                if current_commit == new_commit:
                    await msg.edit("<blockquote>⚝ у ʙᴀᴄ ужᴇ уᴄᴛᴀноʙᴧᴇнᴀ ᴨоᴄᴧᴇдняя ʙᴇᴩᴄия</blockquote>", parse_mode="html")
                    return
                
                commit_msg = subprocess.check_output(
                    ["git", "log", "--format=%B", "-n", "1", new_commit],
                    stderr=subprocess.STDOUT
                ).decode("utf-8").strip()
                
                config = load_update_config()
                config['last_commit'] = new_commit
                save_update_config(config)
                
                update_notification = f"<blockquote>⚝ ноʙоᴇ обноʙᴧᴇниᴇ юзᴇᴩбоᴛᴀ</blockquote>\n"
                update_notification += f"<blockquote>⚝ ᴋоʍʍиᴛ: <code>{new_commit[:7]}</code></blockquote>\n"
                update_notification += f"<blockquote>⚝ ᴄообщᴇниᴇ: {commit_msg}</blockquote>\n\n"
                update_notification += "<blockquote>⚝ нᴀᴨиɯиᴛᴇ <code>.update</code> чᴛобы обноʙиᴛь юзᴇᴩбоᴛ</blockquote>"
                
                await client.send_file(
                    'me',
                    file="https://envs.sh/oSH.jpg",
                    caption=update_notification,
                    parse_mode="html"
                )
                
                await msg.edit("<blockquote>⚝ обноʙᴧᴇниᴇ уᴄᴨᴇɯно зᴀʙᴇᴩɯᴇно, ᴨᴇᴩᴇзᴀᴨуᴄᴋ...</blockquote>", parse_mode="html")
                
                with open('restart_info.json', 'w') as f:
                    json.dump({
                        'chat_id': event.chat_id,
                        'message_id': msg.id,
                        'time': time.time(),
                        'update': True,
                        'commit': new_commit[:7],
                        'commit_msg': commit_msg
                    }, f)
                
                await asyncio.sleep(1)
                os.execl(sys.executable, sys.executable, *sys.argv)
                
            except subprocess.CalledProcessError as e:
                error_output = e.output.decode("utf-8").strip()
                logger.error(f"Git error: {error_output}")
                await msg.edit(f"<blockquote>⚝ ошибᴋᴀ git: <code>{error_output}</code></blockquote>", parse_mode="html")
                
        except Exception as e:
            logger.error(f"Error in update handler: {str(e)}")
            try:
                await event.respond(f"<blockquote>⚝ ошибᴋᴀ ᴨᴩи обноʙᴧᴇнии: <code>{str(e)}</code></blockquote>", parse_mode="html")
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")
    
    return [ping_handler, hyoku_handler, restart_handler, ml_handler, update_handler] 