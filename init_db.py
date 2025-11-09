import sqlite3

# Conectar ao banco (cria o arquivo se não existir)
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Criar tabela usuarios
cursor.execute('''
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    senha TEXT NOT NULL
)
''')

conn.commit()
conn.close()

print("✅ Banco de dados e tabela 'usuarios' criados com sucesso!")
