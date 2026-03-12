import sqlite3
conn = sqlite3.connect('transactions.db')
c = conn.cursor()
for row in c.execute('SELECT * FROM transactions ORDER BY id DESC LIMIT 5'):
    print(row)
conn.close()