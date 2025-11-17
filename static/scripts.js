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

    // Atualiza os cards
    if (data.saldo !== undefined) {
        document.getElementById("saldoValor").innerText = `R$ ${data.saldo.toFixed(2)}`;
    }
    if (data.previsao !== undefined) {
        document.getElementById("previsaoValor").innerText = `R$ ${data.previsao.toFixed(2)}`;
    }
    if (data.entrada !== undefined) {
        document.getElementById("entradaValor").innerText = `R$ ${data.entrada.toFixed(2)}`;
    }
    if (data.saida !== undefined) {
        document.getElementById("saidaValor").innerText = `R$ ${data.saida.toFixed(2)}`;
    }
    if (data.cofre !== undefined) {
        document.getElementById("caixinhaValor").innerText = `R$ ${data.cofre.toFixed(2)}`;
    }

    // Atualiza tabela sem recarregar a página
    $('#tabelaFinanceira').DataTable().ajax.reload(null, false);
})

     document.getElementById("mensagem").value = "";
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

document.addEventListener("DOMContentLoaded", function () {
    // Atualiza cards ao logar
    fetch("/chat")
        .then(r => r.json())
        .then(data => {
            document.getElementById("saldoValor").innerText = `R$ ${data.saldo.toFixed(2)}`;
            document.getElementById("previsaoValor").innerText = `R$ ${data.previsao.toFixed(2)}`;
            document.getElementById("entradaValor").innerText = `R$ ${data.entrada.toFixed(2)}`;
            document.getElementById("saidaValor").innerText = `R$ ${data.saida.toFixed(2)}`;
            document.getElementById("caixinhaValor").innerText = `R$ ${data.cofre.toFixed(2)}`;

            // Agora inicializa a tabela via AJAX
            $('#tabelaFinanceira').DataTable({
                ajax: "/dados_tabela",
                columns: [
                    { data: "Data" },
                    { data: "Tipo" },
                    { data: "Descrição" },
                    { data: "Categoria" },
                    { data: "Valor" },
                    { data: "Saldo Acumulado" }
                ],
                pageLength: 10
            });
        });
});
