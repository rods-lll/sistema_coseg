// Reservas: lista agrupada por dia, com busca, filtro de status e período.
import { api } from "../api.js";
import { abrirDetalhe, cancelarReserva, icone, pilulaStatus, recarregar } from "../ui.js";
import { agoraMinutos, dataExtenso, duracao, hojeISO, html, minutos, rotuloDia } from "../util.js";

const PERIODOS = { proximas: "Próximas", hoje: "Hoje", passadas: "Passadas", todas: "Todas" };
const SITUACOES = { todas: "Todos os status", CONFIRMADA: "Confirmadas", CANCELADA: "Canceladas", CONCLUIDA: "Concluídas" };

export async function render(main, rota) {
  const reservas = await api.reservas();
  const filtro = {
    busca: rota.params.get("q") || "",
    periodo: rota.params.get("periodo") || "proximas",
    status: rota.params.get("status") || "todas",
  };

  main.innerHTML = html`
    <section class="tela">
      <div class="cabecalho">
        <div>
          <p class="sobrelinha">Histórico e próximas saídas</p>
          <h1 class="titulo">Reservas</h1>
          <p class="subtitulo" id="contagem"></p>
        </div>
        <a class="botao botao-escuro" href="#/nova">${icone.mais} Nova reserva</a>
      </div>

      <div class="filtros">
        <label class="busca">
          ${icone.busca}
          <span class="sr">Buscar</span>
          <input type="search" id="busca" placeholder="Buscar por pessoa, motorista, setor, atividade, destino ou veículo" value="${filtro.busca}">
        </label>
        <div class="segmentos" role="group" aria-label="Período">
          ${Object.entries(PERIODOS).map(([chave, nome]) => html`
            <button type="button" data-periodo="${chave}" aria-pressed="${filtro.periodo === chave}">${nome}</button>`)}
        </div>
        <div class="segmentos" role="group" aria-label="Status">
          ${Object.entries(SITUACOES).map(([chave, nome]) => html`
            <button type="button" data-status="${chave}" aria-pressed="${filtro.status === chave}">${nome}</button>`)}
        </div>
      </div>

      <div id="lista" class="lista-dias"></div>
    </section>`.texto;

  const lista = main.querySelector("#lista");

  function filtrar() {
    const hoje = hojeISO();
    const agora = agoraMinutos();
    const termo = filtro.busca.toLowerCase();
    const ehFutura = (r) => r.data > hoje || (r.data === hoje && minutos(r.retorno) > agora);

    let resultado = reservas.filter((r) => {
      if (filtro.status !== "todas" && r.status !== filtro.status) return false;
      if (filtro.periodo === "hoje" && r.data !== hoje) return false;
      if (filtro.periodo === "proximas" && !ehFutura(r)) return false;
      if (filtro.periodo === "passadas" && ehFutura(r)) return false;
      if (!termo) return true;
      return [r.solicitante, r.setor, r.atividade, r.destino, r.origem, r.veiculo, r.motorista_nome]
        .some((t) => (t || "").toLowerCase().includes(termo));
    });
    const ordem = (a, b) => (a.data + a.saida).localeCompare(b.data + b.saida);
    resultado = resultado.sort(filtro.periodo === "passadas" ? (a, b) => ordem(b, a) : ordem);
    return resultado;
  }

  function desenhar() {
    const resultado = filtrar();
    main.querySelector("#contagem").textContent =
      `${resultado.length} de ${reservas.length} reservas · ${PERIODOS[filtro.periodo].toLowerCase()} · ${SITUACOES[filtro.status].toLowerCase()}`;

    if (!resultado.length) {
      lista.innerHTML = html`
        <div class="card vazio-grande">
          <strong>Nada por aqui</strong>
          <p>Nenhuma reserva com esses filtros.</p>
        </div>`.texto;
      return;
    }

    const porDia = new Map();
    for (const r of resultado) {
      if (!porDia.has(r.data)) porDia.set(r.data, []);
      porDia.get(r.data).push(r);
    }

    lista.innerHTML = html`${[...porDia].map(([data, doDia]) => html`
      <div class="grupo-dia">
        <h2>${rotuloDia(data) === dataExtenso(data) ? dataExtenso(data) : `${rotuloDia(data)} · ${dataExtenso(data)}`}
          <span class="pilula pilula-pequena pilula-cinza">${doDia.length}</span></h2>
        ${doDia.map((r) => html`
          <article class="reserva ${r.status === "CANCELADA" ? "cancelada" : ""}">
            <div class="reserva-hora">${r.saida} → ${r.retorno}<small>${duracao(r.saida, r.retorno)}</small></div>
            <div class="reserva-info">
              <strong>${r.atividade}</strong>
              <span>${r.solicitante} · ${r.setor} · ${r.motorista_nome ? `motorista ${r.motorista_nome}` : "motorista a definir"}</span>
              <span>${r.origem} → ${r.destino} · ${r.passageiros} ${r.passageiros === 1 ? "pessoa" : "pessoas"}</span>
            </div>
            <div class="reserva-pilulas">
              <span class="pilula pilula-pequena pilula-escura mono">${r.veiculo}</span>
              ${pilulaStatus(r.status)}
            </div>
            <div class="reserva-acoes">
              <button class="botao botao-fantasma botao-pequeno" data-detalhe="${r.id}">Detalhes</button>
              ${r.status === "CONFIRMADA" ? html`
                <a class="botao botao-contorno botao-pequeno" href="#/editar/${r.id}">${icone.editar} Editar</a>
                <button class="botao botao-fantasma botao-pequeno" data-cancelar="${r.id}">Cancelar</button>` : ""}
            </div>
          </article>`)}
      </div>`)}`.texto;
  }

  const acharReserva = (id) => reservas.find((r) => String(r.id) === id);

  function aoClicar(e) {
    const alvo = e.target.closest("button");
    if (!alvo) return;
    if (alvo.dataset.periodo) {
      filtro.periodo = alvo.dataset.periodo;
      main.querySelectorAll("[data-periodo]").forEach((b) => b.setAttribute("aria-pressed", b === alvo));
    } else if (alvo.dataset.status) {
      filtro.status = alvo.dataset.status;
      main.querySelectorAll("[data-status]").forEach((b) => b.setAttribute("aria-pressed", b === alvo));
    } else if (alvo.dataset.detalhe) {
      abrirDetalhe(acharReserva(alvo.dataset.detalhe), recarregar);
      return;
    } else if (alvo.dataset.cancelar) {
      cancelarReserva(acharReserva(alvo.dataset.cancelar), recarregar);
      return;
    } else {
      return;
    }
    desenhar();
  }

  main.addEventListener("click", aoClicar);
  main.querySelector("#busca").addEventListener("input", (e) => {
    filtro.busca = e.target.value.trim();
    desenhar();
  });

  desenhar();
  return () => main.removeEventListener("click", aoClicar);
}
