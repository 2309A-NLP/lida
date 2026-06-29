// API基础URL
const API_BASE = 'http://localhost:8091';

// 全局状态
let currentWorkOrders = [];
let selectedWorkOrder = null;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    loadStatistics();
    loadWorkOrders();

    document.getElementById('chatInput').addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    setInterval(() => {
        loadStatistics();
        loadWorkOrders();
    }, 30000);
});

// 发送消息
async function sendMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message) return;

    addMessageToChat('用户', message, 'user');
    input.value = '';

    try {
        const response = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message, work_order_id: selectedWorkOrder, user_name: '用户' })
        });
        if (!response.ok) throw new Error('网络请求失败');
        const data = await response.json();
        addMessageToChat('AI助手', data.message, 'bot');
        if (data.work_order_created) {
            loadWorkOrders();
            loadStatistics();
            selectedWorkOrder = data.work_order_id;
        }
    } catch (error) {
        console.error('发送消息失败:', error);
        addMessageToChat('系统', '抱歉，消息发送失败，请稍后重试。', 'system');
    }
}

// 添加消息到聊天区域
function addMessageToChat(sender, message, type) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;
    const now = new Date();
    const timeStr = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    let displayMessage = escapeHtml(message);
    messageDiv.innerHTML = `
        <div class="message-content">
            <strong>${escapeHtml(sender)}：</strong>
            <p style="white-space:pre-line;">${displayMessage}</p>
        </div>
        <div class="message-time">${timeStr}</div>
    `;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// 通过模块名切换
function switchModuleByName(moduleName) {
    document.querySelectorAll('.module-tab').forEach(tab => tab.classList.remove('active'));
    const tabs = document.querySelectorAll('.module-tab');
    const moduleMap = { workorder: 0, money: 1, schedule: 2, fund: 3, prospectus: 4 };
    const idx = moduleMap[moduleName];
    if (idx !== undefined && tabs[idx]) tabs[idx].classList.add('active');
    document.querySelectorAll('.module-panel').forEach(p => p.classList.remove('active'));
    const panel = document.getElementById(`panel-${moduleName}`);
    if (panel) panel.classList.add('active');
    window.scrollTo({ top: 0, behavior: 'smooth' });
    if (moduleName === 'money') loadMoneyData();
    if (moduleName === 'schedule') loadScheduleData();
    if (moduleName === 'fund') loadFundSchema();
    if (moduleName === 'prospectus') loadProspectusStats();
}

// 加载统计信息
async function loadStatistics() {
    try {
        const response = await fetch(`${API_BASE}/api/stats`);
        if (!response.ok) throw new Error('加载统计信息失败');
        const stats = await response.json();
        document.getElementById('totalOrders').textContent = stats.total;
        document.getElementById('pendingOrders').textContent = stats.pending;
        document.getElementById('processingOrders').textContent = stats.processing;
        document.getElementById('completedOrders').textContent = stats.completed;
    } catch (error) {
        console.error('加载统计信息失败:', error);
    }
}

// 加载工单列表
async function loadWorkOrders() {
    const statusFilter = document.getElementById('statusFilter')?.value || '';
    const categoryFilter = document.getElementById('categoryFilter')?.value || '';
    const searchInput = document.getElementById('searchInput')?.value || '';
    let url = `${API_BASE}/api/workorders?limit=100`;
    if (statusFilter) url += `&status=${encodeURIComponent(statusFilter)}`;
    if (categoryFilter) url += `&category=${encodeURIComponent(categoryFilter)}`;
    if (searchInput) url += `&search=${encodeURIComponent(searchInput)}`;
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error('加载工单列表失败');
        currentWorkOrders = await response.json();
        renderWorkOrders(currentWorkOrders);
    } catch (error) {
        console.error('加载工单列表失败:', error);
    }
}

// 搜索防抖
let searchTimeout;
function handleSearchKeyup(event) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => { loadWorkOrders(); }, 500);
}

