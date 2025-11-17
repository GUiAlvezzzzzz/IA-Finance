import sqlite3


DATABASE = "/opt/render/data/database.db"

conn = sqlite3.connect('banco.db')
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    senha TEXT NOT NULL
)
''')


conn.commit()
conn.close()
print("Novo banco criado com sucesso!")
