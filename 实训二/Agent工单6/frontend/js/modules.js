// 多模块切换和新Agent功能JS
const API_BASE = 'http://localhost:8091';

// ==================== 模块切换 ====================
function switchModule(moduleName) {
    // 切换标签
    document.querySelectorAll('.module-tab').forEach(tab => tab.classList.remove('active'));
    event.target.classList.add('active');

    // 切换面板
    document.querySelectorAll('.module-panel').forEach(panel => panel.classList.remove('active'));
    const panel = document.getElementById(`panel-${moduleName}`);
    if (panel) panel.classList.add('active');

    // 滚动到顶部
    window.scrollTo({ top: 0, behavior: 'smooth' });

    // 加载对应模块数据
    if (moduleName === 'money') loadMoneyData();
    if (moduleName === 'schedule') loadScheduleData();
    if (moduleName === 'fund') loadFundSchema();
    if (moduleName === 'prospectus') loadProspectusStats();
}

// ==================== 记账本Agent ====================
async function sendMoneyMessage() {
    const input = document.getElementById('moneyInput');
    const message = input.value.trim();
    if (!message) return;

    addMessage('moneyMessages', '用户', message, 'user');
    input.value = '';

    try {
        const r = await fetch(`${API_BASE}/api/money/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });
        const data = await r.json();
        addMessage('moneyMessages', '记账助手', data.reply, 'bot');
        loadMoneyData();
    } catch (e) {
        addMessage('moneyMessages', '系统', '请求失败，请稍后重试', 'system');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const mi = document.getElementById('moneyInput');
    if (mi) mi.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMoneyMessage(); } });
});

async function loadMoneyData() {
    try {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const start = `${year}-${month}-01`;
        const end = `${year}-${month}-31`;

        const [summaryR, recordsR] = await Promise.all([
            fetch(`${API_BASE}/api/money/summary?start_date=${start}&end_date=${end}`),
            fetch(`${API_BASE}/api/money/records?start_date=${start}&end_date=${end}`)
        ]);

        const summaryData = await summaryR.json();
        const recordsData = await recordsR.json();

        const s = summaryData.summary || {};
        document.getElementById('moneyIncome').textContent = (s['收入'] || 0).toFixed(0);
        document.getElementById('moneyExpense').textContent = (s['支出'] || 0).toFixed(0);
        const net = (s['净收入'] || 0);
        const netEl = document.getElementById('moneyNet');
        netEl.textContent = net.toFixed(0);
        netEl.className = `stat-value ${net >= 0 ? 'money-income' : 'money-expense'}`;

        renderMoneyRecords(recordsData.records || []);
    } catch (e) {
        console.error('加载账目数据失败:', e);
    }
}

function renderMoneyRecords(records) {
    const container = document.getElementById('moneyRecords');
    if (!records.length) {
        container.innerHTML = '<div class="empty-state"><p>本月暂无记录</p></div>';
        return;
    }
    container.innerHTML = records.slice(0, 20).map(r => {
        const isIncome = r.type === '收入';
        const sign = isIncome ? '+' : '-';
        const cls = isIncome ? 'money-income' : 'money-expense';
        return `<div class="money-item">
            <span>${r.date} ${escapeHtml(r.member)} ${escapeHtml(r.item)}</span>
            <span class="${cls} font-bold">${sign}${r.amount}元</span>
        </div>`;
    }).join('');
}

// ==================== 日程提醒Agent ====================
async function sendScheduleMessage() {
    const input = document.getElementById('scheduleInput');
    const message = input.value.trim();
    if (!message) return;

    addMessage('scheduleMessages', '用户', message, 'user');
    input.value = '';

    try {
        const r = await fetch(`${API_BASE}/api/schedule/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: message })
        });
        const data = await r.json();
        addMessage('scheduleMessages', '日程助手', data.answer, 'bot');
        loadScheduleData();
    } catch (e) {
        addMessage('scheduleMessages', '系统', '请求失败，请稍后重试', 'system');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const si = document.getElementById('scheduleInput');
    if (si) si.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendScheduleMessage(); } });
});