// 导出CSV
async function exportWorkOrders() {
    const statusFilter = document.getElementById('statusFilter')?.value || '';
    const categoryFilter = document.getElementById('categoryFilter')?.value || '';
    let url = `${API_BASE}/api/workorders/export/csv?`;
    if (statusFilter) url += `status=${encodeURIComponent(statusFilter)}&`;
    if (categoryFilter) url += `category=${encodeURIComponent(categoryFilter)}&`;
    window.location.href = url;
}

// 渲染工单列表
function renderWorkOrders(workorders) {
    const listContainer = document.getElementById('workorderList');
    if (!workorders || workorders.length === 0) {
        listContainer.innerHTML = `<div class="empty-state"><p>暂无工单</p><p class="hint">与智能助手对话即可创建工单</p></div>`;
        return;
    }
    listContainer.innerHTML = workorders.map(wo => {
        const statusClass = getStatusClass(wo.status);
        const priorityClass = getPriorityClass(wo.priority);
        const createdDate = new Date(wo.created_at).toLocaleString('zh-CN');
        return `
            <div class="workorder-item" onclick="showWorkOrderDetail(${wo.id})">
                <div class="workorder-header">
                    <span class="workorder-number">${escapeHtml(wo.order_number)}</span>
                    <span class="workorder-status ${statusClass}">${escapeHtml(wo.status)}</span>
                </div>
                <div class="workorder-title ${priorityClass}">${escapeHtml(wo.title)}</div>
                <div class="workorder-meta">${escapeHtml(wo.category)} | ${escapeHtml(wo.priority)} | ${escapeHtml(wo.creator_name)} | ${createdDate}</div>
            </div>
        `;
    }).join('');
}

function filterWorkOrders() { loadWorkOrders(); }
function refreshWorkOrders() { loadWorkOrders(); loadStatistics(); }

