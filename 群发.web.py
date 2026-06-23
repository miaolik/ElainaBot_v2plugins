#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import time
import traceback
from datetime import datetime, timedelta
from core.plugin.PluginManager import Plugin

class BroadcastPlugin(Plugin):
    """群发消息插件"""
    priority = 15
    _is_hot_reload = True
    
    # 数据目录
    DATA_DIR = os.path.join(os.path.dirname(__file__), 'data', 'id')
    REMARK_FILE = os.path.join(DATA_DIR, 'remarks.json')
    
    def __init__(self):
        # 确保数据目录存在
        os.makedirs(self.DATA_DIR, exist_ok=True)
        
        # 如果备注文件不存在，创建空文件
        if not os.path.exists(self.REMARK_FILE):
            self._save_remarks({})
    
    @classmethod
    def _load_remarks(cls):
        """加载备注数据"""
        try:
            if os.path.exists(cls.REMARK_FILE):
                with open(cls.REMARK_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"加载备注失败: {str(e)}")
            return {}
    
    @classmethod
    def _save_remarks(cls, remarks):
        """保存备注数据"""
        try:
            os.makedirs(cls.DATA_DIR, exist_ok=True)
            with open(cls.REMARK_FILE, 'w', encoding='utf-8') as f:
                json.dump(remarks, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存备注失败: {str(e)}")
            return False
    
    @classmethod
    def _get_remark_key(cls, chat_type, chat_id):
        """生成备注的键名"""
        return f"{chat_type}_{chat_id}"
    
    @classmethod
    def get_regex_handlers(cls):
        # 不需要消息处理器，只提供Web界面
        return {}
    
    @classmethod
    def get_web_routes(cls):
        """注册Web路由"""
        return {
            'path': 'broadcast',
            'menu_name': '群发消息',
            'menu_icon': 'bi-broadcast',
            'description': '批量发送消息到多个群聊/私聊',
            'handler': 'render_page',
            'priority': 45,
            'api_routes': [
                {
                    'path': '/api/broadcast/get_ids',
                    'handler': 'api_get_ids',
                    'methods': ['POST'],
                    'require_auth': True,
                    'require_token': True
                },
                {
                    'path': '/api/broadcast/delete_id',
                    'handler': 'api_delete_id',
                    'methods': ['POST'],
                    'require_auth': True,
                    'require_token': True
                },
                {
                    'path': '/api/broadcast/save_remark',
                    'handler': 'api_save_remark',
                    'methods': ['POST'],
                    'require_auth': True,
                    'require_token': True
                },
                {
                    'path': '/api/broadcast/send',
                    'handler': 'api_broadcast_send',
                    'methods': ['POST'],
                    'require_auth': True,
                    'require_token': True
                }
            ]
        }
    
    @classmethod
    def render_page(cls):
        """渲染Web页面"""
        html = """
<div class="container-fluid mt-4">
    <div class="row">
        <div class="col-12">
            <div class="card">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h5 class="mb-0"><i class="bi bi-broadcast me-2"></i>群发消息</h5>
                    <button class="btn btn-primary btn-sm" onclick="fetchIds()">
                        <i class="bi bi-download"></i> 获取可用ID
                    </button>
                </div>
                <div class="card-body">
                    <!-- ID列表区域 -->
                    <div class="row mb-4">
                        <div class="col-md-6">
                            <div class="card">
                                <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center">
                                    <span><i class="bi bi-people-fill"></i> 群聊列表 (<span id="group-count">0</span>)</span>
                                    <div>
                                        <button class="btn btn-sm btn-light" onclick="selectAllGroups()">全选</button>
                                        <button class="btn btn-sm btn-light" onclick="clearAllGroups()">清空</button>
                                    </div>
                                </div>
                                <div class="card-body" style="max-height: 400px; overflow-y: auto;">
                                    <div id="group-list" class="list-group">
                                        <div class="text-muted text-center p-3">点击"获取可用ID"按钮加载群聊列表</div>
                                    </div>
                                </div>
                                <div class="card-footer text-muted small">
                                    <i class="bi bi-info-circle"></i> 点击ID可编辑备注
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="card">
                                <div class="card-header bg-success text-white d-flex justify-content-between align-items-center">
                                    <span><i class="bi bi-person-fill"></i> 私聊列表 (<span id="user-count">0</span>)</span>
                                    <div>
                                        <button class="btn btn-sm btn-light" onclick="selectAllUsers()">全选</button>
                                        <button class="btn btn-sm btn-light" onclick="clearAllUsers()">清空</button>
                                    </div>
                                </div>
                                <div class="card-body" style="max-height: 400px; overflow-y: auto;">
                                    <div id="user-list" class="list-group">
                                        <div class="text-muted text-center p-3">点击"获取可用ID"按钮加载私聊列表</div>
                                    </div>
                                </div>
                                <div class="card-footer text-muted small">
                                    <i class="bi bi-info-circle"></i> 点击ID可编辑备注
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 消息编辑区域 -->
                    <div class="card mb-3">
                        <div class="card-header bg-info text-white">
                            <i class="bi bi-pencil-square"></i> 消息内容
                        </div>
                        <div class="card-body">
                            <div class="mb-3">
                                <label class="form-label">发送方式</label>
                                <select class="form-select" id="send-method" onchange="updateSendMethodUI()">
                                    <option value="text">普通文本</option>
                                    <option value="markdown">原生Markdown</option>
                                    <option value="template_markdown">模板Markdown</option>
                                    <option value="image">图片消息</option>
                                    <option value="voice">语音消息</option>
                                    <option value="video">视频消息</option>
                                    <option value="ark">ARK卡片</option>
                                </select>
                            </div>
                            
                            <!-- 文本/Markdown内容 -->
                            <div id="text-content-group">
                                <label class="form-label">消息内容</label>
                                <textarea class="form-control" id="message-content" rows="6" placeholder="请输入要群发的消息内容"></textarea>
                            </div>
                            
                            <!-- 模板Markdown -->
                            <div id="template-markdown-group" style="display: none;">
                                <div class="mb-3">
                                    <label class="form-label">模板ID</label>
                                    <input type="text" class="form-control" id="template-id" placeholder="例如: 1">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">模板参数（每行一个）</label>
                                    <textarea class="form-control" id="template-params" rows="4" placeholder="参数1\n参数2\n参数3"></textarea>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">按钮ID（可选）</label>
                                    <input type="text" class="form-control" id="keyboard-id" placeholder="例如: 102321943_1752737844">
                                </div>
                            </div>
                            
                            <!-- 图片消息 -->
                            <div id="image-group" style="display: none;">
                                <div class="mb-3">
                                    <label class="form-label">图片URL</label>
                                    <input type="text" class="form-control" id="image-url" placeholder="https://example.com/image.jpg">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">图片描述（可选）</label>
                                    <input type="text" class="form-control" id="image-text" placeholder="图片描述文本">
                                </div>
                            </div>
                            
                            <!-- 语音消息 -->
                            <div id="voice-group" style="display: none;">
                                <label class="form-label">语音URL</label>
                                <input type="text" class="form-control" id="voice-url" placeholder="https://example.com/voice.mp3">
                            </div>
                            
                            <!-- 视频消息 -->
                            <div id="video-group" style="display: none;">
                                <label class="form-label">视频URL</label>
                                <input type="text" class="form-control" id="video-url" placeholder="https://example.com/video.mp4">
                            </div>
                            
                            <!-- ARK卡片 -->
                            <div id="ark-group" style="display: none;">
                                <div class="mb-3">
                                    <label class="form-label">ARK类型</label>
                                    <select class="form-select" id="ark-type">
                                        <option value="23">列表卡片 (23)</option>
                                        <option value="24">信息卡片 (24)</option>
                                        <option value="37">通知卡片 (37)</option>
                                    </select>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">ARK参数（每行一个，数组用括号）</label>
                                    <textarea class="form-control" id="ark-params" rows="4" placeholder="参数1\n参数2\n(项1,链接1)\n(项2,链接2)"></textarea>
                                </div>
                            </div>
                            
                            <div class="alert alert-warning mt-3">
                                <i class="bi bi-exclamation-triangle"></i> 
                                <strong>注意：</strong>群发功能会向所有选中的ID发送消息，请谨慎使用！
                            </div>
                        </div>
                    </div>
                    
                    <!-- 发送按钮 -->
                    <div class="text-end">
                        <button class="btn btn-lg btn-success" onclick="sendBroadcast()">
                            <i class="bi bi-send-fill"></i> 开始群发
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- 发送进度模态框 -->
<div class="modal fade" id="progressModal" tabindex="-1" data-bs-backdrop="static">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">群发进度</h5>
            </div>
            <div class="modal-body">
                <div class="progress mb-3">
                    <div id="progress-bar" class="progress-bar progress-bar-striped progress-bar-animated" 
                         role="progressbar" style="width: 0%">0%</div>
                </div>
                <div id="progress-text" class="text-center">准备发送...</div>
                <div id="progress-details" class="mt-3" style="max-height: 200px; overflow-y: auto; font-size: 0.9rem;">
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" id="close-progress-btn" disabled>关闭</button>
            </div>
        </div>
    </div>
</div>
"""
        
        script = """
let groupIds = [];
let userIds = [];
let progressModal = null;

// 初始化模态框
setTimeout(function() {
    const progressModalEl = document.getElementById('progressModal');
    if (progressModalEl) {
        progressModal = new bootstrap.Modal(progressModalEl);
    }
}, 100);

function fetchIds() {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    
    showLoading();
    
    fetch(`/web/api/plugin/broadcast/get_ids?token=${encodeURIComponent(token)}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            groupIds = data.data.groups || [];
            userIds = data.data.users || [];
            
            renderGroupList();
            renderUserList();
            
            showSuccess(`成功获取 ${groupIds.length} 个群聊和 ${userIds.length} 个私聊`);
        } else {
            showError('获取ID失败: ' + data.message);
        }
    })
    .catch(error => {
        showError('网络错误: ' + error.message);
    });
}

function renderGroupList() {
    const listDiv = document.getElementById('group-list');
    document.getElementById('group-count').textContent = groupIds.length;
    
    if (groupIds.length === 0) {
        listDiv.innerHTML = '<div class="text-muted text-center p-3">暂无可用的群聊ID</div>';
        return;
    }
    
    let html = '';
    groupIds.forEach((item, index) => {
        const timeStr = new Date(item.last_time).toLocaleString('zh-CN');
        const remark = item.remark || '';
        const remarkDisplay = remark ? `<span class="badge bg-info ms-2">${remark}</span>` : '';
        
        html += `
            <div class="list-group-item d-flex justify-content-between align-items-center">
                <div class="form-check flex-grow-1">
                    <input class="form-check-input group-checkbox" type="checkbox" value="${index}" id="group-${index}" checked>
                    <label class="form-check-label" for="group-${index}">
                        <strong onclick="editRemark('group', ${index})" style="cursor: pointer; text-decoration: underline;" title="点击编辑备注">${item.chat_id}</strong>
                        ${remarkDisplay}
                        <br><small class="text-muted">最后消息: ${timeStr}</small>
                    </label>
                </div>
                <button class="btn btn-sm btn-outline-danger" onclick="removeGroup(${index})">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        `;
    });
    listDiv.innerHTML = html;
}

function renderUserList() {
    const listDiv = document.getElementById('user-list');
    document.getElementById('user-count').textContent = userIds.length;
    
    if (userIds.length === 0) {
        listDiv.innerHTML = '<div class="text-muted text-center p-3">暂无可用的私聊ID</div>';
        return;
    }
    
    let html = '';
    userIds.forEach((item, index) => {
        const timeStr = new Date(item.last_time).toLocaleString('zh-CN');
        const remark = item.remark || '';
        const remarkDisplay = remark ? `<span class="badge bg-info ms-2">${remark}</span>` : '';
        
        html += `
            <div class="list-group-item d-flex justify-content-between align-items-center">
                <div class="form-check flex-grow-1">
                    <input class="form-check-input user-checkbox" type="checkbox" value="${index}" id="user-${index}" checked>
                    <label class="form-check-label" for="user-${index}">
                        <strong onclick="editRemark('user', ${index})" style="cursor: pointer; text-decoration: underline;" title="点击编辑备注">${item.chat_id}</strong>
                        ${remarkDisplay}
                        <br><small class="text-muted">最后消息: ${timeStr}</small>
                    </label>
                </div>
                <button class="btn btn-sm btn-outline-danger" onclick="removeUser(${index})">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        `;
    });
    listDiv.innerHTML = html;
}

function removeGroup(index) {
    if (confirm('确定要删除这个群聊ID吗？')) {
        const chatId = groupIds[index].chat_id;
        deleteIdFromDB('group', chatId, () => {
            groupIds.splice(index, 1);
            renderGroupList();
            showSuccess('已删除群聊ID');
        });
    }
}

function removeUser(index) {
    if (confirm('确定要删除这个私聊ID吗？')) {
        const chatId = userIds[index].chat_id;
        deleteIdFromDB('user', chatId, () => {
            userIds.splice(index, 1);
            renderUserList();
            showSuccess('已删除私聊ID');
        });
    }
}

function deleteIdFromDB(chatType, chatId, callback) {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    
    fetch(`/web/api/plugin/broadcast/delete_id?token=${encodeURIComponent(token)}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            chat_type: chatType,
            chat_id: chatId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            callback();
        } else {
            showError('删除失败: ' + data.message);
        }
    })
    .catch(error => {
        showError('网络错误: ' + error.message);
    });
}

function selectAllGroups() {
    document.querySelectorAll('.group-checkbox').forEach(cb => cb.checked = true);
}

function clearAllGroups() {
    document.querySelectorAll('.group-checkbox').forEach(cb => cb.checked = false);
}

function selectAllUsers() {
    document.querySelectorAll('.user-checkbox').forEach(cb => cb.checked = true);
}

function clearAllUsers() {
    document.querySelectorAll('.user-checkbox').forEach(cb => cb.checked = false);
}

function updateSendMethodUI() {
    const method = document.getElementById('send-method').value;
    
    // 隐藏所有组
    document.getElementById('text-content-group').style.display = 'none';
    document.getElementById('template-markdown-group').style.display = 'none';
    document.getElementById('image-group').style.display = 'none';
    document.getElementById('voice-group').style.display = 'none';
    document.getElementById('video-group').style.display = 'none';
    document.getElementById('ark-group').style.display = 'none';
    
    // 显示对应的组
    if (method === 'text' || method === 'markdown') {
        document.getElementById('text-content-group').style.display = 'block';
    } else if (method === 'template_markdown') {
        document.getElementById('template-markdown-group').style.display = 'block';
    } else if (method === 'image') {
        document.getElementById('image-group').style.display = 'block';
    } else if (method === 'voice') {
        document.getElementById('voice-group').style.display = 'block';
    } else if (method === 'video') {
        document.getElementById('video-group').style.display = 'block';
    } else if (method === 'ark') {
        document.getElementById('ark-group').style.display = 'block';
    }
}

function sendBroadcast() {
    // 获取选中的ID
    const selectedGroups = [];
    const selectedUsers = [];
    
    document.querySelectorAll('.group-checkbox:checked').forEach(cb => {
        selectedGroups.push(groupIds[parseInt(cb.value)]);
    });
    
    document.querySelectorAll('.user-checkbox:checked').forEach(cb => {
        selectedUsers.push(userIds[parseInt(cb.value)]);
    });
    
    const totalCount = selectedGroups.length + selectedUsers.length;
    
    if (totalCount === 0) {
        showError('请至少选择一个群聊或私聊');
        return;
    }
    
    // 确认发送
    if (!confirm(`确定要向 ${selectedGroups.length} 个群聊和 ${selectedUsers.length} 个私聊发送消息吗？`)) {
        return;
    }
    
    // 构建发送数据
    const sendMethod = document.getElementById('send-method').value;
    const sendData = {
        send_method: sendMethod,
        groups: selectedGroups,
        users: selectedUsers
    };
    
    // 根据发送方式添加对应的数据
    if (sendMethod === 'text' || sendMethod === 'markdown') {
        const content = document.getElementById('message-content').value.trim();
        if (!content) {
            showError('请输入消息内容');
            return;
        }
        sendData.content = content;
    } else if (sendMethod === 'template_markdown') {
        const template = document.getElementById('template-id').value.trim();
        const paramsText = document.getElementById('template-params').value.trim();
        if (!template || !paramsText) {
            showError('请输入模板ID和参数');
            return;
        }
        sendData.template = template;
        sendData.params = paramsText.split('\\n').map(p => p.trim()).filter(p => p);
        sendData.keyboard_id = document.getElementById('keyboard-id').value.trim();
    } else if (sendMethod === 'image') {
        const imageUrl = document.getElementById('image-url').value.trim();
        if (!imageUrl) {
            showError('请输入图片URL');
            return;
        }
        sendData.image_url = imageUrl;
        sendData.image_text = document.getElementById('image-text').value.trim();
    } else if (sendMethod === 'voice') {
        const voiceUrl = document.getElementById('voice-url').value.trim();
        if (!voiceUrl) {
            showError('请输入语音URL');
            return;
        }
        sendData.voice_url = voiceUrl;
    } else if (sendMethod === 'video') {
        const videoUrl = document.getElementById('video-url').value.trim();
        if (!videoUrl) {
            showError('请输入视频URL');
            return;
        }
        sendData.video_url = videoUrl;
    } else if (sendMethod === 'ark') {
        const arkType = document.getElementById('ark-type').value;
        const paramsText = document.getElementById('ark-params').value.trim();
        if (!paramsText) {
            showError('请输入ARK参数');
            return;
        }
        sendData.ark_type = arkType;
        sendData.ark_params = paramsText.split('\\n').map(p => p.trim()).filter(p => p);
    }
    
    // 显示进度模态框
    if (progressModal) {
        progressModal.show();
    }
    document.getElementById('close-progress-btn').disabled = true;
    document.getElementById('progress-bar').style.width = '0%';
    document.getElementById('progress-bar').textContent = '0%';
    document.getElementById('progress-text').textContent = '准备发送...';
    document.getElementById('progress-details').innerHTML = '';
    
    // 发送请求
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    
    fetch(`/web/api/plugin/broadcast/send?token=${encodeURIComponent(token)}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(sendData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const result = data.data;
            const successCount = result.success_count || 0;
            const failCount = result.fail_count || 0;
            const total = result.total || 0;
            
            // 更新进度
            const percentage = Math.round((successCount + failCount) / total * 100);
            document.getElementById('progress-bar').style.width = percentage + '%';
            document.getElementById('progress-bar').textContent = percentage + '%';
            document.getElementById('progress-text').textContent = 
                `发送完成！成功: ${successCount}, 失败: ${failCount}`;
            
            // 显示详细结果
            let detailsHtml = '<div class="alert alert-info">详细结果：</div>';
            if (result.results) {
                result.results.forEach(r => {
                    const statusClass = r.success ? 'text-success' : 'text-danger';
                    const statusIcon = r.success ? '✓' : '✗';
                    detailsHtml += `<div class="${statusClass}">${statusIcon} ${r.chat_type === 'group' ? '群聊' : '私聊'}: ${r.chat_id} - ${r.message}</div>`;
                });
            }
            document.getElementById('progress-details').innerHTML = detailsHtml;
            
            document.getElementById('close-progress-btn').disabled = false;
            
            if (failCount === 0) {
                showSuccess('群发完成！所有消息发送成功');
            } else {
                showWarning(`群发完成！${successCount} 条成功，${failCount} 条失败`);
            }
        } else {
            document.getElementById('progress-text').textContent = '发送失败: ' + data.message;
            document.getElementById('close-progress-btn').disabled = false;
            showError('群发失败: ' + data.message);
        }
    })
    .catch(error => {
        document.getElementById('progress-text').textContent = '网络错误: ' + error.message;
        document.getElementById('close-progress-btn').disabled = false;
        showError('网络错误: ' + error.message);
    });
}

function editRemark(type, index) {
    const item = type === 'group' ? groupIds[index] : userIds[index];
    const currentRemark = item.remark || '';
    
    const newRemark = prompt(`编辑备注\\n\\nID: ${item.chat_id}\\n\\n请输入备注:`, currentRemark);
    
    // 如果用户点击取消，返回null
    if (newRemark === null) {
        return;
    }
    
    // 保存备注（允许空字符串，表示删除备注）
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    
    fetch(`/web/api/plugin/broadcast/save_remark?token=${encodeURIComponent(token)}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            chat_type: type,
            chat_id: item.chat_id,
            remark: newRemark.trim()
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // 更新本地数据
            item.remark = newRemark.trim();
            
            // 重新渲染列表
            if (type === 'group') {
                renderGroupList();
            } else {
                renderUserList();
            }
            
            showSuccess(newRemark.trim() ? '备注已保存' : '备注已清除');
        } else {
            showError('保存备注失败: ' + data.message);
        }
    })
    .catch(error => {
        showError('网络错误: ' + error.message);
    });
}

function showSuccess(message) {
    alert(message);
}

function showError(message) {
    alert(message);
}

function showWarning(message) {
    alert(message);
}

function showLoading() {
    // 可以添加加载动画
}

// 初始化
updateSendMethodUI();
"""
        
        css = """
.list-group-item {
    border-left: 3px solid transparent;
    transition: all 0.2s;
}

.list-group-item:hover {
    background-color: #f8f9fa;
    border-left-color: #0d6efd;
}

.form-check-input:checked ~ .form-check-label {
    font-weight: 600;
}

#progress-details {
    font-family: monospace;
}

.progress {
    height: 25px;
}

.progress-bar {
    font-size: 14px;
    font-weight: 600;
}

.badge.bg-info {
    font-size: 0.75rem;
    padding: 0.25em 0.6em;
    font-weight: normal;
}

.form-check-label strong:hover {
    color: #0d6efd;
}
"""
        
        return {
            'html': html,
            'script': script,
            'css': css
        }
    
    @classmethod
    def api_get_ids(cls, request_data):
        """获取可用的ID列表"""
        try:
            from function.log_db import LogDatabasePool
            from pymysql.cursors import DictCursor
            from config import LOG_DB_CONFIG
            
            log_db_pool = LogDatabasePool()
            connection = log_db_pool.get_connection()
            
            if not connection:
                return {'success': False, 'message': '数据库连接失败'}
            
            try:
                cursor = connection.cursor(DictCursor)
                
                # 获取表前缀
                table_prefix = LOG_DB_CONFIG.get('table_prefix', 'Mlog_')
                id_table_name = f'{table_prefix}id'
                
                # 检查ID表是否存在
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE() 
                    AND table_name = %s
                """, (id_table_name,))
                
                if cursor.fetchone()['count'] == 0:
                    return {'success': False, 'message': 'ID表不存在'}
                
                # 计算时间限制
                now = datetime.now()
                group_time_limit = now - timedelta(minutes=5)  # 群聊5分钟
                user_time_limit = now - timedelta(hours=1)     # 私聊1小时
                
                # 获取群聊ID（排除超过5分钟的）
                cursor.execute(f"""
                    SELECT chat_id, last_message_id, timestamp as last_time
                    FROM {id_table_name}
                    WHERE chat_type = 'group' 
                    AND timestamp >= %s
                    ORDER BY timestamp DESC
                """, (group_time_limit,))
                groups = cursor.fetchall()
                
                # 获取私聊ID（排除超过1小时的）
                cursor.execute(f"""
                    SELECT chat_id, last_message_id, timestamp as last_time
                    FROM {id_table_name}
                    WHERE chat_type = 'user' 
                    AND timestamp >= %s
                    ORDER BY timestamp DESC
                """, (user_time_limit,))
                users = cursor.fetchall()
                
                # 从JSON文件加载备注
                remarks = cls._load_remarks()
                
                # 格式化数据
                group_list = []
                for g in groups:
                    remark_key = cls._get_remark_key('group', g['chat_id'])
                    group_list.append({
                        'chat_id': g['chat_id'],
                        'last_message_id': g['last_message_id'],
                        'last_time': g['last_time'].isoformat() if g['last_time'] else '',
                        'remark': remarks.get(remark_key, '')
                    })
                
                user_list = []
                for u in users:
                    remark_key = cls._get_remark_key('user', u['chat_id'])
                    user_list.append({
                        'chat_id': u['chat_id'],
                        'last_message_id': u['last_message_id'],
                        'last_time': u['last_time'].isoformat() if u['last_time'] else '',
                        'remark': remarks.get(remark_key, '')
                    })
                
                return {
                    'success': True,
                    'data': {
                        'groups': group_list,
                        'users': user_list
                    }
                }
                
            finally:
                cursor.close()
                log_db_pool.release_connection(connection)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'获取ID列表失败: {str(e)}'}
    
    @classmethod
    def api_delete_id(cls, request_data):
        """从数据库删除指定ID"""
        try:
            chat_type = request_data.get('chat_type')
            chat_id = request_data.get('chat_id')
            
            if not chat_type or not chat_id:
                return {'success': False, 'message': '缺少必要参数'}
            
            from function.log_db import LogDatabasePool
            from pymysql.cursors import DictCursor
            from config import LOG_DB_CONFIG
            
            log_db_pool = LogDatabasePool()
            connection = log_db_pool.get_connection()
            
            if not connection:
                return {'success': False, 'message': '数据库连接失败'}
            
            try:
                cursor = connection.cursor(DictCursor)
                
                # 获取表前缀
                table_prefix = LOG_DB_CONFIG.get('table_prefix', 'Mlog_')
                id_table_name = f'{table_prefix}id'
                
                # 删除ID记录
                cursor.execute(f"""
                    DELETE FROM {id_table_name}
                    WHERE chat_type = %s AND chat_id = %s
                """, (chat_type, chat_id))
                
                connection.commit()
                
                return {'success': True, 'message': 'ID删除成功'}
                
            finally:
                cursor.close()
                log_db_pool.release_connection(connection)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'删除ID失败: {str(e)}'}
    
    @classmethod
    def api_save_remark(cls, request_data):
        """保存ID备注"""
        try:
            chat_type = request_data.get('chat_type')
            chat_id = request_data.get('chat_id')
            remark = request_data.get('remark', '').strip()
            
            if not chat_type or not chat_id:
                return {'success': False, 'message': '缺少必要参数'}
            
            # 加载现有备注
            remarks = cls._load_remarks()
            
            # 生成备注键名
            remark_key = cls._get_remark_key(chat_type, chat_id)
            
            # 保存或删除备注
            if remark:
                remarks[remark_key] = remark
            else:
                # 如果备注为空，删除该条记录
                if remark_key in remarks:
                    del remarks[remark_key]
            
            # 保存到文件
            if cls._save_remarks(remarks):
                return {'success': True, 'message': '备注保存成功'}
            else:
                return {'success': False, 'message': '备注保存失败'}
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'保存备注失败: {str(e)}'}
    
    @classmethod
    def api_broadcast_send(cls, request_data):
        """执行群发"""
        try:
            send_method = request_data.get('send_method')
            groups = request_data.get('groups', [])
            users = request_data.get('users', [])
            
            if not send_method:
                return {'success': False, 'message': '缺少发送方式'}
            
            total_count = len(groups) + len(users)
            if total_count == 0:
                return {'success': False, 'message': '没有选择任何接收者'}
            
            # 导入MessageEvent
            from core.event.MessageEvent import MessageEvent
            
            success_count = 0
            fail_count = 0
            results = []
            
            # 向群聊发送
            for group in groups:
                try:
                    # 创建模拟事件
                    mock_data = {
                        'd': {
                            'id': group['last_message_id'],
                            'group_id': group['chat_id'],
                            'author': {'id': '2218872014'},
                            'content': '',
                            'timestamp': group['last_time']
                        },
                        'id': group['last_message_id'],
                        't': 'GROUP_AT_MESSAGE_CREATE'
                    }
                    
                    event = MessageEvent(mock_data, skip_recording=True)
                    message_id = cls._send_message(event, send_method, request_data)
                    
                    if message_id:
                        success_count += 1
                        results.append({
                            'chat_type': 'group',
                            'chat_id': group['chat_id'],
                            'success': True,
                            'message': '发送成功'
                        })
                    else:
                        fail_count += 1
                        results.append({
                            'chat_type': 'group',
                            'chat_id': group['chat_id'],
                            'success': False,
                            'message': '发送失败'
                        })
                except Exception as e:
                    fail_count += 1
                    results.append({
                        'chat_type': 'group',
                        'chat_id': group['chat_id'],
                        'success': False,
                        'message': str(e)
                    })
            
            # 向私聊发送
            for user in users:
                try:
                    # 创建模拟事件
                    mock_data = {
                        'd': {
                            'id': user['last_message_id'],
                            'author': {'id': user['chat_id']},
                            'content': '',
                            'timestamp': user['last_time']
                        },
                        'id': user['last_message_id'],
                        't': 'C2C_MESSAGE_CREATE'
                    }
                    
                    event = MessageEvent(mock_data, skip_recording=True)
                    message_id = cls._send_message(event, send_method, request_data)
                    
                    if message_id:
                        success_count += 1
                        results.append({
                            'chat_type': 'user',
                            'chat_id': user['chat_id'],
                            'success': True,
                            'message': '发送成功'
                        })
                    else:
                        fail_count += 1
                        results.append({
                            'chat_type': 'user',
                            'chat_id': user['chat_id'],
                            'success': False,
                            'message': '发送失败'
                        })
                except Exception as e:
                    fail_count += 1
                    results.append({
                        'chat_type': 'user',
                        'chat_id': user['chat_id'],
                        'success': False,
                        'message': str(e)
                    })
            
            return {
                'success': True,
                'data': {
                    'total': total_count,
                    'success_count': success_count,
                    'fail_count': fail_count,
                    'results': results
                }
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'群发失败: {str(e)}'}
    
    @staticmethod
    def _send_message(event, send_method, data):
        """发送单条消息"""
        try:
            if send_method == 'text':
                return event.reply(data.get('content', ''), use_markdown=False)
            elif send_method == 'markdown':
                return event.reply(data.get('content', ''), use_markdown=True)
            elif send_method == 'template_markdown':
                return event.reply_markdown(
                    data.get('template'),
                    tuple(data.get('params', [])),
                    data.get('keyboard_id')
                )
            elif send_method == 'image':
                return event.reply_image(
                    data.get('image_url'),
                    data.get('image_text', '')
                )
            elif send_method == 'voice':
                return event.reply_voice(data.get('voice_url'))
            elif send_method == 'video':
                return event.reply_video(data.get('video_url'))
            elif send_method == 'ark':
                return event.reply_ark(
                    data.get('ark_type'),
                    tuple(data.get('ark_params', []))
                )
            else:
                return None
        except Exception as e:
            print(f"发送消息失败: {str(e)}")
            return None

