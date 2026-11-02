// Início: resumo do dia — reservas, veículos livres agora e próximas saídas.
import { api } from "../api.js";
import { abrirDetalhe, icone, recarregar } from "../ui.js";
import { agoraMinutos, dataExtenso, hojeISO, html, minutos, rotuloDia, saudacao, somarDias } from "../util.js";

export async function render(main) {
  const [veiculos, reservas] = await Promise.all([api.veiculos(), api.reservas()]);

  const hoje = hojeISO();
  const agora = agoraMinutos();
  const daqui7 = somarDias(hoje, 7);
  const confirmadas = reservas.filter((r) => r.status === "CONFIRMADA");
  const deHoje = reservas.filter((r) => r.data === hoje && r.status !== "CANCELADA");
  const emUso = confirmadas.filter(
    (r) => r.data === hoje && minutos(r.saida) <= agora && agora < minutos(r.retorno),
  );
  const ativos = veiculos.filter((v) => v.ativo);
  const ocupados = new Set(emUso.map((r) => r.veiculo));
  const livresAgora = ativos.filter((v) => !ocupados.has(v.codigo)).length;
  const futuras = confirmadas
    .filter((r) => r.data > hoje || (r.data === hoje && minutos(r.saida) > agora))
    .sort((a, b) => (a.data + a.saida).localeCompare(b.data + b.saida));
  const proximos7 = futuras.filter((r) => r.data <= daqui7).length;
  const leves = veiculos.filter((v) => v.categoria === "VL").length;
  const inativos = veiculos.length - ativos.length;

  const porId = new Map(reservas.map((r) => [String(r.id), r]));

  main.innerHTML = html`
    <section class="tela">
      <div class="hero">
        <div>
          <p class="sobrelinha sobrelinha-menta">COSEG Mobilidade · Porto do Itaqui</p>
          <h1 class="hero-titulo">${saudacao()},<br>COSEG.</h1>
          <p>${dataExtenso(hoje)}. ${deHoje.length === 1 ? "1 reserva" : `${deHoje.length} reservas`} na agenda de hoje
            e ${livresAgora} de ${ativos.length} veículos livres agora.</p>
          <div class="hero-acoes">
            <a class="botao botao-menta botao-grande" href="#/nova">${icone.mais} Nova reserva</a>
            <a class="botao botao-contorno botao-grande" href="#/agenda">Ver agenda ${icone.seta}</a>
          </div>
        </div>
        <div class="hero-arte" aria-hidden="true">
          ${Array.from({ length: 9 }, () => html`<span class="esfera"></span>`)}
        </div>
      </div>

      <div class="grade grade-4">
        <div class="card card-cinza kpi">
          <span class="kpi-rotulo">Reservas hoje</span>
          <span class="kpi-numero">${deHoje.length}</span>
          <span class="kpi-nota">${emUso.length} em andamento agora</span>
        </div>
        <div class="card card-menta kpi">
          <span class="kpi-rotulo">Livres agora</span>
          <span class="kpi-numero">${livresAgora}<small>/ ${ativos.length}</small></span>
          <span class="kpi-nota">veículos ativos sem reserva neste minuto</span>
        </div>
        <div class="card card-verde kpi">
          <span class="kpi-rotulo">Próximos 7 dias</span>
          <span class="kpi-numero">${proximos7}</span>
          <span class="kpi-nota">reservas confirmadas a partir de agora</span>
        </div>
        <div class="card kpi">
          <span class="kpi-rotulo">Frota</span>
          <span class="kpi-numero">${veiculos.length}</span>
          <span class="kpi-nota">${leves} leves · ${veiculos.length - leves} coletivos${inativos ? ` · ${inativos} inativo(s)` : ""}</span>
        </div>
      </div>

      <div class="grade grade-2">
        <div class="card">
          <div class="card-topo">
            <h2 class="card-titulo">Em uso agora</h2>
            <span class="pilula pilula-pequena pilula-escura">${emUso.length}</span>
          </div>
          <div class="lista">
            ${emUso.length ? emUso.map((r) => {
              const total = minutos(r.retorno) - minutos(r.saida);
              const feito = Math.min(100, Math.round(((agora - minutos(r.saida)) / total) * 100));
              return html`
                <button class="item" data-reserva="${r.id}">
                  <span class="item-hora">${r.veiculo}</span>
                  <span class="item-corpo">
                    <span class="item-titulo">${r.atividade}</span>
                    <span class="item-sub">${r.motorista_nome ? `${r.motorista_nome} ao volante` : r.solicitante} · ${r.destino}</span>
                    <span class="progresso" aria-label="${feito}% do horário reservado"><span style="width:${feito}%"></span></span>
                  </span>
                  <span class="mono item-volta">volta ${r.retorno}</span>
                </button>`;
            }) : html`<p class="vazio">Nenhum veículo fora agora. A frota inteira está no pátio.</p>`}
          </div>
        </div>

        <div class="card">
          <div class="card-topo">
            <h2 class="card-titulo">Próximas saídas</h2>
            <a class="botao botao-fantasma botao-pequeno" href="#/reservas">Ver todas ${icone.seta}</a>
          </div>
          <div class="lista">
            ${futuras.length ? futuras.slice(0, 5).map((r) => html`
              <button class="item" data-reserva="${r.id}">
                <span class="item-hora">${r.saida}</span>
                <span class="item-corpo">
                  <span class="item-titulo">${r.atividade}</span>
                  <span class="item-sub">${rotuloDia(r.data)} · ${r.solicitante} · ${r.passageiros} pessoa(s)</span>
                </span>
                <span class="pilula pilula-pequena pilula-cinza mono">${r.veiculo}</span>
              </button>`) : html`<p class="vazio">Nenhuma saída agendada daqui para frente.</p>`}
          </div>
        </div>
      </div>
    </section>`.texto;

  main.addEventListener("click", aoClicar);
  function aoClicar(e) {
    const alvo = e.target.closest("[data-reserva]");
    if (alvo) abrirDetalhe(porId.get(alvo.dataset.reserva), recarregar);
  }
  return () => main.removeEventListener("click", aoClicar);
}
