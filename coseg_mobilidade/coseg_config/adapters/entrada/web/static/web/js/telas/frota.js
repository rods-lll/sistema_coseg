// Frota: veículos e motoristas, cada um com a ocupação de hoje numa mini linha do tempo.
import { api } from "../api.js";
import { icone } from "../ui.js";
import { NOME_CATEGORIA, dataCurta, deISO, hojeISO, html, minutos, primeiroNome } from "../util.js";

const INICIO = 6 * 60;
const FIM = 22 * 60;

const faixa = (min) => Math.min(Math.max(min, INICIO), FIM);
const pct = (min) => ((faixa(min) - INICIO) / (FIM - INICIO)) * 100;

function miniDia(reservas) {
  return html`
    <div>
      <div class="mini-dia" role="img" aria-label="Ocupação de hoje: ${reservas.map((r) => `${r.saida} a ${r.retorno}`).join(", ") || "livre o dia todo"}">
        ${reservas.map((r) => html`<span style="left:${pct(minutos(r.saida))}%;width:${pct(minutos(r.retorno)) - pct(minutos(r.saida))}%"></span>`)}
      </div>
      <div class="mini-dia-horas" aria-hidden="true"><span>06h</span><span>14h</span><span>22h</span></div>
    </div>`;
}

function abas(atual) {
  return html`
    <div class="segmentos" role="tablist" aria-label="O que mostrar">
      <a role="tab" class="segmento" href="#/frota" aria-selected="${atual === "veiculos"}">Veículos</a>
      <a role="tab" class="segmento" href="#/motoristas" aria-selected="${atual === "motoristas"}">Motoristas</a>
    </div>`;
}

export async function render(main, rota) {
  const modo = rota.nome === "motoristas" ? "motoristas" : "veiculos";
  const hoje = hojeISO();
  const [veiculos, motoristas, deHoje] = await Promise.all([
    api.veiculos(), api.motoristas().catch(() => []), api.reservas(hoje),
  ]);
  const ativas = deHoje.filter((r) => r.status !== "CANCELADA");
  main.innerHTML = (modo === "veiculos"
    ? telaVeiculos(veiculos, ativas)
    : telaMotoristas(motoristas, ativas, hoje)).texto;
  return null;
}

function telaVeiculos(veiculos, ativas) {
  const leves = veiculos.filter((v) => v.categoria === "VL").length;
  const inativos = veiculos.filter((v) => !v.ativo).length;
  return html`
    <section class="tela">
      <div class="cabecalho">
        <div>
          <p class="sobrelinha">Frota do COSEG</p>
          <h1 class="titulo">${veiculos.length} veículos</h1>
          <p class="subtitulo">${leves} leves (até 4 pessoas) · ${veiculos.length - leves} coletivos (até 18)${inativos ? ` · ${inativos} fora de operação` : ""}</p>
        </div>
        <div class="barra-ferramentas">
          ${abas("veiculos")}
          <a class="botao botao-contorno" href="/admin/persistencia/veiculomodel/">${icone.externo} Gerenciar no admin</a>
        </div>
      </div>

      <div class="veiculos">
        ${veiculos.map((v) => {
          const reservas = ativas.filter((r) => r.veiculo === v.codigo);
          const coletivo = v.categoria === "VC";
          return html`
            <article class="card veiculo ${coletivo && v.ativo ? "card-verde" : ""} ${v.ativo ? "" : "inativo"}">
              <div class="card-topo-pilulas">
                <span class="pilula pilula-pequena ${coletivo ? "pilula-menta" : "pilula-escura"}">${NOME_CATEGORIA[v.categoria]} · ${v.categoria}</span>
                <span class="pilula pilula-pequena ${v.ativo ? "pilula-contorno" : "pilula-cinza"}">${v.ativo ? "Ativo" : "Inativo"}</span>
              </div>
              <p class="veiculo-codigo">${v.codigo}</p>
              <dl class="veiculo-dados">
                <div><dt>Capacidade</dt><dd>${v.capacidade} lugares</dd></div>
                <div><dt>Hoje</dt><dd>${reservas.length === 1 ? "1 reserva" : `${reservas.length} reservas`}</dd></div>
                <div><dt>Placa</dt><dd class="mono">${v.placa || "—"}</dd></div>
                <div><dt>Modelo</dt><dd>${v.modelo || "—"}</dd></div>
              </dl>
              ${miniDia(reservas)}
              ${v.ativo
                ? html`<a class="botao ${coletivo ? "botao-menta" : "botao-escuro"}" href="#/nova?veiculo=${v.codigo}">Reservar ${v.codigo} ${icone.seta}</a>`
                : html`<p class="kpi-nota">Fora de operação. Reative no admin quando voltar.</p>`}
            </article>`;
        })}
      </div>
    </section>`;
}

