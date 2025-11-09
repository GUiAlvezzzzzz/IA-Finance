function enviarMensagem() {
    const input = document.getElementById("mensagem");
    const mensagem = input.value.trim();

    if (mensagem === "") return;

    // Mostra a mensagem do usuário no chat
    processar_mensagem("Você", mensagem);

    fetch("/mensagem", { 
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mensagem: mensagem })  // ✅ corrigido
    })
    .then(res => {
        if (!res.ok) {
            throw new Error("Servidor retornou erro");
        }
        return res.json();
    })
    .then(data => {
        // Exibe a resposta da IA
        processar_mensagem("IA", data.resposta);

        // Atualiza saldo e previsão no Dashboard
        if (data.saldo !== null && data.saldo !== undefined) {
            document.getElementById("saldoValor").innerText = `R$ ${data.saldo.toFixed(2)}`;
        }

        if (data.previsao !== null && data.previsao !== undefined) {
            document.getElementById("previsaoValor").innerText = `R$ ${data.previsao.toFixed(2)}`;
        }
    })
    .catch(err => {
        processar_mensagem("Erro", "❌ Não foi possível conectar ao servidor.");
    });

    input.value = "";
}

document.getElementById('graf1').src = '/static/saldo.png?t=' + new Date().getTime();
document.getElementById('graf2').src = '/static/categorias.png?t=' + new Date().getTime();


function processar_mensagem(usuario, texto) {
    const chat = document.getElementById("chat-box");
    const msg = document.createElement("p");
    msg.innerHTML = `<strong>${usuario}:</strong> ${texto}`;
    chat.appendChild(msg);
    chat.scrollTop = chat.scrollHeight;
}
