// Componentes compartilhados: ícones, avisos, diálogo, detalhe da reserva.
import { api } from "./api.js";
import { STATUS, dataExtenso, duracao, html, seguro } from "./util.js";

const svg = (caminho) => seguro(`<svg viewBox="0 0 24 24" aria-hidden="true">${caminho}</svg>`);

export const icone = {
  mais: svg('<path d="M12 5v14M5 12h14"/>'),
  seta: svg('<path d="M5 12h14M13 6l6 6-6 6"/>'),
  esquerda: svg('<path d="M15 6l-6 6 6 6"/>'),
  direita: svg('<path d="M9 6l6 6-6 6"/>'),
  fechar: svg('<path d="M6 6l12 12M18 6L6 18"/>'),
  alerta: svg('<path d="M12 8v5M12 16.5v.5"/><path d="M10.3 3.9L2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>'),
  check: svg('<path d="M5 12.5l4.5 4.5L19 7.5"/>'),
  relogio: svg('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
  calendario: svg('<rect x="3.5" y="5" width="17" height="15" rx="3"/><path d="M3.5 10h17M8 3v4M16 3v4"/>'),
  editar: svg('<path d="M4 20h4L19 9l-4-4L4 16v4z"/>'),
  busca: svg('<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>'),
  info: svg('<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>'),
  externo: svg('<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>'),
};

/** Redesenha a tela atual (depois de cancelar, por exemplo). */
export const recarregar = () => window.dispatchEvent(new HashChangeEvent("hashchange"));

// --------------------------------------------------------------- avisos ---
export function aviso(mensagem, tipo = "ok") {
  const area = document.getElementById("avisos");
  const el = document.createElement("div");
  el.className = `aviso ${tipo}`;
  el.setAttribute("role", tipo === "erro" ? "alert" : "status");
  el.innerHTML = html`${tipo === "erro" ? icone.alerta : icone.check}<span>${mensagem}</span>`.texto;
  area.append(el);
  setTimeout(() => el.remove(), tipo === "erro" ? 6500 : 4000);
}

export const pilulaStatus = (status) => {
  const classe = { CONFIRMADA: "pilula-menta", CANCELADA: "pilula-contorno", CONCLUIDA: "pilula-cinza" }[status];
  return html`<span class="pilula pilula-pequena ${classe}">${STATUS[status] || status}</span>`;
};

// -------------------------------------------------------------- diálogo ---
const dialogo = () => document.getElementById("dialogo");

export function abrirDialogo(conteudo) {
  const d = dialogo();
  d.innerHTML = conteudo.texto;
  if (!d.open) d.showModal();
  return d;
}

export function fecharDialogo() {
  const d = dialogo();
  if (d.open) d.close();
}

export function prepararDialogo() {
  const d = dialogo();
  // Clique fora do conteúdo (no fundo escurecido) fecha.
  d.addEventListener("click", (e) => { if (e.target === d) d.close(); });
  d.addEventListener("click", (e) => { if (e.target.closest("[data-fechar]")) d.close(); });
  window.addEventListener("hashchange", fecharDialogo);
}

/** Pergunta de confirmação; resolve true/false. */
export function confirmar({ titulo, texto, botao = "Confirmar", perigo = false }) {
  return new Promise((resolver) => {
    const d = abrirDialogo(html`
      <div class="dialogo-corpo">
        <div class="dialogo-topo"><h2 id="dialogo-titulo">${titulo}</h2></div>
        <p>${texto}</p>
        <div class="dialogo-acoes">
          <button class="botao botao-fantasma" data-resposta="nao">Voltar</button>
          <button class="botao ${perigo ? "botao-perigo" : "botao-escuro"}" data-resposta="sim">${botao}</button>
        </div>
      </div>`);
    const ao = (e) => {
      const botaoClicado = e.target.closest("[data-resposta]");
      if (!botaoClicado) return;
      d.removeEventListener("click", ao);
      d.close();
      resolver(botaoClicado.dataset.resposta === "sim");
    };
    d.addEventListener("click", ao);
    d.addEventListener("close", () => { d.removeEventListener("click", ao); resolver(false); }, { once: true });
    d.querySelector('[data-resposta="sim"]').focus();
  });
}

// --------------------------------------------------- detalhe da reserva ---
export async function cancelarReserva(reserva, aoMudar) {
  const ok = await confirmar({
    titulo: "Cancelar esta reserva?",
    texto: `${reserva.atividade} · ${reserva.veiculo} · ${reserva.saida}–${reserva.retorno}. Ela continua no histórico e o horário fica livre.`,
    botao: "Cancelar reserva",
    perigo: true,
  });
  if (!ok) return;
  try {
    await api.cancelar(reserva.id);
    aviso(`Reserva de ${reserva.veiculo} cancelada. O horário está livre.`);
    aoMudar?.();
  } catch (erro) {
    aviso(erro.message, "erro");
  }
}

export function abrirDetalhe(reserva, aoMudar) {
  const editavel = reserva.status === "CONFIRMADA";
  const d = abrirDialogo(html`
    <div class="dialogo-corpo">
      <div class="dialogo-topo">
        <div>
          <p class="sobrelinha">Reserva #${reserva.id} · ${pilulaStatus(reserva.status)}</p>
          <h2 id="dialogo-titulo" class="dialogo-titulo">${reserva.atividade}</h2>
        </div>
        <button class="botao botao-fantasma botao-icone" data-fechar aria-label="Fechar">${icone.fechar}</button>
      </div>
      <div class="faixa-horario">
        ${icone.calendario}
        <div>
          <div>${dataExtenso(reserva.data)}</div>
          <div class="mono">${reserva.saida} → ${reserva.retorno} <small class="faixa-duracao">${duracao(reserva.saida, reserva.retorno)}</small></div>
        </div>
      </div>
      <dl class="detalhes">
        <div><dt>Veículo</dt><dd class="mono">${reserva.veiculo}</dd></div>
        <div><dt>Motorista</dt><dd>${reserva.motorista_nome || "A definir"}</dd></div>
        <div><dt>Passageiros</dt><dd>${reserva.passageiros}</dd></div>
        <div><dt>Solicitante</dt><dd>${reserva.solicitante}</dd></div>
        <div><dt>Setor</dt><dd>${reserva.setor}</dd></div>
        <div><dt>Origem</dt><dd>${reserva.origem}</dd></div>
        <div><dt>Destino</dt><dd>${reserva.destino}</dd></div>
        ${reserva.observacoes ? html`<div class="cheio"><dt>Observações</dt><dd>${reserva.observacoes}</dd></div>` : ""}
      </dl>
      <div class="dialogo-acoes">
        ${editavel ? html`
          <button class="botao botao-fantasma" data-acao="cancelar">Cancelar reserva</button>
          <a class="botao botao-escuro" href="#/editar/${reserva.id}">${icone.editar} Editar</a>` : html`
          <button class="botao botao-escuro" data-fechar>Fechar</button>`}
      </div>
    </div>`);
  d.querySelector('[data-acao="cancelar"]')?.addEventListener("click", () => cancelarReserva(reserva, aoMudar));
}

export const telaDeErro = (erro) => html`
  <section class="tela">
    <div class="card vazio-grande">
      <strong>Algo deu errado</strong>
      <p>${erro.message}</p>
      <p class="acoes-vazio"><a class="botao botao-escuro" href="#/">Voltar ao início</a></p>
    </div>
  </section>`;
