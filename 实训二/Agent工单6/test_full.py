"""全功能端到端测试"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')

from fastapi.testclient import TestClient
from backend.api import app

client = TestClient(app)
passed = 0
total = 0

def t(name, ok, detail=''):
    global passed, total
    total += 1
    if ok: passed += 1
    mark = 'OK  ' if ok else 'FAIL'
    line = f'  [{mark}] {name}'
    if detail: line += f' | {detail}'
    print(line)

print('=' * 70)
print('全功能端到端测试')
print('=' * 70)

# ===== 1. 系统基础 =====
print('\n--- 系统基础 ---')
r = client.get('/health')
t('健康检查', r.status_code==200)
r = client.get('/api/status')
t('系统状态', r.status_code==200 and r.json()['status']=='running')
r = client.get('/')
t('首页加载', r.status_code==200)
r = client.get('/docs')
t('Swagger文档', r.status_code==200)

# ===== 2. 工单管理 =====
print('\n--- 工单管理 ---')
r = client.post('/api/workorders', json={'title':'服务器故障','description':'服务器无法访问需要紧急处理','category':'故障报修','priority':'高','creator_name':'张三','creator_contact':'138xxx'})
t('创建工单', r.status_code==201)
wo_id = r.json()['id']
t('工单编号格式', r.json()['order_number'].startswith('WO'), r.json()['order_number'])
r = client.get('/api/workorders')
t('工单列表', r.status_code==200 and len(r.json())>0)
r = client.get(f'/api/workorders/{wo_id}')
t('工单详情', r.status_code==200)
r = client.put(f'/api/workorders/{wo_id}', json={'status':'处理中','assigned_to':'运维团队'})
t('更新工单', r.status_code==200 and r.json()['status']=='处理中')
r = client.get('/api/workorders?status=处理中')
t('按状态筛选', r.status_code==200 and len(r.json())>0)
r = client.get('/api/workorders?category=故障报修')
t('按类别筛选', r.status_code==200 and len(r.json())>0)
r = client.get('/api/workorders?search=服务器')
t('关键词搜索', r.status_code==200 and len(r.json())>0)
r = client.post(f'/api/workorders/{wo_id}/messages', json={'content':'正在排查中','sender':'工程师'})
t('添加消息', r.status_code==200)
r = client.get(f'/api/workorders/{wo_id}/messages')
t('查询消息', r.status_code==200 and len(r.json())>0)
r = client.get(f'/api/workorders/{wo_id}/logs')
t('操作日志', r.status_code==200 and len(r.json())>0)
r = client.post(f'/api/workorders/{wo_id}/process')
t('Agent自动处理', r.status_code==200 and r.json()['success'])
r = client.get('/api/workorders/export/csv')
t('导出CSV', r.status_code==200 and len(r.content)>0)
r = client.get('/api/stats')
t('统计信息', r.status_code==200 and 'total' in r.json())
r = client.delete(f'/api/workorders/{wo_id}')
t('删除工单', r.status_code==200)
r = client.get(f'/api/workorders/{wo_id}')
t('删除后404', r.status_code==404)

# ===== 3. NLP分析 =====
print('\n--- NLP分析 ---')
r = client.post('/api/nlp/analyze', json={'text':'我的服务器出现严重故障需要紧急修复'})
t('故障报修意图', r.status_code==200 and r.json()['intent']=='故障报修', f"意图={r.json()['intent']}")
r = client.post('/api/nlp/analyze', json={'text':'非常感谢你们的帮助很满意'})
t('积极情感分析', r.status_code==200 and r.json()['sentiment']=='积极', f"情感={r.json()['sentiment']}")
r = client.post('/api/nlp/analyze', json={'text':'系统出错太差了投诉你们'})
t('消极情感分析', r.status_code==200 and r.json()['sentiment']=='消极', f"情感={r.json()['sentiment']}")

# ===== 4. 智能对话 =====
print('\n--- 智能对话 ---')
r = client.post('/api/chat', json={'message':'你好','user_name':'用户'})
reply = r.json()['message']
t('问候回复有意义', '助手' in reply or '帮您' in reply or '您好' in reply, reply[:40])

r = client.post('/api/chat', json={'message':'我的打印机坏了无法打印','user_name':'用户'})
d = r.json()
t('故障报修自动创建工单', d['work_order_created']==True, f"工单ID={d.get('work_order_id')}")

r = client.post('/api/chat', json={'message':'湖南长远锂科股份有限公司发起人法人有哪些','user_name':'用户'})
reply = r.json()['message']
t('招股书问题正确引导', '招股书' in reply or '金融' in reply or '切换' in reply, reply[:50])

r = client.post('/api/chat', json={'message':'我需要开发一个新的报表功能','user_name':'用户'})
d = r.json()
t('需求开发创建工单', d['work_order_created']==True, f"意图={d.get('intent')}")

r = client.post('/api/chat', json={'message':'如何申请业务','user_name':'用户'})
d = r.json()
t('业务咨询创建工单', d['work_order_created']==True, f"意图={d.get('intent')}")

# ===== 5. 记账本Agent =====
print('\n--- 记账本Agent ---')
r = client.post('/api/money/chat', json={'message':'今天女儿买了登山鞋499元'})
reply = r.json()['reply']
t('记账确认流程', '确认' in reply and '499' in reply, reply[:50])

r = client.post('/api/money/chat', json={'message':'确认'})
reply = r.json()['reply']
t('确认保存记录', '已记录' in reply or '✅' in reply, reply[:40])

r = client.post('/api/money/chat', json={'message':'7月5日妈妈收到报销1000元'})
reply = r.json()['reply']
t('收入记录确认', '确认' in reply and '1000' in reply, reply[:40])

r = client.post('/api/money/chat', json={'message':'查询本月消费明细'})
reply = r.json()['reply']
t('查询消费明细', ('收入' in reply or '支出' in reply or '明细' in reply), reply[:40])

r = client.get('/api/money/records')
t('记录列表API', r.status_code==200 and 'records' in r.json())

r = client.get('/api/money/summary')
d = r.json()
t('汇总统计API', r.status_code==200 and 'summary' in d)

# ===== 6. 日程提醒Agent =====
print('\n--- 日程提醒Agent ---')
r = client.post('/api/schedule/chat', json={'question':'提醒我明天下午3点开会'})
d = r.json()
t('添加单次日程', d.get('success')==True, d.get('answer','')[:40])

r = client.post('/api/schedule/chat', json={'question':'每天早上9点提醒我开晨会'})
d = r.json()
t('添加每日重复日程', d.get('success')==True, d.get('answer','')[:40])

r = client.post('/api/schedule/chat', json={'question':'我今天的日程有哪些'})
t('查询今日日程', r.json().get('intent')=='list', f"意图={r.json().get('intent')}")

r = client.post('/api/schedule/chat', json={'question':'今天有什么日程'})
t('自然语言查询日程', r.json().get('intent')=='list', f"意图={r.json().get('intent')}")

r = client.post('/api/schedule/chat', json={'question':'查看全部日程'})
t('查看全部日程', r.json().get('intent')=='list', f"意图={r.json().get('intent')}")

r = client.get('/api/schedule/list')
items = r.json().get('items', [])
t('日程列表API', r.status_code==200 and len(items)>0, f'{len(items)}个日程')

if items:
    sid = items[0]['id']
    r = client.post('/api/schedule/chat', json={'question': f'删除日程 {sid}'})
    t('删除日程', r.json().get('success')==True, r.json().get('answer','')[:40])

r = client.get('/api/schedule/stats')
d = r.json()
t('日程统计API', r.status_code==200 and 'active_schedules' in d)

r = client.get('/api/schedule/reminders')
t('提醒记录API', r.status_code==200 and 'items' in r.json())

# ===== 7. 基金数据问答 =====
print('\n--- 基金数据问答 ---')
r = client.post('/api/fund/ask', json={'question':'基金数据库有哪些表'})
d = r.json()
t('查询数据库有哪些表', '表' in d.get('answer','') and d.get('success'), d.get('answer','')[:40])

r = client.post('/api/fund/ask', json={'question':'查询基金基本信息'})
d = r.json()
t('基金基本信息查询', d.get('success')==True, d.get('answer','')[:40])

r = client.post('/api/fund/ask', json={'question':'查询股票持仓明细'})
d = r.json()
t('股票持仓查询', d.get('success')==True, d.get('answer','')[:40])

r = client.post('/api/fund/ask', json={'question':'查询债券持仓明细'})
d = r.json()
t('债券持仓查询', d.get('success')==True, d.get('answer','')[:40])

r = client.post('/api/fund/ask', json={'question':'查询基金日行情'})
d = r.json()
t('日行情查询', d.get('success')==True, d.get('answer','')[:40])

r = client.get('/api/fund/schema')
d = r.json()
t('数据库结构API', r.status_code==200 and 'tables' in d, f"可用={d.get('available')}")

# ===== 8. 招股书问答 =====
print('\n--- 招股书问答 ---')
r = client.post('/api/prospectus/ask', json={'question':'公司主营业务是什么'})
d = r.json()
kws = d.get('keywords', [])
bad = [k for k in kws if k in ['是什','是哪','有哪','的是']]
t('主营业务查询', d.get('success')==True, d.get('answer','')[:40])
t('关键词无残留词', len(bad)==0, f'关键词={kws[:3]}')

r = client.post('/api/prospectus/ask', json={'question':'湖南长远锂科股份有限公司变更设立时作为发起人的法人有哪些'})
d = r.json()
t('专业招股书查询', d.get('success')==True, f"匹配={d.get('matched_docs',0)}篇")

r = client.post('/api/prospectus/ask', json={'question':'募集资金用途'})
d = r.json()
t('募集资金查询', d.get('success')==True, f"匹配={d.get('matched_docs',0)}篇")

r = client.get('/api/prospectus/stats')
d = r.json()
t('知识库统计', r.status_code==200, f"文档数={d.get('total_docs')}")

# ===== 汇总 =====
print()
print('=' * 70)
rate = passed/total*100 if total else 0
if passed == total:
    print(f'全部通过！ {passed}/{total} ({rate:.0f}%)')
else:
    print(f'结果: {passed}/{total} 通过 ({rate:.0f}%)')
    fails = total - passed
    print(f'失败: {fails} 项 — 请检查上方 FAIL 行')
print('=' * 70)
