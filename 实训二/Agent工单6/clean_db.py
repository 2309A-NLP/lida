import sqlite3
c = sqlite3.connect('data/workorders.db')
c.execute('DELETE FROM agent_tasks')
c.execute('DELETE FROM work_order_logs')
c.execute('DELETE FROM work_order_messages')
c.execute('DELETE FROM work_orders')
c.commit()
count = c.execute('SELECT COUNT(*) FROM work_orders').fetchone()[0]
c.close()
print(f'数据库已清理，当前工单数: {count}')
