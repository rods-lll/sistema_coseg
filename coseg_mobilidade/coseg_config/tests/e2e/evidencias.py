"""Evidências da interface web (PBL 2): CRUD, integração, mensagens e responsividade.

Sobe o Django num banco SQLite temporário (o seu db.sqlite3 não é tocado),
carrega o seed, abre a interface num Chromium de verdade e percorre os fluxos.
Cada verificação vira uma linha em docs/evidencias/RELATORIO.md e cada etapa
importante vira um print em docs/evidencias/.

Como rodar (na pasta coseg_config):
    pip install playwright
    python -m playwright install chromium
    python tests/e2e/evidencias.py

Não faz parte do `manage.py test` porque precisa de navegador.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = RAIZ / "docs" / "evidencias"
PORTA = 8790
BASE = f"http://127.0.0.1:{PORTA}"
AMANHA = (dt.date.today() + dt.timedelta(days=1)).isoformat()

resultados: list[tuple[str, str, bool, str]] = []  # (grupo, verificação, ok, detalhe)


def checar(grupo: str, descricao: str, condicao: bool, detalhe: str = "") -> None:
    resultados.append((grupo, descricao, bool(condicao), detalhe))
    print(f"[{'OK' if condicao else 'FALHOU'}] {grupo}: {descricao} {detalhe}")


def api(metodo: str, caminho: str, corpo: dict | None = None) -> tuple[int, dict]:
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(BASE + caminho, data=dados, method=metodo,
                                 headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def subir_servidor() -> subprocess.Popen:
    banco = Path(tempfile.mkdtemp()) / "evidencias.sqlite3"
    env = {**os.environ, "COSEG_SQLITE": str(banco), "DJANGO_DEBUG": "1"}
    manage = [sys.executable, "manage.py"]
    subprocess.run(manage + ["migrate", "-v0"], cwd=RAIZ, env=env, check=True)
    subprocess.run(manage + ["carregar_seed", "-v0"], cwd=RAIZ, env=env, check=True)
    proc = subprocess.Popen(manage + ["runserver", str(PORTA), "--noreload"], cwd=RAIZ, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", PORTA)) == 0:
                return proc
        time.sleep(0.2)
    proc.kill()
    raise RuntimeError("o servidor não subiu")


def print_(page: Page, nome: str, inteira: bool = False) -> None:
    # Avisos antigos (de etapas anteriores) não devem cobrir o que o print quer mostrar.
    page.evaluate("document.querySelectorAll('#avisos .aviso').forEach((a, i, t) => i < t.length - 1 && a.remove())")
    page.screenshot(path=SAIDA / f"{nome}.png", full_page=inteira)


def esperar_servidor(page: Page) -> None:
    """Espera o formulário mostrar a resposta mais recente de /api/disponibilidade/."""
    page.wait_for_timeout(300)  # a tela espera 220 ms sem digitação antes de consultar
    page.wait_for_load_state("networkidle")
    expect(page.locator("#r-fonte")).to_contain_text("confirmada pelo servidor", timeout=8000)


def preencher(page: Page, atividade: str, saida="08:00", retorno="10:00") -> None:
    page.fill("#solicitante", "Telma Regina")
    page.fill("#setor", "Operações")
    page.fill("#atividade", atividade)
    page.fill("#destino", "Berço 101")
    page.fill("#data", AMANHA)
    page.fill("#saida", saida)
    page.fill("#retorno", retorno)
    esperar_servidor(page)


def fluxos_desktop(page: Page) -> None:
    consultas: list[str] = []
    page.on("request", lambda r: "/api/disponibilidade/" in r.url and consultas.append(r.url))

    # --- Integração: o formulário consulta o servidor, não calcula sozinho ---
    page.goto(f"{BASE}/#/nova")
    esperar_servidor(page)
    checar("Integração", "Formulário pede a disponibilidade ao servidor (GET /api/disponibilidade/)",
           len(consultas) >= 1, f"({len(consultas)} consulta(s))")
    js = (RAIZ / "adapters/entrada/web/static/web/js/util.js").read_text()
    checar("Integração", "util.js não tem mais regra de capacidade/conflito/escala",
           not any(p in js for p in ("CAPACIDADE", "conflita", "escalarMotorista")))
    print_(page, "01-formulario-desktop", inteira=True)

    # --- Mensagens: campos obrigatórios ---
    page.fill("#solicitante", "")
    page.click("#enviar")
    expect(page.locator("#erro-solicitante")).to_contain_text("Preencha este campo")
    checar("Mensagens", "Campos obrigatórios vazios aparecem marcados no próprio campo",
           page.locator(".campo.erro").count() >= 3, f"({page.locator('.campo.erro').count()} campos)")
    print_(page, "02-campos-obrigatorios")

    # --- CRUD: criar escolhendo a categoria pretendida ---
    preencher(page, "Inspeção técnica (evidência)")
    page.check("#v-cat-VL")
    esperar_servidor(page)
    previsto = page.locator("#r-motorista").inner_text()
    with page.expect_response(lambda r: r.url.endswith("/api/reservas/") and r.request.method == "POST") as resp:
        page.click("#enviar")
    corpo = resp.value.json()
    reserva = corpo.get("reserva", {})
    checar("CRUD", "Criar (POST) com 'Qualquer VL' devolve 201 e um VL",
           resp.value.status == 201 and reserva.get("veiculo", "").startswith("VL"),
           f"(#{reserva.get('id')} {reserva.get('veiculo')})")
    checar("Integração", "Motorista mostrado antes de enviar é o que o servidor escalou",
           bool(reserva.get("motorista_nome")) and reserva["motorista_nome"] in previsto,
           f"({reserva.get('motorista_nome')})")
    expect(page.locator(".aviso.ok").last).to_contain_text("sucesso")
    checar("Mensagens", "Aviso de sucesso depois da resposta do servidor", True)
    page.wait_for_url("**/#/agenda**")
    page.wait_for_timeout(400)
    print_(page, "03-criada-na-agenda")
    rid, veiculo = reserva["id"], reserva["veiculo"]

    # --- Integração: o veículo ocupado aparece bloqueado com o motivo do servidor ---
    page.goto(f"{BASE}/#/nova")
    preencher(page, "Outra saída no mesmo horário")
    radio = page.locator(f"#v-{veiculo}")
    motivo = page.locator(f"label[for='v-{veiculo}']").inner_text()
    checar("Integração", f"{veiculo} aparece ocupado no mesmo horário (motivo vem do servidor)",
           radio.is_disabled() and "Ocupado" in motivo, f"({motivo.splitlines()[-1]})")
    print_(page, "04-veiculo-ocupado")

    # --- Mensagens: 409 quando alguém reserva o mesmo carro antes de você ---
    livre = page.locator("#escolhas input[value^='veiculo:VL']:not([disabled])").first
    alvo = livre.get_attribute("value").split(":")[1]
    livre.check()
    esperar_servidor(page)
    status, _ = api("POST", "/api/reservas/", {
        "solicitante": "Rodrigo Lima", "setor": "Engenharia", "atividade": "Chegou primeiro",
        "origem": "Porto do Itaqui", "destino": "Centro", "data": AMANHA, "saida": "09:00",
        "retorno": "09:30", "passageiros": 1, "veiculo": alvo})
    page.wait_for_load_state("networkidle")
    with page.expect_response(lambda r: r.url.endswith("/api/reservas/") and r.request.method == "POST") as resp:
        page.click("#enviar")
    erro = resp.value.json()
    expect(page.locator("#erro-veiculo")).not_to_be_empty()
    checar("Mensagens", "Conflito de horário: 409 do servidor aparece no campo do veículo",
           status == 201 and resp.value.status == 409 and erro.get("codigo") == "CONFLITO_DE_HORARIO",
           f"({erro.get('codigo')}: {erro.get('erro')})")
    page.wait_for_timeout(500)
    print_(page, "05-conflito-409")

    # --- Mensagens: capacidade (erro devolvido pela consulta do servidor) ---
    page.goto(f"{BASE}/#/nova")
    preencher(page, "Grupo grande", saida="14:00", retorno="15:00")
    page.check("#v-cat-VL")
    for _ in range(6):
        page.click("[data-passageiros='1']")
    esperar_servidor(page)
    page.locator("#r-alertas").scroll_into_view_if_needed()
    page.evaluate("document.getElementById('avisos').replaceChildren()")
    alerta = page.locator("#r-alertas").inner_text()
    checar("Mensagens", "7 pessoas em 'Qualquer VL': o servidor avisa que excede a capacidade",
           "comporta até 4" in alerta, f"({alerta.strip()[:90]})")
    checar("Integração", "Categoria mínima vira VC e 'Qualquer VL' fica bloqueado",
           page.locator("#v-cat-VL").is_disabled())
    print_(page, "06-capacidade")

    # --- CRUD: ler (lista e API) ---
    st, lida = api("GET", f"/api/reservas/{rid}/")
    lida = lida.get("reserva", {})
    checar("CRUD", "Ler (GET /api/reservas/<id>/) devolve a reserva criada",
           st == 200 and lida.get("id") == rid)

    # --- CRUD: editar ---
    page.goto(f"{BASE}/#/editar/{rid}")
    esperar_servidor(page)
    page.fill("#retorno", "11:00")
    esperar_servidor(page)
    with page.expect_response(lambda r: f"/api/reservas/{rid}/" in r.url and r.request.method == "PUT") as resp:
        page.click("#enviar")
    depois = api("GET", f"/api/reservas/{rid}/")[1].get("reserva", {})
    checar("CRUD", "Editar (PUT) muda o retorno e mantém o motorista",
           resp.value.status == 200 and depois.get("retorno") == "11:00"
           and depois.get("motorista") == reserva.get("motorista"),
           f"(retorno {depois.get('retorno')}, motorista {depois.get('motorista_nome')})")
    page.wait_for_timeout(400)
    print_(page, "07-editada")

    # --- CRUD: excluir (cancelamento lógico) ---
    page.goto(f"{BASE}/#/reservas")
    page.click(f"[data-cancelar='{rid}']")
    print_(page, "08-confirmar-cancelamento")
    with page.expect_response(lambda r: f"/api/reservas/{rid}/" in r.url and r.request.method == "DELETE") as resp:
        page.click("[data-resposta='sim']")
    expect(page.locator(".aviso.ok").last).to_contain_text("cancelada")
    cancelada = api("GET", f"/api/reservas/{rid}/")[1].get("reserva", {})
    checar("CRUD", "Excluir (DELETE) cancela a reserva e ela fica no histórico",
           resp.value.status == 200 and cancelada.get("status") == "CANCELADA")
    page.wait_for_timeout(400)
    print_(page, "09-cancelada")


def navegacao_com_servidor_lento(navegador) -> None:
    """Servidor lento (como na Vercel): trocar de tela rápido não pode mostrar a tela errada."""
    page = navegador.new_page(viewport={"width": 1366, "height": 900}, locale="pt-BR")
    page.add_init_script("""
      const original = window.fetch;
      window.fetch = (url, opcoes) => new Promise((ok) => setTimeout(ok,
        String(url).includes('/api/reservas/') && !(opcoes && opcoes.method && opcoes.method !== 'GET') ? 1500 : 300
      )).then(() => original(url, opcoes));
    """)
    page.goto(f"{BASE}/#/")
    page.wait_for_load_state("networkidle")
    page.click(".menu a[data-rota='reservas']")
    page.wait_for_timeout(100)
    page.click(".menu a[data-rota='nova']")
    page.wait_for_timeout(2500)
    titulo = page.locator("main h1").first.inner_text()
    checar("Integração", "Servidor lento: Reservas → Nova reserva rápido mostra a tela certa",
           titulo == "Pedir um veículo", f"(tela: {titulo})")
    page.close()


TELAS = [("inicio", "#/"), ("nova", "#/nova"), ("agenda", f"#/agenda?data={AMANHA}"),
         ("reservas", "#/reservas"), ("frota", "#/frota"), ("motoristas", "#/motoristas")]
TAMANHOS = [("celular", 390, 844), ("tablet", 768, 1024), ("desktop", 1366, 900)]


def responsividade(navegador) -> None:
    for nome_tam, largura, altura in TAMANHOS:
        page = navegador.new_page(viewport={"width": largura, "height": altura}, locale="pt-BR")
        estouros = []
        for nome, rota in TELAS:
            page.goto(f"{BASE}/{rota}")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(300)
            sobra = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            if sobra > 0:
                estouros.append(f"{nome} (+{sobra}px)")
            menu = page.evaluate("(() => { const m = document.querySelector('.menu'); return m.scrollWidth - m.clientWidth })()")
            if menu > 0:
                estouros.append(f"menu de {nome} cortado (+{menu}px)")
            if nome_tam != "desktop" or nome in ("inicio", "agenda"):
                print_(page, f"resp-{nome_tam}-{nome}")
        checar("Responsividade", f"{nome_tam} {largura}px: nenhuma tela com rolagem horizontal e o menu inteiro visível",
               not estouros, ", ".join(estouros))
        page.close()


def relatorio() -> None:
    linhas = [
        "# Evidências de teste da interface (PBL 2)",
        "",
        f"Gerado por `python tests/e2e/evidencias.py` em {dt.datetime.now():%d/%m/%Y %H:%M}, "
        "num Chromium real, contra o Django com banco temporário e o seed do projeto.",
        "",
        "| Grupo | Verificação | Resultado |",
        "|---|---|---|",
    ]
    for grupo, desc, ok, detalhe in resultados:
        linhas.append(f"| {grupo} | {desc} {detalhe} | {'✅ ok' if ok else '❌ falhou'} |")
    linhas += ["", "## Prints", ""]
    for png in sorted(SAIDA.glob("*.png")):
        linhas.append(f"- [{png.stem}]({png.name})")
    (SAIDA / "RELATORIO.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def main() -> int:
    SAIDA.mkdir(parents=True, exist_ok=True)
    for antigo in SAIDA.glob("*.png"):
        antigo.unlink()
    servidor = subir_servidor()
    erros_console: list[str] = []
    try:
        with sync_playwright() as p:
            navegador = p.chromium.launch()
            page = navegador.new_page(viewport={"width": 1366, "height": 900}, locale="pt-BR")
            page.on("console", lambda m: m.type == "error" and erros_console.append(m.text))
            page.on("pageerror", lambda e: erros_console.append(str(e)))
            fluxos_desktop(page)
            page.close()
            navegacao_com_servidor_lento(navegador)
            responsividade(navegador)
            navegador.close()
        # 409 é esperado no teste de conflito (o navegador loga a resposta como erro de rede);
        # fontes externas (Google Fonts) podem não carregar sem internet.
        inesperados = [e for e in erros_console
                       if "409" not in e and "ERR_TUNNEL" not in e and "ERR_INTERNET" not in e]
        checar("Geral", "Nenhum erro de JavaScript no console", not inesperados, "; ".join(inesperados)[:200])
    finally:
        servidor.terminate()
        relatorio()
    falhas = [r for r in resultados if not r[2]]
    print(f"\n{len(resultados) - len(falhas)}/{len(resultados)} verificações ok → {SAIDA / 'RELATORIO.md'}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
