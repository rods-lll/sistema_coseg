// Agenda: linha do tempo do dia, uma faixa por veículo ou por motorista.
// Clicar num espaço vazio abre uma reserva já preenchida com o veículo (ou o
// motorista) e o horário clicado.
import { api } from "../api.js";
import { abrirDetalhe, aviso, icone, recarregar } from "../ui.js";
import {
  STATUS, agoraMinutos, dataExtenso, hojeISO, html, minutos,
  paraHHMM, rotuloDia, somarDias, trocarParams,
} from "../util.js";

const PASSO = 30;     // encaixe do clique na grade, em minutos
const PISTA = 34;     // altura de cada pista quando há blocos que se cruzam

/** Distribui em pistas os blocos que se sobrepõem na mesma faixa
 *  (ex.: "A definir", ou canceladas visíveis junto das confirmadas). */
function pistas(reservas) {
  const fins = [];
  const pistaDe = new Map();
  for (const r of [...reservas].sort((a, b) => minutos(a.saida) - minutos(b.saida))) {
    let i = fins.findIndex((fim) => fim <= minutos(r.saida));
    if (i === -1) { i = fins.length; fins.push(0); }
    fins[i] = minutos(r.retorno);
    pistaDe.set(r.id, i);
  }
  return { pistaDe, total: Math.max(1, fins.length) };
}
const DURACAO = 60;   // duração sugerida para uma reserva nova