function situacaoCnh(m, hoje) {
  const dias = Math.round((deISO(m.cnh_validade) - deISO(hoje)) / 86400000);
  if (dias < 0) return { texto: "Vencida", classe: "alerta-erro", ok: false };
  if (dias <= 30) return { texto: `Vence em ${dias} dia(s)`, classe: "alerta-aviso", ok: true };
  return { texto: "Válida", classe: "", ok: true };
}

function telaMotoristas(motoristas, ativas, hoje) {
  const ativos = motoristas.filter((m) => m.ativo);
  const coletivo = motoristas.filter((m) => m.dirige.includes("VC")).length;
  const vencidas = motoristas.filter((m) => !situacaoCnh(m, hoje).ok).length;
  return html`
    <section class="tela">
      <div class="cabecalho">
        <div>
          <p class="sobrelinha">Equipe do COSEG</p>
          <h1 class="titulo">${motoristas.length} motoristas</h1>
          <p class="subtitulo">${ativos.length} ativos · ${coletivo} habilitados para o coletivo (CNH D ou E)${vencidas ? ` · ${vencidas} com CNH vencida` : ""}. A escala é automática, pela CNH e pela disponibilidade.</p>
        </div>
        <div class="barra-ferramentas">
          ${abas("motoristas")}
          <a class="botao botao-contorno" href="/admin/persistencia/motoristamodel/">${icone.externo} Cadastrar no admin</a>
        </div>
      </div>

      ${motoristas.length ? html`
      <div class="veiculos">
        ${motoristas.map((m) => {
          const escalas = ativas.filter((r) => r.motorista === m.matricula);
          const cnh = situacaoCnh(m, hoje);
          const dirigeColetivo = m.dirige.includes("VC");
          const disponivel = m.ativo && cnh.ok;
          return html`
            <article class="card veiculo ${dirigeColetivo && disponivel ? "card-verde" : ""} ${disponivel ? "" : "inativo"}">
              <div class="card-topo-pilulas">
                <span class="pilula pilula-pequena ${dirigeColetivo ? "pilula-menta" : "pilula-escura"}">CNH ${m.cnh_categoria} · dirige ${m.dirige.join(" e ")}</span>
                <span class="pilula pilula-pequena ${m.ativo ? "pilula-contorno" : "pilula-cinza"}">${m.ativo ? "Ativo" : "Inativo"}</span>
              </div>
              <div>
                <p class="motorista-nome">${m.nome}</p>
                <p class="mono motorista-matricula">${m.matricula}</p>
              </div>
              <dl class="veiculo-dados">
                <div><dt>Telefone</dt><dd>${m.telefone || "—"}</dd></div>
                <div><dt>Hoje</dt><dd>${escalas.length === 1 ? "1 escala" : `${escalas.length} escalas`}</dd></div>
                <div><dt>Validade da CNH</dt><dd class="mono">${dataCurta(m.cnh_validade)}</dd></div>
                <div><dt>Situação</dt><dd>${cnh.texto}</dd></div>
              </dl>
              ${cnh.classe ? html`<div class="alerta ${cnh.classe}">${icone.alerta}<span>CNH ${cnh.texto.toLowerCase()}${cnh.ok ? "" : ": não pode ser escalado(a)"}.</span></div>` : ""}
              ${miniDia(escalas)}
              ${disponivel
                ? html`<a class="botao ${dirigeColetivo ? "botao-menta" : "botao-escuro"}" href="#/agenda?modo=motoristas">Ver escala de ${primeiroNome(m.nome)} ${icone.seta}</a>`
                : html`<p class="kpi-nota">${m.ativo ? "Fora da escala automática até a CNH ser renovada no admin." : "Inativo: fora da escala automática. Reative no admin quando voltar."}</p>`}
            </article>`;
        })}
      </div>` : html`
      <div class="card vazio-grande">
        <strong>Nenhum motorista cadastrado</strong>
        <p>Cadastre no admin ou rode <span class="mono">python manage.py carregar_seed</span>.</p>
      </div>`}
    </section>`;
}
