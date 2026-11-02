// Ponto de entrada: roteamento por hash (#/agenda, #/nova...) e relógio do topo.
import { prepararDialogo, telaDeErro } from "./ui.js";
import { html, lerRota } from "./util.js";
import * as inicio from "./telas/inicio.js";
import * as agenda from "./telas/agenda.js";
import * as formulario from "./telas/formulario.js";
import * as reservas from "./telas/reservas.js";
import * as frota from "./telas/frota.js";

const TELAS = {
  "": { modulo: inicio, menu: "inicio", titulo: "Início" },
  agenda: { modulo: agenda, menu: "agenda", titulo: "Agenda" },
  nova: { modulo: formulario, menu: "nova", titulo: "Nova reserva" },
  editar: { modulo: formulario, menu: "reservas", titulo: "Editar reserva" },
  reservas: { modulo: reservas, menu: "reservas", titulo: "Reservas" },
  frota: { modulo: frota, menu: "frota", titulo: "Frota" },
  motoristas: { modulo: frota, menu: "frota", titulo: "Motoristas" },
};

const main = document.getElementById("app");
const fab = document.getElementById("fab");
let limpar = null;
let navegacao = 0; // só a navegação mais recente pode mostrar a tela
const progresso = document.createElement("div");
progresso.className = "barra-navegacao";
progresso.setAttribute("aria-hidden", "true");
document.body.append(progresso);

async function navegar() {
  const numero = ++navegacao;
  const rota = lerRota();
  const tela = TELAS[rota.nome] || TELAS[""];

  limpar?.();
  limpar = null;
  document.title = `${tela.titulo} · COSEG Mobilidade`;
  document.querySelectorAll(".menu a").forEach((link) => {
    if (link.dataset.rota === tela.menu) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  fab.hidden = tela.modulo === formulario;

  // A tela atual fica esmaecida (com a barra no topo) enquanto a próxima carrega;
  // nada de "Carregando…" piscando entre uma tela e outra.
  main.classList.add("trocando");
  progresso.className = "barra-navegacao";
  void progresso.offsetWidth; // recomeça a barra do zero
  progresso.className = "barra-navegacao ativo";
  // A tela é montada num "palco" fora da página e só entra quando fica pronta.
  // Se a pessoa já foi para outra tela nesse meio-tempo, este resultado é descartado.
  const palco = document.createElement("div");
  palco.className = "palco";
  let fim = null;
  try {
    fim = (await tela.modulo.render(palco, rota)) || null;
  } catch (erro) {
    console.error(erro);
    palco.innerHTML = telaDeErro(erro).texto;
  }
  if (numero !== navegacao) { fim?.(); return; }
  main.classList.remove("trocando");
  progresso.className = "barra-navegacao terminou";
  main.replaceChildren(palco);
  window.scrollTo({ top: 0, behavior: "instant" });
  limpar = fim;
  main.focus({ preventScroll: true });
  palco.dispatchEvent(new Event("tela-visivel"));
}

function relogio() {
  const el = document.getElementById("relogio");
  const tic = () => {
    const agora = new Date();
    el.textContent = agora.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  };
  tic();
  setInterval(tic, 15000);
}

prepararDialogo();
relogio();
window.addEventListener("hashchange", navegar);
navegar();
