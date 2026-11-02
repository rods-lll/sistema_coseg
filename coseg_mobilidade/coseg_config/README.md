# COSEG Mobilidade — reserva de veículos do Porto do Itaqui (PBL 1 + PBL 2)

Sistema de reserva de veículos do Porto do Itaqui. Python + Django, organizado em
Arquitetura Hexagonal (Ports and Adapters).

## Estrutura

```
core/                       # regras de negócio em Python puro (sem Django)
  domain/                   # entidades, validadores e exceções
  ports/                    # contratos dos repositórios (Protocol)
  services/                 # ReservaService
adapters/
  saida/persistencia/       # models, migrations, repositórios ORM, seed
  entrada/web/              # views, rotas, serialização JSON, painel HTML
config/                     # settings e urls do projeto Django
tests/
  dominio/                  # testes das regras, sem banco
  integracao/               # persistência, CRUD e rotas HTTP
```

## Como rodar

```
pip install -r requirements.txt
python manage.py migrate
python manage.py carregar_seed
python manage.py createsuperuser
python manage.py runserver
```

Painel: http://127.0.0.1:8000/painel/
Admin: http://127.0.0.1:8000/admin/ (entre com o usuário criado no `createsuperuser`).
O formulário de reservas do Admin passa pelas mesmas regras da API
(capacidade, data, horários e conflito).

## Interface web (PBL 2)

Abra **http://127.0.0.1:8000/** com o servidor rodando. É uma página única em
HTML + CSS + JavaScript puro (sem framework), servida pelo Django e consumindo a API.

| Tela | O que faz |
|---|---|
| Início | Resumo do dia: reservas de hoje, veículos livres agora, quem está na rua e próximas saídas |
| Agenda | Linha do tempo do dia, por veículo ou **por motorista** (com a faixa "A definir"). Clicar num espaço vazio abre a reserva já preenchida com veículo e horário |
| Nova reserva | Formulário com painel ao vivo, **consultado no servidor** (`/api/disponibilidade/`): veículos livres no horário, categoria mínima pelo número de pessoas e **prévia do motorista que será escalado**. O campo "Veículo ou categoria pretendida" aceita *Automático*, *Qualquer VL*, *Qualquer VC* ou um veículo específico. Erros do servidor aparecem no campo certo |
| Reservas | Lista por dia com busca e filtros de período e status; editar e cancelar |
| Frota | Abas **Veículos** e **Motoristas**: placa, modelo, CNH, validade, situação e ocupação do dia |

```
adapters/entrada/web/
  templates/web/app.html     # esqueleto da página
  static/web/app.css         # identidade visual (a mesma da apresentação)
  static/web/js/
    main.js                  # rotas (#/agenda, #/nova...) e relógio
    api.js                   # chamadas à API e tratamento de erro
    util.js                  # HTML seguro e formatação de datas (nenhuma regra de negócio)
    ui.js                    # avisos, diálogos, detalhe da reserva
    telas/                   # inicio, agenda, formulario, reservas, frota
```

**Estrutura, estilo e comportamento separados:** o HTML vem do template e dos
componentes de cada tela, toda a aparência está em `app.css` (os únicos `style=` que
sobram são posições calculadas, como o início e a largura de um bloco na agenda) e o
comportamento fica nos módulos JS.

**Sem regra duplicada no JavaScript:** capacidade, datas, conflito de horário e
escala de motorista existem só no `ReservaService`. Enquanto a pessoa preenche, a tela
chama `GET /api/disponibilidade/`, que roda essas mesmas regras **sem gravar nada**
(`ReservaService.simular`) e devolve o que aconteceria; a tela só desenha a resposta.
A única checagem local é "campo obrigatório vazio", para não gastar uma ida ao servidor;
o servidor confere tudo de novo no POST/PUT. O painel antigo continua em `/painel/`.

**Exclusão = cancelamento lógico:** `DELETE /api/reservas/<id>/` não apaga a linha,
muda o status para `CANCELADA` e guarda `cancelada_em`. Assim o histórico de uso da
frota fica preservado para auditoria e o horário volta a ficar livre.

## Deploy na Vercel

O projeto já vem pronto para a Vercel (`config/wsgi.py`, `pyproject.toml`, `build.py`).

1. Em **Settings › General › Root Directory**, use `coseg_mobilidade/coseg_config`.
2. **Banco (recomendado):** em **Storage**, crie um banco **Neon (Postgres)** e conecte ao
   projeto. A Vercel cria a variável `DATABASE_URL` sozinha e, a cada deploy, o `build.py`
   aplica as migrations e carrega a frota.
3. Em **Settings › Environment Variables**, crie `DJANGO_SECRET_KEY` com um texto longo e
   aleatório.
4. Faça um novo deploy.

Para criar o usuário do admin **sem terminal**, crie na Vercel as variáveis
`DJANGO_SUPERUSER_USERNAME` e `DJANGO_SUPERUSER_PASSWORD` e faça um novo deploy: o
`build.py` cria o usuário (ou atualiza a senha, se ele já existir). Ou, no seu computador,
com o endereço do banco no terminal (`SUPABASE_DB_URL` ou `DATABASE_URL`):

```
python manage.py createsuperuser
```

**Usando Supabase em vez de Neon:** no Supabase, abra **Connect** no projeto e copie a URL do
**Transaction pooler** (porta 6543). Cole em `SUPABASE_DB_URL` (tem prioridade sobre a
`DATABASE_URL`, que alguma integração pode ter criado com outro valor) nas variáveis da Vercel, trocando
`[YOUR-PASSWORD]` pela senha do banco. O projeto reconhece o pooler sozinho. Não use a
"Direct connection": ela só funciona em IPv6, e a Vercel não alcança.

