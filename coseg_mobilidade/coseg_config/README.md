# COSEG Mobilidade — camada de servidor (PBL 1)

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

## Modelo de dados

| Tabela | Campos principais | Relacionamentos e restrições |
|---|---|---|
| `SetorModel` | nome (único) | 1 setor → N colaboradores |
| `ColaboradorModel` | nome, e-mail, telefone | N → 1 setor; nome único dentro do setor |
| `VeiculoModel` | código (único), categoria VL/VC, placa (única), modelo, ativo | 1 veículo → N reservas |
| `ReservaModel` | atividade, origem, destino, data, saída, retorno, passageiros, categoria pretendida, observações, status | N → 1 colaborador; N → 1 veículo (PROTECT); retorno > saída; passageiros ≥ 1; status válido; índice (veículo, data) |

Todas as tabelas guardam `criado_em`/`atualizado_em` (na reserva, `criada_em`/`atualizada_em`).

- **Status da reserva:** `CONFIRMADA` → `CANCELADA` ou `CONCLUIDA`. Cancelar não apaga:
  a reserva fica no histórico (com `cancelada_em`) e deixa de ocupar o veículo.
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

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/veiculos/` | Lista a frota |
| GET | `/api/reservas/?data=AAAA-MM-DD` | Lista reservas (filtro opcional) |
| POST | `/api/reservas/` | Cria reserva (201, 400 ou 409) |
| GET, PUT, DELETE | `/api/reservas/<id>/` | Consulta, altera ou cancela (DELETE marca como cancelada, sem apagar) |

Respostas de erro: `{"sucesso": false, "codigo": "...", "erro": "...", "campo": "..."}`.
Códigos: `CAMPOS_OBRIGATORIOS`, `CAPACIDADE_EXCEDIDA`, `PERIODO_INVALIDO`,
`VEICULO_INATIVO` (400); `CONFLITO_DE_HORARIO`, `SEM_VEICULO_DISPONIVEL`,
`RESERVA_NAO_EDITAVEL` (409); `RESERVA_NAO_ENCONTRADA` (404).
