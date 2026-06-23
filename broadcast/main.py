"""群发消息插件 — 批量向群聊/私聊主动推送消息 (Web 面板操作)

适配自 miaolik/ElainaBot_v2plugins 的旧版「群发.web.py」。
旧版基于 v1 的 PluginManager / MySQL 日志库 / 模拟 MessageEvent 实现;
本版改用 v2 的 register_page / register_route + 主动推送 API (sender.send_to_*),
可用 ID 来源改为读取框架自带的 SQLite 消息日志 (message.db)。
"""

import json
import os
import random
from datetime import datetime, timedelta

from aiohttp import web

from core.base.logger import PLUGIN, get_logger, report_error
from core.message._http import MessageType
from core.message.keyboard import convert_simple_ark_data
from core.plugin.decorators import on_unload
from core.plugin.web_pages import register_page, register_route, unregister_page

__plugin_meta__ = {
    'name': '群发消息',
    'author': 'miaolik',
    'description': '批量发送消息到多个群聊/私聊 (Web 面板)',
    'version': '2.0.0',
    'github': 'https://github.com/miaolik/ElainaBot_v2plugins',
    'license': 'MIT',
}

log = get_logger(PLUGIN, '群发消息')

_PLUGIN_DIR = os.path.dirname(__file__)
_PAGE_FILE = os.path.join(_PLUGIN_DIR, 'page.html')
_DATA_DIR = os.path.join(_PLUGIN_DIR, 'data', 'id')
_REMARK_FILE = os.path.join(_DATA_DIR, 'remarks.json')

# 可用 ID 的时间窗口 (主动消息需要近期有过互动)
_GROUP_WINDOW = timedelta(minutes=5)
_USER_WINDOW = timedelta(hours=1)


# ==================== 备注持久化 ====================