export async function render(main, rota) {
  const [veiculos, motoristas] = await Promise.all([api.veiculos(), api.motoristas().catch(() => [])]);
  const categoriaDo = new Map(veiculos.map((v) => [v.codigo, v.categoria]));
  const estado = {
    data: rota.params.get("data") || hojeISO(),
    canceladas: rota.params.get("canceladas") === "1",
    modo: rota.params.get("modo") === "motoristas" ? "motoristas" : "veiculos",
    reservas: [],
  };

  main.innerHTML = html`
    <section class="tela">
      <div class="cabecalho">
        <div>
          <p class="sobrelinha">Agenda da frota</p>
          <h1 class="titulo" id="agenda-titulo"></h1>
          <p class="subtitulo" id="agenda-resumo"></p>
        </div>
        <div class="barra-ferramentas">
          <button class="botao botao-contorno botao-icone" data-ir="-1" aria-label="Dia anterior">${icone.esquerda}</button>
          <button class="botao botao-escuro botao-pequeno" data-ir="hoje">Hoje</button>
          <button class="botao botao-contorno botao-icone" data-ir="1" aria-label="Próximo dia">${icone.direita}</button>
          <label class="sr" for="agenda-data">Escolher data</label>
          <input class="campo-data mono" type="date" id="agenda-data">
        </div>
      </div>

      <div class="card card-agenda">
        <div class="agenda-barra">
          <div class="segmentos" role="group" aria-label="Ver a agenda por">
            <button type="button" data-modo="veiculos">Por veículo</button>
            <button type="button" data-modo="motoristas">Por motorista</button>
          </div>
          <div class="legenda" aria-label="Legenda">
            <span><i class="leg-vl"></i>Leve (VL)</span>
            <span><i class="leg-vc"></i>Coletivo (VC)</span>
            <span><i class="leg-concluida"></i>Concluída</span>
            <span><i class="leg-cancelada"></i>Cancelada</span>
          </div>
          <label class="alternar"><input type="checkbox" id="agenda-canceladas"> Mostrar canceladas</label>
        </div>
        <div class="agenda" id="agenda-grade"></div>
      </div>
      <p class="dica" id="agenda-dica"></p>
    </section>`.texto;

  const grade = main.querySelector("#agenda-grade");
  const campoData = main.querySelector("#agenda-data");
  const campoCanceladas = main.querySelector("#agenda-canceladas");

  const salvarUrl = () => trocarParams("agenda", {
    data: estado.data,
    ...(estado.modo === "motoristas" ? { modo: "motoristas" } : {}),
    ...(estado.canceladas ? { canceladas: "1" } : {}),
  });

  let pedido = 0;
  async function carregar() {
    campoData.value = estado.data;
    campoCanceladas.checked = estado.canceladas;
    salvarUrl();
    main.querySelector("#agenda-titulo").textContent = rotuloDia(estado.data) === dataExtenso(estado.data)
      ? dataExtenso(estado.data) : `${rotuloDia(estado.data)}, ${dataExtenso(estado.data).split(", ")[1]}`;
    grade.setAttribute("aria-busy", "true");
    const numero = ++pedido;
    const dia = estado.data;
    let lista;
    try {
      lista = await api.reservas(dia);
    } catch (erro) {
      if (numero !== pedido) return;
      aviso(erro.message, "erro");
      lista = [];
    }
    if (numero !== pedido) return; // chegou depois de um pedido mais novo
    estado.reservas = lista;
    grade.removeAttribute("aria-busy");
    desenhar();
    rolarParaOFoco();
  }

  // No celular a grade rola para o lado: centraliza no "agora" ou na primeira saída.
  function rolarParaOFoco() {
    if (grade.scrollWidth <= grade.clientWidth) return;
    const inicio = Number(grade.dataset.inicio);
    const total = Number(grade.dataset.total);
    const ativas = estado.reservas.filter((r) => r.status !== "CANCELADA");
    let alvo = 8 * 60;
    if (estado.data === hojeISO()) alvo = agoraMinutos();
    else if (ativas.length) alvo = Math.min(...ativas.map((r) => minutos(r.saida)));
    const interna = grade.firstElementChild;
    const x = 24 + 168 + (interna.clientWidth - 48 - 168) * ((alvo - inicio) / total);
    grade.scrollLeft = Math.max(0, x - grade.clientWidth / 2);
  }

  // Cada faixa da agenda: um veículo ou um motorista.
  function faixas(visiveis) {
    if (estado.modo === "veiculos") {
      return veiculos.map((v) => ({
        tipo: "veiculo",
        chave: v.codigo,
        titulo: v.codigo,
        mono: true,
        pilula: v.categoria,
        pilulaClasse: v.categoria === "VC" ? "pilula-verde" : "pilula-cinza",
        sub: v.ativo ? `${v.capacidade} lugares${v.placa ? ` · ${v.placa}` : ""}` : "Inativo",
        disponivel: v.ativo,
        motivo: `${v.codigo} está inativo e não pode ser reservado.`,
        reservas: visiveis.filter((r) => r.veiculo === v.codigo),
      }));
    }
    const linhas = motoristas.map((m) => {
      const cnhOk = m.cnh_validade >= estado.data;
      return {
        tipo: "motorista",
        chave: m.matricula,
        titulo: m.nome,
        mono: false,
        pilula: `CNH ${m.cnh_categoria}`,
        pilulaClasse: m.dirige.includes("VC") ? "pilula-verde" : "pilula-cinza",
        sub: !m.ativo ? "Inativo" : cnhOk ? `Dirige ${m.dirige.join(" e ")}` : "CNH vencida nesta data",
        disponivel: m.ativo && cnhOk,
        motivo: `${m.nome} não pode ser escalado(a) nesta data (${m.ativo ? "CNH vencida" : "inativo"}).`,
        reservas: visiveis.filter((r) => r.motorista === m.matricula),
      };
    });
    // Faixa extra com reservas sem motorista (antigas, de antes da escala automática).
    const semMotorista = visiveis.filter((r) => !r.motorista);
    if (semMotorista.length) linhas.push({
      tipo: "sem-motorista",
      chave: "",
      titulo: "A definir",
      mono: false,
      pilula: "sem motorista",
      pilulaClasse: "pilula-contorno",
      sub: "Reservas para escalar",
      disponivel: false,
      motivo: "",
      reservas: semMotorista,
    });
    return linhas;
  }

  function desenhar() {
    main.querySelectorAll("[data-modo]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.modo === estado.modo));
    const visiveis = estado.reservas.filter((r) => estado.canceladas || r.status !== "CANCELADA");
    const ativas = estado.reservas.filter((r) => r.status !== "CANCELADA");
    const qtd = ativas.length === 1 ? "1 reserva" : `${ativas.length} reservas`;
    if (estado.modo === "veiculos") {
      const emUso = new Set(ativas.map((r) => r.veiculo)).size;
      main.querySelector("#agenda-resumo").textContent = `${qtd} · ${emUso} de ${veiculos.length} veículos com saída no dia`;
      main.querySelector("#agenda-dica").innerHTML = html`${icone.info} Clique num espaço vazio para reservar aquele veículo naquele horário. Clique numa reserva para ver detalhes, editar ou cancelar.`.texto;
    } else {
      const escalados = new Set(ativas.filter((r) => r.motorista).map((r) => r.motorista)).size;
      const semMotorista = ativas.filter((r) => !r.motorista).length;
      main.querySelector("#agenda-resumo").textContent =
        `${qtd} · ${escalados} motorista(s) escalado(s) · ${semMotorista} sem motorista`;
      main.querySelector("#agenda-dica").innerHTML = html`${icone.info} Clique num espaço vazio para pedir um veículo naquele horário: o sistema escala automaticamente quem tem a CNH certa e está livre.`.texto;
    }

    // Janela padrão 06h–22h, alargada se houver reserva fora dela.
    let inicio = 6 * 60;
    let fim = 22 * 60;
    for (const r of visiveis) {
      inicio = Math.min(inicio, Math.floor(minutos(r.saida) / 60) * 60);
      fim = Math.max(fim, Math.ceil(minutos(r.retorno) / 60) * 60);
    }
    const total = fim - inicio;
    const horas = total / 60;
    const pos = (min) => `${((min - inicio) / total) * 100}%`;
    const larg = (a, b) => `${((b - a) / total) * 100}%`;

    const agora = agoraMinutos();
    const mostrarAgora = estado.data === hojeISO() && agora >= inicio && agora <= fim;
    const porMotorista = estado.modo === "motoristas";

    grade.innerHTML = html`
      <div class="agenda-interna" style="--passo-hora: calc(100% / ${horas})">
        <div class="agenda-linha agenda-cabeca" aria-hidden="true">
          <div></div>
          <div class="agenda-trilho agenda-reguas">
            ${Array.from({ length: horas + 1 }, (_, i) => html`
              <span class="agenda-hora" style="left:${(i / horas) * 100}%">${paraHHMM(inicio + i * 60).slice(0, 2)}h</span>`)}
          </div>
        </div>
        ${faixas(visiveis).map((f) => {
          const { pistaDe, total: nPistas } = pistas(f.reservas);
          const empilhado = nPistas > 1;
          return html`
          <div class="agenda-linha">
            <div class="agenda-veiculo">
              <strong class="${f.mono ? "" : "nome-pessoa"}">${f.titulo}
                <span class="pilula pilula-pequena ${f.pilulaClasse}">${f.pilula}</span>
              </strong>
              <small>${f.sub}</small>
            </div>
            <div class="agenda-trilho ${f.disponivel ? "" : f.tipo === "sem-motorista" ? "sem-motorista" : "inativo"}"
                 data-tipo="${f.tipo}" data-chave="${f.chave}" data-ativo="${f.disponivel ? "1" : "0"}"
                 data-motivo="${f.motivo}" role="group" aria-label="${f.titulo}: ${f.reservas.length} reserva(s)"
                 style="${empilhado ? `height:${nPistas * PISTA + 12}px` : ""}">
              ${f.reservas.map((r) => {
                // Bloco curto mostra menos texto; o detalhe completo fica no title e no clique.
                const dur = minutos(r.retorno) - minutos(r.saida);
                const rotulo = dur >= 120 ? `${r.saida}–${r.retorno}` : r.saida;
                const texto = porMotorista ? `${r.veiculo} · ${r.atividade}` : `${r.atividade} · ${r.motorista_nome || r.solicitante}`;
                return html`
                <button class="bloco ${categoriaDo.get(r.veiculo) === "VC" ? "vc" : ""} ${r.status.toLowerCase()} ${empilhado ? "compacto" : ""}"
                        style="left:${pos(minutos(r.saida))};width:${larg(minutos(r.saida), minutos(r.retorno))}${empilhado ? `;top:${6 + pistaDe.get(r.id) * PISTA}px;bottom:auto;height:${PISTA - 4}px` : ""}"
                        data-reserva="${r.id}"
                        title="${r.saida}–${r.retorno} · ${r.veiculo} · ${r.atividade} · motorista: ${r.motorista_nome || "a definir"}"
                        aria-label="${r.saida} a ${r.retorno}, ${r.veiculo}, ${r.atividade}, motorista ${r.motorista_nome || "a definir"}, ${STATUS[r.status]}">
                  ${dur >= 60 ? html`<b>${rotulo}</b>` : ""}
                  ${dur >= 60 ? html`<span>${texto}</span>` : ""}
                </button>`;
              })}
            </div>
          </div>`;
        })}
        ${mostrarAgora ? html`
          <span class="agenda-agora" aria-hidden="true"
                style="left:calc(24px + 168px + (100% - 48px - 168px) * ${(agora - inicio) / total})"></span>` : ""}
      </div>`.texto;

    grade.dataset.inicio = inicio;
    grade.dataset.total = total;
  }

  // Converte a posição do mouse num horário encaixado na grade de 30 min.
  function horarioNoPonto(trilho, clientX) {
    const caixa = trilho.getBoundingClientRect();
    const proporcao = Math.min(Math.max((clientX - caixa.left) / caixa.width, 0), 1);
    const inicio = Number(grade.dataset.inicio);
    const total = Number(grade.dataset.total);
    let saida = inicio + Math.floor((proporcao * total) / PASSO) * PASSO;
    saida = Math.min(saida, inicio + total - PASSO);
    const retorno = Math.min(saida + DURACAO, inicio + total);
    return { saida, retorno, inicio, total };
  }

  // Bloco fantasma que acompanha o mouse mostrando o horário que será reservado.
  let fantasma = null;
  function mostrarFantasma(e) {
    const trilho = e.target.closest(".agenda-trilho[data-tipo]");
    if (!trilho || trilho.dataset.ativo === "0" || e.target.closest(".bloco")) {
      fantasma?.remove();
      fantasma = null;
      return;
    }
    const { saida, retorno, inicio, total } = horarioNoPonto(trilho, e.clientX);
    if (!fantasma || fantasma.parentElement !== trilho) {
      fantasma?.remove();
      fantasma = document.createElement("span");
      fantasma.className = "agenda-fantasma";
      fantasma.setAttribute("aria-hidden", "true");
      trilho.append(fantasma);
    }
    fantasma.style.left = `${((saida - inicio) / total) * 100}%`;
    fantasma.style.width = `${((retorno - saida) / total) * 100}%`;
    fantasma.textContent = `+ ${paraHHMM(saida)}`;
  }

  function aoClicar(e) {
    const bloco = e.target.closest("[data-reserva]");
    if (bloco) {
      const reserva = estado.reservas.find((r) => String(r.id) === bloco.dataset.reserva);
      abrirDetalhe(reserva, recarregar);
      return;
    }
    const trilho = e.target.closest(".agenda-trilho[data-tipo]");
    if (trilho) {
      if (trilho.dataset.tipo === "sem-motorista") return;
      if (trilho.dataset.ativo === "0") {
        aviso(trilho.dataset.motivo, "erro");
        return;
      }
      const { saida, retorno } = horarioNoPonto(trilho, e.clientX);
      // Na faixa de um veículo, já leva o veículo; motorista quem escolhe é o sistema.
      const params = new URLSearchParams({
        ...(trilho.dataset.tipo === "veiculo" ? { veiculo: trilho.dataset.chave } : {}),
        data: estado.data, saida: paraHHMM(saida), retorno: paraHHMM(retorno),
      });
      location.hash = `#/nova?${params}`;
      return;
    }
    const modo = e.target.closest("[data-modo]")?.dataset.modo;
    if (modo) {
      estado.modo = modo;
      salvarUrl();
      desenhar();
      return;
    }
    const ir = e.target.closest("[data-ir]")?.dataset.ir;
    if (ir) {
      estado.data = ir === "hoje" ? hojeISO() : somarDias(estado.data, Number(ir));
      carregar();
    }
  }

  campoData.addEventListener("change", () => {
    if (campoData.value) { estado.data = campoData.value; carregar(); }
  });
  campoCanceladas.addEventListener("change", () => {
    estado.canceladas = campoCanceladas.checked;
    salvarUrl();
    desenhar();
  });
  main.addEventListener("click", aoClicar);
  grade.addEventListener("mousemove", mostrarFantasma);
  grade.addEventListener("mouseleave", () => { fantasma?.remove(); fantasma = null; });

  // Linha do "agora" anda sozinha.
  const relogio = setInterval(() => { if (estado.data === hojeISO()) desenhar(); }, 60000);

  await carregar();
  main.addEventListener("tela-visivel", rolarParaOFoco, { once: true });
  return () => {
    clearInterval(relogio);
    main.removeEventListener("click", aoClicar);
  };
}
