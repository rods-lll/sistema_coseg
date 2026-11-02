// Nova reserva / editar reserva.
//
// As regras críticas (capacidade, datas, conflito de horário, escala de motorista)
// ficam SÓ no servidor. Enquanto a pessoa preenche, a tela pergunta ao servidor
// (GET /api/disponibilidade/) o que aconteceria com o pedido e apenas mostra a
// resposta. Ao enviar, a tela só muda depois da resposta do POST/PUT; os erros
// voltam no JSON com o "campo" e aparecem no lugar certo.
import { api } from "../api.js";
import { aviso, icone } from "../ui.js";
import { NOME_CATEGORIA, agoraMinutos, dataExtenso, duracao, hojeISO, html, minutos, paraHHMM, somarDias } from "../util.js";

const CAMPOS = ["solicitante", "setor", "atividade", "origem", "destino", "data", "saida", "retorno", "passageiros", "observacoes"];
const OBRIGATORIOS = ["solicitante", "setor", "atividade", "origem", "destino", "data", "saida", "retorno"];
// Nome do campo no JSON de erro da API -> campo da tela.
const CAMPO_DA_TELA = { categoria: "veiculo", "veiculo ou categoria": "veiculo", status: "geral" };

export async function render(main, rota) {
  const editando = rota.nome === "editar";
  const [veiculos, cadastro, original] = await Promise.all([
    api.veiculos(),
    api.colaboradores().catch(() => ({ colaboradores: [], setores: [] })),
    editando ? api.reserva(rota.id) : null,
  ]);

  if (editando && original.status !== "CONFIRMADA") {
    main.innerHTML = html`
      <section class="tela"><div class="card vazio-grande">
        <strong>Esta reserva está ${original.status === "CANCELADA" ? "cancelada" : "concluída"}</strong>
        <p>Só reservas confirmadas podem ser alteradas.</p>
        <p class="acoes-vazio"><a class="botao botao-escuro" href="#/reservas">Voltar para reservas</a></p>
      </div></section>`.texto;
    return null;
  }

  const p = rota.params;
  const inicial = original || {
    solicitante: "", setor: "", atividade: "", origem: "Porto do Itaqui", destino: "",
    ...horarioSugerido(p),
    passageiros: 1, observacoes: "", veiculo: p.get("veiculo") || "",
  };
  const capacidadeDe = Object.fromEntries(veiculos.map((v) => [v.categoria, v.capacidade]));

  main.innerHTML = html`
    <section class="tela">
      <div class="cabecalho">
        <div>
          <p class="sobrelinha">${editando ? `Reserva #${original.id}` : "Nova reserva"}</p>
          <h1 class="titulo">${editando ? "Editar reserva" : "Pedir um veículo"}</h1>
          <p class="subtitulo">${editando
            ? "Altere o que precisar. O servidor confere tudo de novo antes de salvar."
            : "Preencha os dados e veja ao lado, consultado no servidor, o que está livre."}</p>
        </div>
      </div>

      <form class="form-layout" id="form" novalidate>
        <div class="coluna-form">
          <div class="alerta alerta-erro" id="erro-geral" role="alert" hidden></div>

          <fieldset class="card secao">
            <legend class="secao-cabeca"><span class="secao-num">01</span><span class="secao-titulo">Quem está pedindo</span></legend>
            <div class="campos">
              ${campo("solicitante", "Nome do solicitante", inicial.solicitante, { list: "lista-colaboradores", autocomplete: "name", required: true })}
              ${campo("setor", "Setor", inicial.setor, { list: "lista-setores", required: true })}
            </div>
            <datalist id="lista-colaboradores">${cadastro.colaboradores.map((c) => html`<option value="${c.nome}">${c.setor}</option>`)}</datalist>
            <datalist id="lista-setores">${cadastro.setores.map((s) => html`<option value="${s}"></option>`)}</datalist>
          </fieldset>

          <fieldset class="card secao">
            <legend class="secao-cabeca"><span class="secao-num">02</span><span class="secao-titulo">Para quê e para onde</span></legend>
            <div class="campos">
              ${campo("atividade", "Atividade", inicial.atividade, { cheio: true, required: true, placeholder: "Ex.: inspeção técnica no berço 101" })}
              ${campo("origem", "Origem", inicial.origem, { required: true })}
              ${campo("destino", "Destino", inicial.destino, { required: true })}
            </div>
          </fieldset>

          <fieldset class="card secao">
            <legend class="secao-cabeca"><span class="secao-num">03</span><span class="secao-titulo">Quando</span></legend>
            <div class="campos campos-3">
              ${campo("data", "Data", inicial.data, { type: "date", required: true })}
              ${campo("saida", "Saída", inicial.saida, { type: "time", step: 300, required: true })}
              ${campo("retorno", "Retorno previsto", inicial.retorno, { type: "time", step: 300, required: true })}
            </div>
          </fieldset>

          <fieldset class="card secao">
            <legend class="secao-cabeca"><span class="secao-num">04</span><span class="secao-titulo">Quantas pessoas</span></legend>
            <div class="campo" id="campo-passageiros">
              <div class="contador">
                <button type="button" data-passageiros="-1" aria-label="Menos um passageiro">−</button>
                <output id="passageiros-saida" aria-live="polite">${inicial.passageiros}</output>
                <button type="button" data-passageiros="1" aria-label="Mais um passageiro">+</button>
                <input type="hidden" name="passageiros" id="passageiros" value="${inicial.passageiros}">
                <span class="contador-nota" id="passageiros-nota"></span>
              </div>
              <p class="msg-erro" id="erro-passageiros"></p>
            </div>
          </fieldset>

          <fieldset class="card secao">
            <legend class="secao-cabeca"><span class="secao-num">05</span><span class="secao-titulo">Veículo e motorista</span></legend>
            <div class="campo" id="campo-veiculo" role="radiogroup" aria-labelledby="rotulo-veiculo">
              <span class="rotulo" id="rotulo-veiculo">Veículo ou categoria pretendida</span>
              <div class="escolhas" id="escolhas"></div>
              <p class="msg-erro" id="erro-veiculo"></p>
            </div>
            <div class="campo" id="campo-motorista">
              <span class="rotulo">Motorista · escalado pelo sistema</span>
              <div class="escala" id="escala" aria-live="polite"></div>
              <p class="msg-erro" id="erro-motorista"></p>
            </div>
            ${campo("observacoes", "Observações (opcional)", inicial.observacoes, { textarea: true, placeholder: "Ex.: levar EPI, motorista precisa de crachá" })}
          </fieldset>
        </div>

        <aside class="card card-escuro resumo" aria-label="Resumo da reserva">
          <div class="resumo-bloco">
            <span class="resumo-rotulo">Quando</span>
            <span class="resumo-valor" id="r-data"></span>
            <span class="resumo-valor mono" id="r-horario"></span>
            <span class="resumo-nota" id="r-duracao"></span>
          </div>
          <div class="resumo-bloco">
            <span class="resumo-rotulo">Grupo</span>
            <span class="resumo-valor" id="r-grupo"></span>
            <span class="resumo-nota" id="r-grupo-nota"></span>
          </div>
          <div class="resumo-bloco">
            <span class="resumo-rotulo">Disponibilidade no horário</span>
            <span class="resumo-nota" id="r-livres"></span>
            <div class="chips" id="r-chips"></div>
          </div>
          <div class="resumo-bloco">
            <span class="resumo-rotulo">Veículo</span>
            <span class="resumo-valor" id="r-veiculo"></span>
          </div>
          <div class="resumo-bloco">
            <span class="resumo-rotulo">Motorista</span>
            <span class="resumo-valor" id="r-motorista"></span>
            <span class="resumo-nota" id="r-motorista-nota"></span>
          </div>
          <div id="r-alertas" class="alertas" aria-live="polite"></div>
          <p class="resumo-fonte" id="r-fonte">${icone.info} Consultando o servidor…</p>
          <button class="botao botao-menta botao-grande" type="submit" id="enviar">
            ${icone.check} ${editando ? "Salvar alterações" : "Confirmar reserva"}
          </button>
          ${editando ? html`<a class="botao botao-contorno" href="#/reservas">Descartar alterações</a>` : ""}
        </aside>
      </form>
    </section>`.texto;

  const form = main.querySelector("#form");
  const $ = (id) => form.querySelector(`#${id}`);
  const valor = (nome) => (form.elements[nome]?.value ?? "").trim();
  const passageiros = () => Number($("passageiros").value) || 1;

  // Escolha atual: automática (categoria mínima), uma categoria ou um veículo.
  let escolha = inicial.veiculo ? { tipo: "veiculo", valor: inicial.veiculo } : { tipo: "auto" };
  let ultima = null;        // última resposta do servidor
  let consulta = 0;         // descarta respostas antigas que cheguem fora de ordem
  let espera = null;

  // ------------------------------------------- consulta ao servidor ---
  function agendarConsulta() {
    clearTimeout(espera);
    $("r-fonte").innerHTML = html`<span class="spinner spinner-pequeno" aria-hidden="true"></span> Consultando o servidor…`.texto;
    espera = setTimeout(consultar, 220);
  }

  async function consultar() {
    const numero = ++consulta;
    const params = {
      data: valor("data"), saida: valor("saida"), retorno: valor("retorno"), passageiros: passageiros(),
      ...(escolha.tipo === "veiculo" ? { veiculo: escolha.valor } : {}),
      ...(escolha.tipo === "categoria" ? { categoria: escolha.valor } : {}),
      ...(editando ? { ignorar: original.id } : {}),
    };
    if (!params.data || !params.saida || !params.retorno) {
      desenhar(null, "Preencha data, saída e retorno para ver a disponibilidade.");
      return;
    }
    try {
      const resposta = await api.disponibilidade(params);
      if (numero === consulta) desenhar(resposta);
    } catch (erro) {
      if (numero === consulta) desenhar(null, erro.message);
    }
  }

  // --------------------------------------------------------- desenho ---
  function desenhar(r, problema) {
    ultima = r;
    const data = valor("data");
    const saida = valor("saida");
    const retorno = valor("retorno");
    const pessoas = passageiros();
    const minima = r?.categoria_minima;

    $("passageiros-saida").textContent = pessoas;
    $("passageiros-nota").textContent = !r ? "" : minima
      ? `cabe em veículo ${NOME_CATEGORIA[minima].toLowerCase()} (${minima}, até ${capacidadeDe[minima]})`
      : "nenhum veículo da frota leva esse grupo";

    // Se o veículo escolhido deixou de servir, volta para a escolha automática.
    let avisoTroca = "";
    const situacoes = r?.veiculos || [];
    const atual = situacoes.find((s) => escolha.tipo === "veiculo" && s.codigo === escolha.valor);
    if (atual && !atual.livre) {
      avisoTroca = `${atual.codigo} não serve para esse pedido (${atual.motivo.toLowerCase()}). Voltei para a escolha automática.`;
      escolha = { tipo: "auto" };
      agendarConsulta();
    }
    const marcado = (tipo, v = "") => (escolha.tipo === tipo && (escolha.valor || "") === v ? "checked" : "");
    $("escolhas").innerHTML = html`
      <div class="escolha escolha-auto">
        <input type="radio" name="veiculo" id="v-auto" value="auto" ${marcado("auto")}>
        <label for="v-auto"><strong>Automático</strong><small>${minima ? `qualquer ${minima} livre` : "conforme o grupo"}</small></label>
      </div>
      ${["VL", "VC"].map((c) => html`
        <div class="escolha escolha-auto">
          <input type="radio" name="veiculo" id="v-cat-${c}" value="categoria:${c}" ${marcado("categoria", c)}
                 ${minima === "VC" && c === "VL" ? "disabled" : ""}>
          <label for="v-cat-${c}"><strong>Qualquer ${c}</strong><small>${NOME_CATEGORIA[c].toLowerCase()} · até ${capacidadeDe[c]}</small></label>
        </div>`)}
      ${(situacoes.length ? situacoes : veiculos.map((v) => ({ codigo: v.codigo, categoria: v.categoria, livre: true, motivo: "" })))
        .map((s) => html`
        <div class="escolha">
          <input type="radio" name="veiculo" id="v-${s.codigo}" value="veiculo:${s.codigo}"
                 ${marcado("veiculo", s.codigo)} ${s.livre ? "" : "disabled"}>
          <label for="v-${s.codigo}"><strong>${s.codigo}</strong><small>${s.categoria}${s.motivo ? ` · ${s.motivo}` : ""}</small></label>
        </div>`)}`.texto;

    // Motorista que o servidor escalaria.
    const exigida = r?.veiculo && situacoes.find((s) => s.codigo === r.veiculo)?.categoria === "VC" ? "D ou E" : "B ou superior";
    $("escala").innerHTML = (!r ? html`<p class="contador-nota">${problema || ""}</p>`
      : !r.motoristas_cadastrados ? html`<p class="contador-nota">Nenhum motorista cadastrado: a reserva segue sem escala.</p>`
      : !r.veiculo ? html`<p class="contador-nota">Defina um veículo disponível para ver quem será escalado.</p>`
      : html`
      <div class="escala-escolhido ${r.motorista ? "" : "vazio"}">
        ${r.motorista ? html`
          <span class="escala-avatar" aria-hidden="true">${r.motorista.nome.split(" ").map((x) => x[0]).slice(0, 2).join("")}</span>
          <span><strong>${r.motorista.nome}</strong>
            <small>CNH ${r.motorista.cnh_categoria} · ${r.motorista.matricula === original?.motorista ? "continua na reserva" : "escalado pelo servidor"}</small></span>` : html`
          <span><strong>Ninguém disponível</strong><small>Nenhum motorista com CNH ${exigida} livre nesse horário.</small></span>`}
      </div>
      <p class="contador-nota">Critério do servidor: CNH ${exigida} válida e livre no horário; entre esses, a CNH mais básica que serve (para poupar quem dirige o coletivo) e quem rodou menos no dia.</p>
      <ul class="escala-lista">
        ${r.motoristas.map((m) => html`
          <li class="${m.livre ? "livre" : ""} ${m.escalado ? "escolhido" : ""}">
            <span class="nome-pessoa">${m.nome}</span>
            <span class="mono">CNH ${m.cnh_categoria}</span>
            <span>${m.escalado ? "Será escalado(a)" : m.motivo}</span>
          </li>`)}
      </ul>`).texto;

    // Resumo (o que vem do servidor está marcado como tal).
    $("r-data").textContent = data ? dataExtenso(data) : "Escolha a data";
    $("r-horario").textContent = saida && retorno ? `${saida} → ${retorno}` : "";
    $("r-duracao").textContent = saida && retorno && duracao(saida, retorno) ? `${duracao(saida, retorno)} de uso` : "";
    $("r-grupo").textContent = `${pessoas} ${pessoas === 1 ? "pessoa" : "pessoas"}`;
    $("r-grupo-nota").textContent = !r ? "" : minima
      ? `Categoria mínima: ${minima} (${NOME_CATEGORIA[minima].toLowerCase()}, até ${capacidadeDe[minima]} lugares)`
      : "Nenhum veículo da frota leva esse grupo";

    const alvo = escolha.tipo === "categoria" ? escolha.valor : minima;
    const relevantes = situacoes.filter((s) => !alvo || s.categoria === alvo);
    $("r-livres").textContent = r && alvo ? `${relevantes.filter((s) => s.livre).length} de ${relevantes.length} veículos ${alvo} livres` : "";
    $("r-chips").innerHTML = html`${relevantes.map((s) => html`
      <span class="chip ${s.livre ? "livre" : "ocupado"}" title="${s.motivo}">${s.codigo}</span>`)}`.texto;

    $("r-veiculo").textContent = !r ? "—" : r.veiculo
      ? (escolha.tipo === "veiculo" ? r.veiculo : `Automático → ${r.veiculo}`)
      : "Nenhum disponível";
    $("r-motorista").textContent = !r ? "—"
      : !r.motoristas_cadastrados ? "Sem escala"
      : !r.veiculo ? "Depende do veículo"
      : r.motorista ? `Automático → ${r.motorista.nome}` : "Ninguém disponível";
    $("r-motorista-nota").textContent = r?.motoristas?.length
      ? `${r.motoristas.filter((m) => m.livre).length} motorista(s) com CNH ${exigida} livre(s) no horário` : "";

    // Erros de data/horário que o servidor apontou aparecem também embaixo do campo.
    for (const nome of ["data", "saida", "retorno"]) {
      const erro = (r?.erros || []).find((e) => e.campo === nome);
      $(`campo-${nome}`).classList.toggle("erro", Boolean(erro));
      $(`erro-${nome}`).innerHTML = erro ? html`${icone.alerta}<span>${erro.erro}</span>`.texto : "";
    }

    // Avisos: os erros vêm do servidor (mesmas regras que ele aplica ao gravar).
    const alertas = [];
    if (avisoTroca) alertas.push(["aviso", avisoTroca]);
    if (problema) alertas.push(["aviso", problema]);
    for (const e of r?.erros || []) alertas.push(["erro", e.erro]);
    $("r-alertas").innerHTML = html`${alertas.map(([tipo, texto]) => html`
      <div class="alerta alerta-${tipo}">${icone.alerta}<span>${texto}</span></div>`)}`.texto;
    $("r-fonte").innerHTML = r
      ? html`${icone.check} Disponibilidade confirmada pelo servidor agora.`.texto
      : html`${icone.info} Aguardando dados para consultar o servidor.`.texto;
  }

  // ----------------------------------------------------------- erros ---
  function limparErros() {
    form.querySelectorAll(".campo.erro").forEach((el) => el.classList.remove("erro"));
    form.querySelectorAll(".msg-erro").forEach((el) => { el.innerHTML = ""; });
    form.querySelectorAll("[aria-invalid]").forEach((el) => el.removeAttribute("aria-invalid"));
    $("erro-geral").hidden = true;
  }

  function marcarErro(nome, mensagem) {
    const alvo = CAMPO_DA_TELA[nome] || nome;
    const caixa = $(`campo-${alvo}`);
    const msg = $(`erro-${alvo}`);
    if (!caixa || !msg) {
      $("erro-geral").innerHTML = html`${icone.alerta}<span>${mensagem}</span>`.texto;
      $("erro-geral").hidden = false;
      return $("erro-geral");
    }
    caixa.classList.add("erro");
    msg.innerHTML = html`${icone.alerta}<span>${mensagem}</span>`.texto;
    form.elements[alvo]?.setAttribute?.("aria-invalid", "true");
    return caixa;
  }

  // ---------------------------------------------------------- envio ---
  async function enviar(e) {
    e.preventDefault();
    limparErros();

    // Validação de experiência: só avisa o que está vazio antes de gastar uma ida
    // ao servidor. Ele valida tudo de novo (inclusive isto) ao receber.
    const vazios = OBRIGATORIOS.filter((c) => !valor(c));
    if (vazios.length) {
      vazios.forEach((c) => marcarErro(c, "Preencha este campo."));
      $(`campo-${vazios[0]}`).scrollIntoView({ behavior: "smooth", block: "center" });
      form.elements[vazios[0]].focus({ preventScroll: true });
      aviso(`Faltam ${vazios.length} campo(s) obrigatório(s).`, "erro");
      return;
    }

    const dados = Object.fromEntries(CAMPOS.map((c) => [c, valor(c)]));
    dados.passageiros = passageiros();
    if (escolha.tipo === "veiculo") dados.veiculo = escolha.valor;
    else dados.categoria = escolha.tipo === "categoria" ? escolha.valor : ultima?.categoria_minima || "VC";

    const botao = $("enviar");
    botao.disabled = true;
    const textoBotao = botao.innerHTML;
    botao.innerHTML = html`<span class="spinner" aria-hidden="true"></span> Enviando ao servidor…`.texto;
    try {
      const resposta = editando ? await api.atualizar(original.id, dados) : await api.criar(dados);
      const r = resposta.reserva;
      aviso(`${resposta.mensagem} ${r.veiculo} · ${r.saida}–${r.retorno}${r.motorista_nome ? ` · motorista ${r.motorista_nome}` : ""}.`);
      location.hash = `#/agenda?data=${r.data}`;
    } catch (erro) {
      const corpo = erro.corpo || {};
      let primeiro;
      if (corpo.campos?.length) {
        corpo.campos.forEach((c) => {
          const marcadoErro = marcarErro(c, "Campo obrigatório.");
          primeiro ??= marcadoErro;
        });
      } else {
        primeiro = marcarErro(corpo.campo || "geral", erro.message);
      }
      if (erro.status === 409) agendarConsulta(); // a agenda mudou: pergunta de novo
      primeiro?.scrollIntoView({ behavior: "smooth", block: "center" });
      aviso(erro.message, "erro");
    } finally {
      botao.disabled = false;
      botao.innerHTML = textoBotao;
    }
  }

  // ---------------------------------------------------------- eventos ---
  form.addEventListener("input", (e) => {
    if (e.target.name === "veiculo") return;
    e.target.closest(".campo")?.classList.remove("erro");
    if (e.target.name === "solicitante") {
      // Nome conhecido: completa o setor sozinho.
      const conhecido = cadastro.colaboradores.find((c) => c.nome.toLowerCase() === e.target.value.trim().toLowerCase());
      if (conhecido && !valor("setor")) form.elements.setor.value = conhecido.setor;
    }
    if (["data", "saida", "retorno"].includes(e.target.name)) agendarConsulta();
  });
  form.addEventListener("change", (e) => {
    if (e.target.name !== "veiculo") return;
    const [tipo, v] = e.target.value.split(":");
    escolha = tipo === "auto" ? { tipo: "auto" } : { tipo, valor: v };
    $("campo-veiculo").classList.remove("erro");
    $("erro-veiculo").innerHTML = "";
    agendarConsulta();
  });
  form.addEventListener("click", (e) => {
    const passo = e.target.closest("[data-passageiros]")?.dataset.passageiros;
    if (!passo) return;
    const novo = Math.min(30, Math.max(1, passageiros() + Number(passo)));
    $("passageiros").value = novo;
    $("passageiros-saida").textContent = novo;
    $("campo-passageiros").classList.remove("erro");
    agendarConsulta();
  });
  form.addEventListener("submit", enviar);

  desenhar(null);
  await consultar();
  if (!editando) main.addEventListener("tela-visivel", () => form.elements.solicitante.focus({ preventScroll: true }), { once: true });
  return () => clearTimeout(espera);
}