**Sem Postgres** o site também sobe, em *modo demonstração*: o SQLite fica em `/tmp` do
servidor e é recriado (com a frota) sempre que a Vercel liga um servidor novo, ou seja,
as reservas somem de tempos em tempos e o admin não tem usuário. Pior: a Vercel pode
atender cada requisição num servidor diferente, cada um com o seu arquivo, então uma reserva
recém-criada pode não aparecer na agenda, e cada servidor novo demora alguns segundos para
preparar o banco. Serve para
mostrar, não para usar de verdade.

## Modelo de dados

| Tabela | Campos principais | Relacionamentos e restrições |
|---|---|---|
| `SetorModel` | nome (único) | 1 setor → N colaboradores |
| `ColaboradorModel` | nome, e-mail, telefone | N → 1 setor; nome único dentro do setor |
| `VeiculoModel` | código (único), categoria VL/VC, placa (única), modelo, ativo | 1 veículo → N reservas |
| `MotoristaModel` | matrícula (única), nome, telefone, nº da CNH (único), categoria da CNH (B/C/D/E), validade da CNH, ativo | 1 motorista → N reservas (PROTECT) |
| `ReservaModel` | atividade, origem, destino, data, saída, retorno, passageiros, categoria pretendida, observações, status | N → 1 colaborador; N → 1 veículo (PROTECT); N → 0..1 motorista; retorno > saída; passageiros ≥ 1; status válido; índice (veículo, data) |

Todas as tabelas guardam `criado_em`/`atualizado_em` (na reserva, `criada_em`/`atualizada_em`).

- **Status da reserva:** `CONFIRMADA` → `CANCELADA` ou `CONCLUIDA`. Cancelar não apaga:
  a reserva fica no histórico (com `cancelada_em`) e deixa de ocupar o veículo.
- **Escala automática de motorista:** quem pede o veículo não escolhe o motorista. Ao criar
  a reserva, o sistema escala um motorista **ativo**, com **CNH compatível** com o veículo
  escolhido (leve: B ou superior; coletivo de 18 lugares: D ou E), **CNH válida** na data e
  **livre** no horário. Entre os que podem, escolhe: (1) numa edição, o motorista que já estava,
  se ainda puder; (2) a CNH mais básica que serve, para poupar quem dirige o coletivo; (3) quem
  rodou menos minutos no dia; (4) ordem alfabética. Sem ninguém disponível, a reserva é recusada
  (`SEM_MOTORISTA_DISPONIVEL`, 409). O COSEG pode trocar a escala à mão pelo admin (ou mandando
  `"motorista"` na API), e as mesmas regras são conferidas. Os motoristas do `carregar_seed` são
  fictícios, só para demonstração.
- **Veículo inativo** (ex.: em manutenção) não pode ser reservado nem é escolhido na
  alocação automática por categoria.
- A API continua recebendo `solicitante` e `setor` como texto: o servidor reaproveita o
  colaborador e o setor já cadastrados (sem diferenciar maiúsculas) ou cria novos.
- As migrations `0003` a `0005` convertem os dados antigos (texto) para as tabelas novas
  e podem ser desfeitas.

## Testes

```
python manage.py test tests
```

Testes de unidade (regras do domínio), de integração (API, persistência, admin,
disponibilidade) e de escala de motoristas.

### Evidências da interface (navegador)

```
pip install playwright
python -m playwright install chromium
python tests/e2e/evidencias.py
```

O script sobe o Django num banco temporário, abre a interface num Chromium e percorre
CRUD (criar, ler, editar, cancelar), integração com a API, mensagens de erro
(campos obrigatórios, conflito 409, capacidade) e responsividade (390, 768 e 1366 px,
sem rolagem horizontal). O resultado fica em
[`docs/evidencias/RELATORIO.md`](docs/evidencias/RELATORIO.md), com os prints ao lado.

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/veiculos/` | Lista a frota |
| GET | `/api/motoristas/` | Lista motoristas com CNH, validade e o que cada um dirige |
| GET | `/api/colaboradores/?setor=` | Lista colaboradores e setores cadastrados (sugestões do formulário) |
| GET | `/api/disponibilidade/?data=&saida=&retorno=&passageiros=&veiculo=` ou `&categoria=` (`&ignorar=<id>` ao editar) | Simula o pedido sem gravar: situação de cada veículo e motorista, veículo e motorista que seriam escolhidos e os erros que o POST daria |
| GET | `/api/reservas/?data=AAAA-MM-DD` | Lista reservas (filtro opcional) |
| POST | `/api/reservas/` | Cria reserva (201, 400 ou 409) |
| GET, PUT, DELETE | `/api/reservas/<id>/` | Consulta, altera ou cancela (DELETE marca como cancelada, sem apagar) |

Respostas de erro: `{"sucesso": false, "codigo": "...", "erro": "...", "campo": "..."}`.
Códigos: `CAMPOS_OBRIGATORIOS`, `CAPACIDADE_EXCEDIDA`, `PERIODO_INVALIDO`,
`VEICULO_INATIVO`, `MOTORISTA_NAO_HABILITADO`, `CNH_VENCIDA`, `MOTORISTA_INATIVO` (400);
`CONFLITO_DE_HORARIO`, `CONFLITO_DE_MOTORISTA`, `SEM_VEICULO_DISPONIVEL`, `SEM_MOTORISTA_DISPONIVEL`,
`RESERVA_NAO_EDITAVEL` (409); `RESERVA_NAO_ENCONTRADA` (404).
O motorista é escalado automaticamente; o campo opcional `"motorista": "MOT-001"` (matrícula)
no POST/PUT serve só para o COSEG indicar alguém à mão.