async function loadScheduleData() {
    try {
        const [statsR, todayR, allR, remindersR] = await Promise.all([
            fetch(`${API_BASE}/api/schedule/stats`),
            fetch(`${API_BASE}/api/schedule/today`),
            fetch(`${API_BASE}/api/schedule/list`),
            fetch(`${API_BASE}/api/schedule/reminders?limit=5`)
        ]);

        const stats = await statsR.json();
        const today = await todayR.json();
        const all = await allR.json();
        const reminders = await remindersR.json();

        document.getElementById('activeSchedules').textContent = stats.active_schedules || 0;
        document.getElementById('reminderLogs').textContent = stats.reminder_logs || 0;
        document.getElementById('todayDate').textContent = (stats.today || '').slice(5);

        renderScheduleList('todaySchedules', today.items || [], true);
        renderScheduleList('allSchedules', all.items || [], false);
        renderReminders(reminders.items || []);
    } catch (e) {
        console.error('加载日程数据失败:', e);
    }
}

function renderScheduleList(containerId, items, isToday) {
    const container = document.getElementById(containerId);
    if (!items.length) {
        container.innerHTML = `<div class="empty-state"><p>${isToday ? '今日无日程' : '暂无日程'}</p></div>`;
        return;
    }
    container.innerHTML = items.map(item => `
        <div class="schedule-item">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span class="time">${escapeHtml(item.time_label || item.time_segment)}</span>
                <span class="repeat badge badge-gray">${escapeHtml(item.repeat_text || '单次')}</span>
            </div>
            <div class="content">${escapeHtml(item.content)}</div>
            <div style="margin-top:4px;">
                <button onclick="deleteSchedule(${item.id})" style="font-size:0.75em;padding:2px 8px;border:1px solid #ef4444;color:#ef4444;background:white;border-radius:4px;cursor:pointer;">删除</button>
            </div>
        </div>
    `).join('');
}

function renderReminders(items) {
    const container = document.getElementById('recentReminders');
    if (!items.length) {
        container.innerHTML = '<div class="empty-state"><p>暂无提醒记录</p></div>';
        return;
    }
    container.innerHTML = items.map(item => `
        <div class="reminder-item">
            <div>${escapeHtml(item.message)}</div>
            <div style="font-size:0.8em;color:#999;margin-top:2px;">${item.triggered_at ? item.triggered_at.replace('T', ' ').slice(0, 16) : ''}</div>
        </div>
    `).join('');
}

async function deleteSchedule(scheduleId) {
    addMessage('scheduleMessages', '日程助手', `正在删除日程 ${scheduleId}...`, 'bot');
    try {
        const r = await fetch(`${API_BASE}/api/schedule/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: scheduleId })
        });
        const data = await r.json();
        addMessage('scheduleMessages', '日程助手', data.answer, 'bot');
        loadScheduleData();
    } catch (e) {
        addMessage('scheduleMessages', '系统', '删除失败', 'system');
    }
}

// ==================== 基金数据问答Agent ====================
async function sendFundQuestion() {
    const input = document.getElementById('fundInput');
    const question = input.value.trim();
    if (!question) return;

    addMessage('fundMessages', '用户', question, 'user');
    input.value = '';
    addMessage('fundMessages', '基金助手', '正在查询中...', 'bot');

    try {
        const r = await fetch(`${API_BASE}/api/fund/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });
        const data = await r.json();
        // 替换最后一条"查询中"消息
        const msgs = document.getElementById('fundMessages');
        const lastMsg = msgs.lastElementChild;
        if (lastMsg && lastMsg.textContent.includes('查询中')) {
            msgs.removeChild(lastMsg);
        }
        addMessage('fundMessages', '基金助手', data.answer, 'bot');
    } catch (e) {
        addMessage('fundMessages', '系统', '查询失败，请稍后重试', 'system');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const fi = document.getElementById('fundInput');
    if (fi) fi.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendFundQuestion(); } });
});