// Só um valor inicial para não abrir o formulário já com erro: hoje, a próxima
// meia hora; tarde da noite, amanhã às 08:00. Quem valida o horário é o servidor.
function horarioSugerido(p) {
  if (p.get("saida")) {
    return { data: p.get("data") || hojeISO(), saida: p.get("saida"), retorno: p.get("retorno") || paraHHMM(Math.min(minutos(p.get("saida")) + 60, 23 * 60 + 55)) };
  }
  const data = p.get("data") || hojeISO();
  if (data !== hojeISO()) return { data, saida: "08:00", retorno: "10:00" };
  const saida = Math.ceil((agoraMinutos() + 1) / 30) * 30;
  if (saida > 22 * 60) return { data: somarDias(hojeISO(), 1), saida: "08:00", retorno: "10:00" };
  return { data, saida: paraHHMM(saida), retorno: paraHHMM(Math.min(saida + 120, 23 * 60 + 55)) };
}

function campo(nome, rotulo, valor, opcoes = {}) {
  const { type = "text", cheio = false, textarea = false, required = false, ...extra } = opcoes;
  const atributos = Object.entries(extra).map(([k, v]) => html` ${k}="${v}"`);
  const obrigatorio = required ? html` required aria-required="true"` : "";
  return html`
    <div class="campo ${cheio || textarea ? "campo-cheio" : ""}" id="campo-${nome}">
      <label for="${nome}">${rotulo}</label>
      ${textarea
        ? html`<textarea id="${nome}" name="${nome}"${atributos} aria-describedby="erro-${nome}">${valor}</textarea>`
        : html`<input id="${nome}" name="${nome}" type="${type}" value="${valor}"${atributos}${obrigatorio} aria-describedby="erro-${nome}">`}
      <p class="msg-erro" id="erro-${nome}"></p>
    </div>`;
}