// 显示工单详情
async function showWorkOrderDetail(workorderId) {
    try {
        const [woResp, logsResp] = await Promise.all([
            fetch(`${API_BASE}/api/workorders/${workorderId}`),
            fetch(`${API_BASE}/api/workorders/${workorderId}/logs`)
        ]);
        if (!woResp.ok) throw new Error('加载工单详情失败');
        const workorder = await woResp.json();
        const logs = logsResp.ok ? await logsResp.json() : [];
        const modal = document.getElementById('workorderModal');
        const detailContainer = document.getElementById('workorderDetail');
        const createdDate = new Date(workorder.created_at).toLocaleString('zh-CN');
        const updatedDate = new Date(workorder.updated_at).toLocaleString('zh-CN');
        detailContainer.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
                <h2 style="color:#333;">工单详情</h2>
                <div style="display:flex;gap:8px;">
                    <button onclick="processWorkOrder(${workorder.id})" class="btn btn-small" style="background:#667eea;color:white;">Agent处理</button>
                    <button onclick="updateWorkOrderStatus(${workorder.id},'已完成')" class="btn btn-small" style="background:#10b981;color:white;">标记完成</button>
                    <button onclick="updateWorkOrderStatus(${workorder.id},'已取消')" class="btn btn-small" style="background:#ef4444;color:white;">取消工单</button>
                </div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:20px;">
                <div><strong>工单编号</strong><br><span style="color:#667eea;font-weight:bold;">${escapeHtml(workorder.order_number)}</span></div>
                <div><strong>状态</strong><br><span class="workorder-status ${getStatusClass(workorder.status)}">${escapeHtml(workorder.status)}</span></div>
                <div><strong>类别</strong><br>${escapeHtml(workorder.category)}</div>
                <div><strong>优先级</strong><br><span class="${getPriorityClass(workorder.priority)}">${escapeHtml(workorder.priority)}</span></div>
                <div><strong>创建人</strong><br>${escapeHtml(workorder.creator_name)}</div>
                <div><strong>负责人</strong><br>${workorder.assigned_to ? escapeHtml(workorder.assigned_to) : '未分配'}</div>
                <div><strong>创建时间</strong><br>${createdDate}</div>
                <div><strong>更新时间</strong><br>${updatedDate}</div>
            </div>
            <div style="padding:15px;background:#f9fafb;border-radius:8px;margin-bottom:15px;">
                <strong>详细描述：</strong>
                <p style="margin-top:8px;line-height:1.8;color:#555;">${escapeHtml(workorder.description)}</p>
            </div>
            ${workorder.messages && workorder.messages.length > 0 ? `
                <h3 style="margin:15px 0 10px;">消息记录 (${workorder.messages.length}条)</h3>
                <div style="max-height:200px;overflow-y:auto;">
                    ${workorder.messages.map(msg => `
                        <div style="padding:10px;background:#f9fafb;border-radius:8px;margin-bottom:8px;border-left:3px solid #667eea;">
                            <div style="display:flex;justify-content:space-between;">
                                <strong style="color:#667eea;">${escapeHtml(msg.sender)}</strong>
                                <small style="color:#999;">${new Date(msg.created_at).toLocaleString('zh-CN')}</small>
                            </div>
                            <p style="color:#555;margin-top:5px;">${escapeHtml(msg.content)}</p>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
            ${logs && logs.length > 0 ? `
                <h3 style="margin:15px 0 10px;">操作日志 (${logs.length}条)</h3>
                <div style="max-height:150px;overflow-y:auto;">
                    ${logs.map(log => `
                        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f0f0f0;font-size:0.9em;">
                            <span><strong>${escapeHtml(log.action)}</strong> ${escapeHtml(log.description || '')}</span>
                            <span style="color:#999;white-space:nowrap;margin-left:10px;">${escapeHtml(log.operator)}</span>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
            <h3 style="margin:15px 0 10px;">添加回复</h3>
            <div style="display:flex;gap:10px;">
                <textarea id="replyInput_${workorder.id}" placeholder="输入回复..." rows="2"
                    style="flex:1;padding:10px;border:2px solid #e5e7eb;border-radius:8px;font-family:inherit;resize:none;"></textarea>
                <button onclick="addReply(${workorder.id})" class="btn btn-primary" style="padding:10px 20px;">发送</button>
            </div>
        `;
        modal.style.display = 'block';
        selectedWorkOrder = workorderId;
    } catch (error) {
        alert('加载工单详情失败，请稍后重试');
    }
}

async function updateWorkOrderStatus(workorderId, status) {
    try {
        const r = await fetch(`${API_BASE}/api/workorders/${workorderId}`, {
            method: 'PUT', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({status: status})
        });
        if (r.ok) { closeModal(); loadWorkOrders(); loadStatistics(); }
    } catch (e) { alert('操作失败'); }
}

async function processWorkOrder(workorderId) {
    try {
        const r = await fetch(`${API_BASE}/api/workorders/${workorderId}/process`, {method: 'POST'});
        if (r.ok) {
            const data = await r.json();
            alert(data.message || 'Agent处理完成');
            showWorkOrderDetail(workorderId);
            loadWorkOrders(); loadStatistics();
        }
    } catch (e) { alert('Agent处理失败'); }
}

async function addReply(workorderId) {
    const input = document.getElementById(`replyInput_${workorderId}`);
    const content = input?.value?.trim();
    if (!content) return;
    try {
        const r = await fetch(`${API_BASE}/api/workorders/${workorderId}/messages`, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({content: content, sender: '客服人员', sender_type: 'agent'})
        });
        if (r.ok) showWorkOrderDetail(workorderId);
    } catch (e) { alert('发送失败'); }
}

function closeModal() { document.getElementById('workorderModal').style.display = 'none'; }

window.onclick = function(event) {
    const modal = document.getElementById('workorderModal');
    if (event.target === modal) modal.style.display = 'none';
}

function getStatusClass(status) {
    return {'待处理':'status-pending','处理中':'status-processing','已完成':'status-completed','已取消':'status-cancelled'}[status] || '';
}

function getPriorityClass(priority) {
    return {'紧急':'priority-urgent','高':'priority-high','中':'priority-medium','低':'priority-low'}[priority] || '';
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