async function loadFundSchema() {
    const container = document.getElementById('fundSchemaInfo');
    container.innerHTML = '<p style="color:#999;padding:10px;">加载中...</p>';
    try {
        const r = await fetch(`${API_BASE}/api/fund/schema`);
        const data = await r.json();
        if (!data.available) {
            container.innerHTML = `<div class="empty-state"><p>基金数据库未配置</p><p class="hint">请确认数据库文件路径正确</p></div>`;
            return;
        }
        container.innerHTML = `
            <div style="margin-bottom:10px;">
                <span class="badge badge-green">可用</span>
                <span style="font-size:0.85em;color:#666;margin-left:8px;">${data.tables.length} 个数据表</span>
            </div>
            ${data.tables.slice(0, 8).map(t => `
                <div style="margin-bottom:10px;padding:10px;background:#f9fafb;border-radius:8px;">
                    <div style="font-weight:600;color:#333;">${escapeHtml(t.name)}</div>
                    <div style="font-size:0.8em;color:#999;">${t.row_count?.toLocaleString() || '?'} 行 | ${t.columns?.length || 0} 列</div>
                    <div style="font-size:0.8em;color:#666;margin-top:3px;">${(t.columns || []).slice(0, 5).map(c => escapeHtml(c.name)).join(' · ')}</div>
                </div>
            `).join('')}
        `;
    } catch (e) {
        container.innerHTML = '<div class="empty-state"><p>加载失败</p></div>';
    }
}

// ==================== 招股书问答Agent ====================
async function sendProspectusQuestion() {
    const input = document.getElementById('prospectusInput');
    const question = input.value.trim();
    if (!question) return;

    addMessage('prospectusMessages', '用户', question, 'user');
    input.value = '';
    addMessage('prospectusMessages', '招股书助手', '正在检索知识库...', 'bot');

    try {
        const r = await fetch(`${API_BASE}/api/prospectus/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });
        const data = await r.json();
        const msgs = document.getElementById('prospectusMessages');
        const lastMsg = msgs.lastElementChild;
        if (lastMsg && lastMsg.textContent.includes('检索知识库')) {
            msgs.removeChild(lastMsg);
        }
        const detail = data.matched_docs ? ` (匹配${data.matched_docs}篇文档)` : '';
        addMessage('prospectusMessages', `招股书助手${detail}`, data.answer, 'bot');
    } catch (e) {
        addMessage('prospectusMessages', '系统', '查询失败，请稍后重试', 'system');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const pi = document.getElementById('prospectusInput');
    if (pi) pi.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendProspectusQuestion(); } });
});

async function loadProspectusStats() {
    const container = document.getElementById('prospectusStatsInfo');
    container.innerHTML = '<p style="color:#999;padding:10px;">检查中...</p>';
    try {
        const r = await fetch(`${API_BASE}/api/prospectus/stats`);
        const data = await r.json();
        container.innerHTML = `
            <div style="padding:15px;background:#f9fafb;border-radius:8px;">
                <div style="margin-bottom:10px;">
                    <span class="badge ${data.available ? 'badge-green' : 'badge-gray'}">${data.available ? '知识库已加载' : '知识库未加载'}</span>
                </div>
                <div style="font-size:0.9em;color:#555;">
                    <p>📄 招股书文档数：<strong>${data.total_docs || 0}</strong></p>
                    ${data.text_dir ? `<p>📁 数据目录：<code style="font-size:0.85em;">${escapeHtml(data.text_dir)}</code></p>` : ''}
                    ${data.sample_companies?.length ? `<p>🏢 示例公司：${data.sample_companies.slice(0,3).map(c => escapeHtml(c)).join('、')}</p>` : ''}
                </div>
                ${!data.available ? '<p style="color:#ef4444;margin-top:10px;font-size:0.9em;">⚠️ 知识库数据未找到，请确认数据文件路径正确</p>' : '<p style="color:#10b981;margin-top:10px;font-size:0.9em;">✓ 知识库就绪，可以开始提问</p>'}
            </div>
        `;
    } catch (e) {
        container.innerHTML = '<div class="empty-state"><p>加载失败</p></div>';
    }
}

// ==================== 通用消息添加函数 ====================
function addMessage(containerId, sender, message, type) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const div = document.createElement('div');
    div.className = `message ${type}-message`;
    const now = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    div.innerHTML = `
        <div class="message-content">
            <strong>${escapeHtml(sender)}：</strong>
            <p style="white-space:pre-line;">${escapeHtml(message)}</p>
        </div>
        <div class="message-time">${now}</div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}
