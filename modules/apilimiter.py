# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# 🌐 https://github.com/hikariatama/Hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html
# meta developer: @hikarimods
# description: Защита от блокировки аккаунта
# command: .api_fw_protection - `Включить/выключить защиту от блокировки`
# command: .suspend_api_protect <секунды> - `Приостановить защиту на указанное количество секунд`

import asyncio
import io
import json
import logging
import random
import time
import os
from telethon import TelegramClient, events, functions
from telethon.tl.tlobject import TLRequest
from telethon.utils import is_list_like
from userbot import client, is_owner

logger = logging.getLogger(__name__)

GROUPS = [
    "auth",
    "account",
    "users",
    "contacts",
    "messages",
    "updates",
    "photos",
    "upload",
    "help",
    "channels",
    "bots",
    "payments",
    "stickers",
    "phone",
    "langpack",
    "folders",
    "stats",
]

CONSTRUCTORS = {}
for group in GROUPS:
    group_module = getattr(functions, group, None)
    if group_module:
        for item_name in dir(group_module):
            item = getattr(group_module, item_name, None)
            if isinstance(item, type) and issubclass(item, TLRequest) and hasattr(item, "CONSTRUCTOR_ID"):
                constructor_name = item_name.rsplit("Request", 1)[0]
                constructor_name = constructor_name[0].lower() + constructor_name[1:]
                CONSTRUCTORS[constructor_name] = item.CONSTRUCTOR_ID

def register_handlers(client):
    """
    Защита от блокировки аккаунта
    """
    
    config = {
        'time_sample': 15,  
        'threshold': 100,   
        'local_floodwait': 30,  
        'forbidden_methods': [
            "joinChannel", 
            "importChatInvite", 
            "sendReaction", 
            "forwardMessages", 
            "reportSpam", 
            "updatePinnedMessage"
        ],  
    }

    apilimiter_data = {
        'ratelimiter': [],
        'suspend_until': 0,
        'lock': False,
        'is_protected': True, 
    }

    original_call = client._call

    async def new_call(
        sender,
        request,
        ordered=False,
        flood_sleep_threshold=None,
    ):
        await asyncio.sleep(random.randint(1, 5) / 100)
        
        req = (request,) if not is_list_like(request) else request
        for r in req:
            if (
                time.perf_counter() > apilimiter_data['suspend_until']
                and apilimiter_data['is_protected']
                and (
                    r.__module__.rsplit(".", maxsplit=1)[1]
                    in {"messages", "account", "channels"}
                )
            ):
                request_name = type(r).__name__
                apilimiter_data['ratelimiter'] += [(request_name, time.perf_counter())]
                
                apilimiter_data['ratelimiter'] = list(
                    filter(
                        lambda x: time.perf_counter() - x[1] < config['time_sample'],
                        apilimiter_data['ratelimiter'],
                    )
                )
                
                if (
                    len(apilimiter_data['ratelimiter']) > config['threshold']
                    and not apilimiter_data['lock']
                ):
                    apilimiter_data['lock'] = True
                    
                    report = io.BytesIO(
                        json.dumps(
                            apilimiter_data['ratelimiter'],
                            indent=4,
                        ).encode()
                    )
                    report.name = "local_fw_report.json"
                    
                    try:
                        await client.send_file(
                            'me',
                            report,
                            caption=f"<blockquote>⚝ чᴛобы избᴇжᴀᴛь бᴧоᴋиᴩоʙᴋи ᴀᴋᴋᴀунᴛᴀ, юзᴇᴩбоᴛ будᴇᴛ ᴄᴨᴀᴛь {config['local_floodwait']} ᴄᴇᴋунд\n⚝ дᴧя оᴛᴋᴧючᴇния: <code>.api_fw_protection</code></blockquote>",
                            parse_mode="html"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send floodwait message: {e}")
                    
                    time.sleep(config['local_floodwait'])
                    apilimiter_data['lock'] = False
                
                for forbidden in config['forbidden_methods']:
                    if forbidden.lower() in request_name.lower():
                        logger.warning(f"Blocked forbidden request: {request_name}")
                        return None  
        
        return await original_call(sender, request, ordered, flood_sleep_threshold)
    
    async def install_protection():
        await asyncio.sleep(30)  
        client._original_call = original_call
        client._call = new_call
        logger.debug("Successfully installed API ratelimiter")
    
    client.loop.create_task(install_protection())
    
    @client.on(events.NewMessage(pattern=r'\.suspend_api_protect(?:\s+(\d+))?'))
    async def suspend_api_protect_handler(event):
        """Приостановить защиту от блокировки на указанное количество секунд"""
        try:
            if not await is_owner(event) and not event.out:
                return  

            can_edit = event.out
            

            async def send_message(text):
                try:
                    if can_edit:
                        return await event.edit(text, parse_mode="html")
                    else:
                        return await event.respond(text, parse_mode="html")
                except Exception as e:
                    logger.error(f"Error sending message: {str(e)}")
                    return await event.respond(text, parse_mode="html")
            
            args = event.pattern_match.group(1)
            if not args or not args.isdigit():
                await send_message("<blockquote>⚝ нᴇʙᴇᴩный ᴀᴩᴦуʍᴇнᴛ, уᴋᴀжиᴛᴇ ʙᴩᴇʍя ʙ ᴄᴇᴋундᴀх</blockquote>")
                return
            
            seconds = int(args)
            apilimiter_data['suspend_until'] = time.perf_counter() + seconds
            await send_message(f"<blockquote>⚝ зᴀщиᴛᴀ оᴛ бᴧоᴋиᴩоʙᴋи ᴨᴩиоᴄᴛᴀноʙᴧᴇнᴀ нᴀ {seconds} ᴄᴇᴋунд</blockquote>")
            
        except Exception as e:
            logger.error(f"Error in suspend_api_protect handler: {str(e)}")
            try:
                await event.respond(f"<blockquote>⚝ ошибᴋᴀ: <code>{str(e)}</code></blockquote>", parse_mode="html")
            except Exception:
                pass
    
    @client.on(events.NewMessage(pattern=r'\.api_fw_protection'))
    async def api_fw_protection_handler(event):
        """Включить/выключить защиту от блокировки"""
        try:
            if not await is_owner(event) and not event.out:
                return  
            
            can_edit = event.out
            
            async def send_message(text):
                try:
                    if can_edit:
                        return await event.edit(text, parse_mode="html")
                    else:
                        return await event.respond(text, parse_mode="html")
                except Exception as e:
                    logger.error(f"Error sending message: {str(e)}")
                    return await event.respond(text, parse_mode="html")
            
            apilimiter_data['is_protected'] = not apilimiter_data['is_protected']
            
            if apilimiter_data['is_protected']:
                await send_message("<blockquote>⚝ зᴀщиᴛᴀ оᴛ бᴧоᴋиᴩоʙᴋи ʙᴋᴧючᴇнᴀ</blockquote>")
            else:
                await send_message("<blockquote>⚝ зᴀщиᴛᴀ оᴛ бᴧоᴋиᴩоʙᴋи ʙыᴋᴧючᴇнᴀ</blockquote>")
            
        except Exception as e:
            logger.error(f"Error in api_fw_protection handler: {str(e)}")
            try:
                await event.respond(f"<blockquote>⚝ ошибᴋᴀ: <code>{str(e)}</code></blockquote>", parse_mode="html")
            except Exception:
                pass
    
    return [suspend_api_protect_handler, api_fw_protection_handler] 