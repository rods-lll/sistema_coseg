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
python manage.py runserver
```

Painel: http://127.0.0.1:8000/painel/

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
| GET, PUT, DELETE | `/api/reservas/<id>/` | Consulta, altera ou cancela |

Respostas de erro: `{"sucesso": false, "codigo": "...", "erro": "...", "campo": "..."}`.
Códigos: `CAMPOS_OBRIGATORIOS`, `CAPACIDADE_EXCEDIDA`, `PERIODO_INVALIDO`,
`CONFLITO_DE_HORARIO`, `SEM_VEICULO_DISPONIVEL`, `RESERVA_NAO_ENCONTRADA`.
