import random
import matplotlib.pyplot as plt
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
# usado para validar senha com hash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_session import Session
from sklearn.linear_model import LinearRegression
from datetime import datetime
import sqlite3
import os
import pandas as pd
import re
import matplotlib
matplotlib.use('Agg')  # importante para servidores sem display

print("pandas:", pd.__version__)

app = Flask(__name__)


# Configuração de sessão
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
app.secret_key = 'chave_secreta'


def get_db_connection():
    conn = sqlite3.connect('banco.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# inicializa DB e CSV se necessário
def init_db():
    """Cria o banco e a tabela de usuários e gastos, se não existirem."""
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

    # Tabela de gastos (pode conter Entrada, Saída ou Cofre)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            data TEXT NOT NULL,
            tipo TEXT NOT NULL CHECK(tipo IN ('Entrada', 'Saída', 'Cofre')),
            descricao TEXT,
            categoria TEXT,
            valor REAL NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    ''')

    conn.commit()
    conn.close()


CSV_FILE = 'registros.csv'
if not os.path.exists(CSV_FILE):
    df_init = pd.DataFrame(columns=['descricao', 'tipo', 'valor', 'data'])
    df_init.to_csv(CSV_FILE, index=False)


# --- ROTAS ---
@app.route('/')
def index():
    return render_template('index.html')


# -----------------------------------------------------------
# ROTA DE CADASTRO
# -----------------------------------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '').strip()

        if not nome or not email or not senha:
            flash("⚠️ Preencha todos os campos.", "error")
            return render_template('register.html')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Verifica se o e-mail já existe
        cursor.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
        existing_user = cursor.fetchone()
        if existing_user:
            flash("❌ Este e-mail já está cadastrado.", "error")
            conn.close()
            return render_template('register.html')

        # Criptografa a senha antes de salvar
        senha_hash = generate_password_hash(senha)

        # Insere novo usuário
        cursor.execute("""
            INSERT INTO usuarios (nome, email, senha)
            VALUES (?, ?, ?)
        """, (nome, email, senha_hash))
        conn.commit()
        conn.close()

        flash("✅ Cadastro realizado com sucesso! Faça login.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

# -----------------------------------------------------------
# ROTA DE LOGIN
# -----------------------------------------------------------


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['email']
        senha = request.form['senha']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE email = ?", (usuario,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['senha'], senha):
            session['usuario'] = usuario
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('chat'))
        else:
            flash('Usuário ou senha incorretos!', 'error')
            return render_template('login.html')
        


    # Se for GET (ou erro), sempre renderiza a página de login
    return render_template('login.html')

# -----------------------------------------------------------
# ROTA DE LOGOUT
# -----------------------------------------------------------


@app.route('/logout')
def logout():
    session.clear()  # Limpa a sessão (remove o usuário logado)
    flash("Você saiu da conta com sucesso.", "success")
    return redirect(url_for('login'))


@app.route('/chat', methods=['GET'])
def chat():
    return render_template('chat.html')


# Funções principais
def registrar_transacao(valor, tipo, descricao, categoria):
    """Registra uma transação no banco vinculada ao usuário logado."""
    if 'usuario' not in session:
        print("⚠️ Nenhum usuário logado.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # Busca o ID do usuário logado
    cursor.execute("SELECT id FROM usuarios WHERE email = ?",
                   (session['usuario'],))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return

    usuario_id = user['id']
    data = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    cursor.execute("""
        INSERT INTO gastos (usuario_id, data, tipo, descricao, categoria, valor)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (usuario_id, data, tipo, descricao, categoria, valor))

    conn.commit()
    conn.close()


def gerar_dashboard():
    if 'usuario' not in session:
        return None

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM usuarios WHERE email = ?", (session['usuario'],))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return None

    usuario_id = user['id']

    cursor.execute("""
        SELECT data, tipo, descricao, categoria, valor
        FROM gastos
        WHERE usuario_id = ?
        ORDER BY id
    """, (usuario_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return {"saldo": 0, "previsao": 0, "entrada": 0, "saida": 0, "cofre": 0, "tabela": []}

    df = pd.DataFrame(rows, columns=['Data', 'Tipo', 'Descrição', 'Categoria', 'Valor'])
    df["Valor"] = pd.to_numeric(df["Valor"], errors='coerce').fillna(0.0)

    # ✅ Valores dos cards
    entrada = df[df["Tipo"].str.lower() == "entrada"]["Valor"].sum()
    saida = df[df["Tipo"].str.lower() == "saída"]["Valor"].sum()

    # Se sua categoria para cofre for outro nome, ajuste aqui:
    cofre = df[df["Categoria"].str.lower() == "cofre"]["Valor"].sum()

    # Saldo acumulado
    df["Valor Ajustado"] = df.apply(
        lambda x: x["Valor"] if x["Tipo"].lower() == "entrada" else -x["Valor"], axis=1
    )
    df["Saldo Acumulado"] = df["Valor Ajustado"].cumsum()
    saldo = float(df["Saldo Acumulado"].iloc[-1])

    # Previsão
    df["Indice"] = df.index.values
    if len(df) >= 2:
        modelo = LinearRegression()
        modelo.fit(df[["Indice"]], df["Saldo Acumulado"])
        previsao = float(modelo.predict([[len(df) + 1]])[0])
    else:
        previsao = saldo

    # Dados da tabela
    dados_tabela = df.to_dict(orient='records')

    # ✅ Agora retorna TUDO
    return {
        "saldo": saldo,
        "previsao": previsao,
        "entrada": entrada,
        "saida": saida,
        "cofre": cofre,
        "tabela": dados_tabela
    }


@app.route("/dados_tabela")
def dados_tabela():
    dados = gerar_dashboard()
    if dados:
        return jsonify(dados["tabela"])
    return jsonify([])




@app.route("/regenerate_graphs", methods=["GET"])
def regenerate_graphs():
    dados = gerar_dashboard()
    if dados:
        return jsonify({"status": "ok", "saldo": dados["saldo"], "previsao": dados["previsao"]})
    else:
        return jsonify({"status": "no-data"}), 404


@app.route("/chat")
def dashboard_dados():
    dados = gerar_dashboard()  # sua função existente
    if not dados:
        return jsonify({"saldo": 0, "previsao": 0, "entrada": 0, "saida": 0, "caixinha": 0})

    return jsonify(dados)


# Função de processamento
def processar_mensagem(frase):
    frase = frase.lower().strip()

    # Detecta valor informado (ex: "50", "50,00", "100.20")
    valor_match = re.search(r"(\d+(\,\d+)?|\d+(\.\d+)?)", frase)
    valor = float(valor_match.group().replace(
        ",", ".")) if valor_match else None

    # Identifica tipo (entrada/saída/cofre)
    if any(p in frase for p in ["entrada", "recebi", "ganhei", "salário", "deposito"]):
        tipo = "Entrada"
    elif any(p in frase for p in ["saída", "gastei", "paguei", "comprei", "compra"]):
        tipo = "Saída"
    else:
        tipo = None

    # Detecta categoria
    categorias = {
        "alimentação": ["mercado", "comida", "restaurante", "lanche"],
        "contas fixas": ["luz", "água", "aluguel", "internet"],
        "lazer": ["cinema", "viagem", "show", "bar"],
        "educação": ["curso", "faculdade", "livro"],
        "salário": ["salário", "freela"],
        "cofre": ["caixinha", "investimento", "cofre"]
    }

    categoria = "outros"
    for cat, palavras in categorias.items():
        if any(p in frase for p in palavras):
            categoria = cat
            break

    # Caso a pessoa só diga "oi", "olá", "bom dia"
    cumprimentos = ["oi", "olá", "ei", "boa tarde",
                    "bom dia", "boa noite", "opa", "fala ai"]
    if frase in cumprimentos:
        mensagens_resposta = [
            "Olá! 😊 Como posso ajudar com suas finanças hoje?",
            "Oi! 💰 Já fez algum controle financeiro hoje?",
            "Olá! Me diga uma transação ou pergunte seu saldo! 💬"
        ]
        return random.choice(mensagens_resposta), None, None

     # Caso a pessoa só diga "Tudo bem?"
    cumprimentos = ["tudo bem?", "como você ta?",
                    "de boa?" "como tu ta?", "tranquilo?"]
    if frase in cumprimentos:
        mensagens_resposta = [
            "Bem, e você?! 😊",
            "Tranquilo, e por aí",
            "De boa, e você?"
        ]
        return random.choice(mensagens_resposta), None, None

    # Se registrou uma transação válida:
    saldo, previsao = None, None
    if tipo and valor:
        registrar_transacao(valor, tipo, frase.capitalize(), categoria)
        dados = gerar_dashboard()

        if dados:
            saldo = dados['saldo']
            previsao = dados['previsao']

        respostas = [
            f"✅ Registro feito! {tipo} de R$ {valor:.2f} na categoria **{categoria}**.",
            f"Anotado ✍️ {tipo} de R$ {valor:.2f}.",
            f"Ok! Lancei {tipo.lower()} de R$ {valor:.2f}."
        ]
        resumo = f"💰 Saldo atual: R$ {saldo:.2f} | 📈 Previsão: R$ {previsao:.2f}"
        return random.choice(respostas) + "\n" + resumo, saldo, previsao

    # Se ele pedir “saldo”
    if "saldo" in frase or "como estou" in frase:
        dados = gerar_dashboard()
        if dados:
            saldo = dados['saldo']
            previsao = dados['previsao']
            return f"💰 Seu saldo atual é **R$ {saldo:.2f}**.\n📈 Previsão futura: **R$ {previsao:.2f}**.", saldo, previsao
        else:
            return "Ainda não encontrei registros financeiros para calcular seu saldo.", None, None

    return "🤔 Não entendi. Diga algo como: 'Recebi 2000 de salário' ou 'Gastei 50 no mercado'.", None, None


@app.route("/mensagem", methods=["POST"])
def mensagem():
    user_msg = request.json["mensagem"]
    resposta, saldo, previsao = processar_mensagem(user_msg)
    return jsonify({"resposta": resposta, "saldo": saldo, "previsao": previsao})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    init_db()  # 🔹 cria as tabelas (usuarios e gastos) se não existirem
    print("✅ Banco inicializado!")
    print(app.url_map)
    app.run(debug=True, port=5500)