def _load_remarks():
    try:
        if os.path.exists(_REMARK_FILE):
            with open(_REMARK_FILE, encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        log.warning(f'加载备注失败: {e}')
    return {}


def _save_remarks(remarks):
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        with open(_REMARK_FILE, 'w', encoding='utf-8') as f:
            json.dump(remarks, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log.warning(f'保存备注失败: {e}')
        return False


def _remark_key(chat_type, chat_id):
    return f'{chat_type}_{chat_id}'


# ==================== 机器人/发送辅助 ====================

def _get_app():
    from core.application import get_app

    return get_app()


def _all_bots():
    app = _get_app()
    return list(app._bots.values()) if app else []


def _primary_sender():
    bots = _all_bots()
    return bots[0].sender if bots else None


def _parse_ts(ts):
    if not ts:
        return None
    try:
        return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return None


def _collect_recent_chats():
    """从所有机器人的 message.db 聚合近期活跃的群聊/私聊 ID。

    返回 (groups, users), 每项为 {chat_id, last_time(isoformat)}。
    """
    now = datetime.now()
    dates = [now.strftime('%Y-%m-%d'), (now - timedelta(days=1)).strftime('%Y-%m-%d')]
    group_last: dict[str, datetime] = {}
    user_last: dict[str, datetime] = {}

    group_sql = (
        "SELECT group_id AS chat_id, MAX(timestamp) AS last_time FROM log "
        "WHERE direction='receive' AND group_id != '' AND group_id != 'c2c' "
        "GROUP BY group_id"
    )
    user_sql = (
        "SELECT user_id AS chat_id, MAX(timestamp) AS last_time FROM log "
        "WHERE direction='receive' AND user_id != '' AND (group_id = '' OR group_id = 'c2c') "
        "GROUP BY user_id"
    )

    for bot in _all_bots():
        ls = getattr(bot, 'log_service', None)
        if not ls:
            continue
        for date in dates:
            for row in ls.query('message', group_sql, date=date) or []:
                ts = _parse_ts(row.get('last_time'))
                cid = row.get('chat_id')
                if ts and cid and (cid not in group_last or ts > group_last[cid]):
                    group_last[cid] = ts
            for row in ls.query('message', user_sql, date=date) or []:
                ts = _parse_ts(row.get('last_time'))
                cid = row.get('chat_id')
                if ts and cid and (cid not in user_last or ts > user_last[cid]):
                    user_last[cid] = ts

    remarks = _load_remarks()

    groups = [
        {'chat_id': cid, 'last_time': ts.isoformat(), 'remark': remarks.get(_remark_key('group', cid), '')}
        for cid, ts in group_last.items()
        if now - ts <= _GROUP_WINDOW
    ]
    users = [
        {'chat_id': cid, 'last_time': ts.isoformat(), 'remark': remarks.get(_remark_key('user', cid), '')}
        for cid, ts in user_last.items()
        if now - ts <= _USER_WINDOW
    ]
    groups.sort(key=lambda x: x['last_time'], reverse=True)
    users.sort(key=lambda x: x['last_time'], reverse=True)
    return groups, users


async def _send_one(sender, chat_type, chat_id, send_method, data):
    """向单个目标发送一条消息, 返回 (ok, message)。"""
    is_group = chat_type == 'group'

    if send_method in ('text', 'markdown'):
        content = data.get('content', '')
        msg_type = MessageType.MSG_TYPE_TEXT if send_method == 'text' else None
        ok = await _push_text(sender, is_group, chat_id, content, msg_type=msg_type)
    elif send_method == 'template_markdown':
        ok = await _push_template_markdown(sender, is_group, chat_id, data)
    elif send_method == 'image':
        ok = await _push_media(sender, sender.reply_image, is_group, chat_id,
                               data.get('image_url'), data.get('image_text', ''))
    elif send_method == 'voice':
        ok = await _push_media(sender, sender.reply_voice, is_group, chat_id, data.get('voice_url'))
    elif send_method == 'video':
        ok = await _push_media(sender, sender.reply_video, is_group, chat_id, data.get('video_url'))
    elif send_method == 'ark':
        ok = await _push_ark(sender, is_group, chat_id, data)
    else:
        return False, f'不支持的发送方式: {send_method}'

    return (True, '发送成功') if ok else (False, '发送失败')


async def _push_text(sender, is_group, chat_id, content, *, msg_type=None):
    fn = sender.send_to_group if is_group else sender.send_to_user
    ok, _data, _payload = await fn(chat_id, content, msg_type=msg_type)
    return ok


def _push_endpoint(is_group, chat_id):
    return f'/v2/groups/{chat_id}/messages' if is_group else f'/v2/users/{chat_id}/messages'


async def _push_template_markdown(sender, is_group, chat_id, data):
    params = data.get('params', []) or []
    payload = {
        'msg_type': MessageType.MSG_TYPE_MARKDOWN,
        'msg_seq': random.randint(10000, 999999),
        'markdown': {
            'custom_template_id': str(data.get('template', '')),
            'params': [{'key': f'text{i + 1}', 'values': [str(p)]} for i, p in enumerate(params)],
        },
    }
    keyboard_id = (data.get('keyboard_id') or '').strip()
    if keyboard_id:
        payload['keyboard'] = {'id': keyboard_id}
    ok, _data = await sender.post_json(_push_endpoint(is_group, chat_id), payload)
    return ok


async def _push_media(sender, reply_fn, is_group, chat_id, url, content=''):
    if not url:
        return False
    target = {'target_group_id': chat_id} if is_group else {'target_user_id': chat_id}
    data = await reply_fn(None, url, content, **target)
    return data is not None


async def _push_ark(sender, is_group, chat_id, data):
    try:
        ark_type = int(data.get('ark_type', 23))
    except (ValueError, TypeError):
        ark_type = 23
    kv_data = data.get('ark_params', []) or []
    if isinstance(kv_data, list | tuple) and ark_type in (23, 24, 37):
        kv_data = convert_simple_ark_data(ark_type, tuple(kv_data))
    payload = {
        'msg_type': MessageType.MSG_TYPE_ARK,
        'msg_seq': random.randint(10000, 999999),
        'content': '',
        'ark': {'template_id': ark_type, 'kv': kv_data},
    }
    ok, _data = await sender.post_json(_push_endpoint(is_group, chat_id), payload)
    return ok


# ==================== Web 路由 ====================

async def _json_body(request):
    try:
        return await request.json()
    except Exception:
        return {}


@register_route('POST', '/api/ext/broadcast/get_ids')
async def api_get_ids(request):
    try:
        groups, users = _collect_recent_chats()
        return web.json_response({'success': True, 'data': {'groups': groups, 'users': users}})
    except Exception as e:
        report_error(PLUGIN, '群发消息', e)
        return web.json_response({'success': False, 'message': f'获取ID列表失败: {e}'})


@register_route('POST', '/api/ext/broadcast/delete_id')
async def api_delete_id(request):
    body = await _json_body(request)
    chat_type = body.get('chat_type')
    chat_id = body.get('chat_id')
    if not chat_type or not chat_id:
        return web.json_response({'success': False, 'message': '缺少必要参数'})
    # 消息日志由框架自动滚动维护, 这里仅移除其备注 (旧版删 MySQL ID 表)
    remarks = _load_remarks()
    remarks.pop(_remark_key(chat_type, chat_id), None)
    _save_remarks(remarks)
    return web.json_response({'success': True, 'message': 'ID删除成功'})


@register_route('POST', '/api/ext/broadcast/save_remark')
async def api_save_remark(request):
    body = await _json_body(request)
    chat_type = body.get('chat_type')
    chat_id = body.get('chat_id')
    remark = (body.get('remark') or '').strip()
    if not chat_type or not chat_id:
        return web.json_response({'success': False, 'message': '缺少必要参数'})
    remarks = _load_remarks()
    key = _remark_key(chat_type, chat_id)
    if remark:
        remarks[key] = remark
    else:
        remarks.pop(key, None)
    if _save_remarks(remarks):
        return web.json_response({'success': True, 'message': '备注保存成功'})
    return web.json_response({'success': False, 'message': '备注保存失败'})


@register_route('POST', '/api/ext/broadcast/send')
async def api_broadcast_send(request):
    try:
        body = await _json_body(request)
        send_method = body.get('send_method')
        groups = body.get('groups', []) or []
        users = body.get('users', []) or []

        if not send_method:
            return web.json_response({'success': False, 'message': '缺少发送方式'})
        if not groups and not users:
            return web.json_response({'success': False, 'message': '没有选择任何接收者'})

        sender = _primary_sender()
        if not sender:
            return web.json_response({'success': False, 'message': '没有可用的机器人实例'})

        results = []
        success_count = 0
        fail_count = 0

        for chat_type, items in (('group', groups), ('user', users)):
            for item in items:
                chat_id = item.get('chat_id')
                try:
                    ok, message = await _send_one(sender, chat_type, chat_id, send_method, body)
                except Exception as e:
                    ok, message = False, str(e)
                if ok:
                    success_count += 1
                else:
                    fail_count += 1
                results.append({'chat_type': chat_type, 'chat_id': chat_id, 'success': ok, 'message': message})

        return web.json_response({
            'success': True,
            'data': {
                'total': len(groups) + len(users),
                'success_count': success_count,
                'fail_count': fail_count,
                'results': results,
            },
        })
    except Exception as e:
        report_error(PLUGIN, '群发消息', e)
        return web.json_response({'success': False, 'message': f'群发失败: {e}'})


# ==================== 页面注册 ====================

register_page(
    key='broadcast',
    label='群发消息',
    source='plugin',
    source_name='broadcast',
    html_file=_PAGE_FILE,
    icon='broadcast',
)


@on_unload
def _cleanup():
    unregister_page('broadcast')
