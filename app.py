import random
import matplotlib.pyplot as plt
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
# usado para validar senha com hash
from werkzeug.security import check_password_hash
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
ARQUIVO = "controle_financeiro.xlsx"

# Configuração de sessão
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
app.secret_key = 'chave_secreta'


def get_db_connection():
    conn = sqlite3.connect('database.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Cria a tabela usuarios se não existir."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


# inicializa DB e CSV se necessário
init_db()

CSV_FILE = 'registros.csv'
if not os.path.exists(CSV_FILE):
    df_init = pd.DataFrame(columns=['descricao', 'tipo', 'valor', 'data'])
    df_init.to_csv(CSV_FILE, index=False)


# --- ROTAS ---
@app.route('/')
def index():
    # página inicial pode ser index.html (coloque um arquivo templates/index.html)
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '').strip()

        if not email or not senha:
            flash("⚠️ Preencha todos os campos.", "error")
            return redirect(url_for('login'))

        conn = get_db_connection()
        cursor = conn.cursor()

        # Primeiro: verifica se o usuário existe
        cursor.execute(
            "SELECT * FROM usuarios WHERE LOWER(email) = ?", (email,))
        user = cursor.fetchone()

        conn.close()

        if not user:
            flash("❌ Usuário não encontrado.", "error")
            return redirect(url_for('login'))

        if senha == user['senha']:
            session['user_id'] = user['id']
            flash("✅ Login bem-sucedido!", "success")
            return redirect(url_for('chat'))
        else:
            flash("❌ Senha incorreta.", "error")
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        email = request.form.get(
            'email', '').strip().lower()  # padroniza o e-mail
        senha = request.form.get('senha', '').strip()

        # Verificação de campos obrigatórios
        if not nome or not email or not senha:
            flash("⚠️ Preencha todos os campos.", "error")
            return redirect(url_for('register'))

        conn = get_db_connection()
        cursor = conn.cursor()

        # Verifica se o e-mail já existe
        cursor.execute(
            "SELECT id FROM usuarios WHERE LOWER(email) = ?", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash("❌ Este e-mail já está cadastrado.", "error")
            conn.close()
            return redirect(url_for('register'))

        # Insere novo usuário
        cursor.execute("""
            INSERT INTO usuarios (nome, email, senha)
            VALUES (?, ?, ?)
        """, (nome, email, senha))

        conn.commit()
        conn.close()

        flash("✅ Cadastro realizado com sucesso! Faça login.", "success")
        return redirect(url_for('login'))

    # Se for GET, apenas renderiza a página de cadastro
    return render_template('register.html')


@app.route('/chat', methods=['GET'])
def chat():
    return render_template('chat.html')


# Funções principais
def registrar_transacao(valor, tipo, descricao, categoria):
    try:
        valor = float(valor)
    except Exception:
        valor = 0.0

    data = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    nova = {"Data": data, "Tipo": tipo, "Descrição": descricao,
            "Categoria": categoria, "Valor": valor}

    if os.path.exists(ARQUIVO):
        df = pd.read_excel(ARQUIVO)
        df = pd.concat([df, pd.DataFrame([nova])], ignore_index=True)
    else:
        df = pd.DataFrame([nova])
    # força a coluna Valor como numérica
    df["Valor"] = pd.to_numeric(df["Valor"], errors='coerce').fillna(0.0)
    df.to_excel(ARQUIVO, index=False)


def gerar_dashboard():
    if not os.path.exists(ARQUIVO):
        return None

    df = pd.read_excel(ARQUIVO)

    # Normaliza colunas
    if "Valor" not in df.columns or "Tipo" not in df.columns:
        return None

    df["Valor"] = pd.to_numeric(df["Valor"], errors='coerce').fillna(0.0)
    # ajusta data para datetime se possível
    try:
        df["Data_parsed"] = pd.to_datetime(
            df["Data"], dayfirst=True, errors='coerce')
    except Exception:
        df["Data_parsed"] = pd.NaT

    df["Valor Ajustado"] = df.apply(lambda x: x["Valor"] if str(
        x.get("Tipo")).lower() == "entrada".lower() else -x["Valor"], axis=1)
    df["Saldo Acumulado"] = df["Valor Ajustado"].cumsum()
    if df["Saldo Acumulado"].empty:
        saldo = 0.0
    else:
        saldo = float(df["Saldo Acumulado"].iloc[-1])

    # Previsão simples
    df = df.reset_index(drop=True)
    df["Indice"] = df.index.values.reshape(-1)
    if len(df) >= 2:
        modelo = LinearRegression()
        X = df[["Indice"]].values.reshape(-1, 1)
        y = df["Saldo Acumulado"].values
        try:
            modelo.fit(X, y)
            previsao = float(modelo.predict([[len(df) + 1]])[0])
        except Exception:
            previsao = saldo
    else:
        previsao = saldo

    # Geração dos gráficos (salva em static/)
    try:
        os.makedirs("static", exist_ok=True)

        # PALETA CLEAN
        azul = "#3A6EA5"
        cinza = "#7A7A7A"

        # --- Gráfico de Saldo como BARRAS (colunas) ----
        plt.figure(figsize=(7, 4), dpi=100)
        x = df["Data_parsed"] if not df["Data_parsed"].isna().all() else df.index

        # garantir que x é convertível para matplotlib (lista de strings ou datetimes)
        x_vals = list(x) if hasattr(x, "__iter__") else list(range(len(df)))
        y_vals = df["Saldo Acumulado"].tolist()

        plt.clf()
        fig1 = plt.figure(figsize=(7, 4), dpi=100)
        ax1 = fig1.add_subplot(1, 1, 1)
        ax1.bar(x_vals, y_vals, color=azul)
        ax1.set_title("Evolução do Saldo", color=cinza)
        ax1.set_xlabel("Data", color=cinza)
        ax1.set_ylabel("Saldo (R$)", color=cinza)
        for label in ax1.get_xticklabels():
            label.set_rotation(45)
            label.set_color(cinza)
        ax1.tick_params(axis='y', colors=cinza)
        fig1.tight_layout()
        fig1.savefig("static/saldo.png",
                     bbox_inches='tight', facecolor='white')
        plt.close(fig1)

        # --- Gráfico por Categoria como PIZZA com % ---
        cat = df.groupby("Categoria")["Valor Ajustado"].sum()
        # se todas categorias somarem zero, evita erro
        if cat.sum() == 0 or cat.empty:
            # cria uma pizza vazia com placeholder
            labels = ["Nenhum registro"]
            sizes = [1]
            colors = [azul]
        else:
            labels = cat.index.tolist()
            sizes = cat.values.tolist()
            colors = None  # matplotlib default

        plt.clf()
        fig2 = plt.figure(figsize=(7, 4), dpi=100)
        ax2 = fig2.add_subplot(1, 1, 1)
        wedges, texts, autotexts = ax2.pie(
            sizes, labels=labels, autopct="%1.1f%%", startangle=90, textprops={'color': cinza}
        )
        ax2.set_title("Distribuição por Categoria (%)", color=cinza)
        # ajusta aspecto para círculo
        ax2.axis('equal')
        fig2.tight_layout()
        fig2.savefig("static/categorias.png",
                     bbox_inches='tight', facecolor='white')
        plt.close(fig2)

    except Exception as e:
        print("Erro ao gerar gráficos:", e)

    return {"saldo": saldo, "previsao": previsao}


@app.route("/regenerate_graphs", methods=["GET"])
def regenerate_graphs():
    dados = gerar_dashboard()
    if dados:
        return jsonify({"status": "ok", "saldo": dados["saldo"], "previsao": dados["previsao"]})
    else:
        return jsonify({"status": "no-data"}), 404


# Função de processamento
def processar_mensagem(frase):
    frase = frase.lower().strip()

    # Detecta valor informado (ex: "50", "50,00", "100.20")
    valor_match = re.search(r"(\d+(\,\d+)?|\d+(\.\d+)?)", frase)
    valor = float(valor_match.group().replace(
        ",", ".")) if valor_match else None

    # Identifica tipo (entrada/saída)
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
        "salário": ["salário", "freela"]
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
    cumprimentos = ["tudo bem", "como você ta",
                    "de boa" "como tu ta", "tranquilo"]
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
    # imprime rotas para debug
    print(app.url_map)
    app.run(debug=True, port=5500)
