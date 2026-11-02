import json
from functools import wraps

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods

from core.domain.excecoes import (
    CamposObrigatorios,
    CapacidadeExcedida,
    CnhVencida,
    SemMotoristaDisponivel,
    ConflitoDeHorario,
    ConflitoDeMotorista,
    MotoristaInativo,
    MotoristaNaoHabilitado,
    PeriodoInvalido,
    ReservaInvalida,
    ReservaNaoEditavel,
    ReservaNaoEncontrada,
    SemVeiculoDisponivel,
    VeiculoInativo,
)

from .composicao import montar_cadastro, montar_service
from .serializacao import (
    ler_categoria,
    ler_data,
    ler_hora,
    ler_inteiro,
    motorista_para_dict,
    situacao_para_dict,
    reserva_do_payload,
    reserva_para_dict,
    veiculo_para_dict,
)

# Subclasses antes da base: a primeira correspondência vence.
ERROS_DE_DOMINIO = [
    (ConflitoDeHorario, 409, "CONFLITO_DE_HORARIO"),
    (ConflitoDeMotorista, 409, "CONFLITO_DE_MOTORISTA"),
    (SemMotoristaDisponivel, 409, "SEM_MOTORISTA_DISPONIVEL"),
    (MotoristaNaoHabilitado, 400, "MOTORISTA_NAO_HABILITADO"),
    (CnhVencida, 400, "CNH_VENCIDA"),
    (MotoristaInativo, 400, "MOTORISTA_INATIVO"),
    (SemVeiculoDisponivel, 409, "SEM_VEICULO_DISPONIVEL"),
    (ReservaNaoEditavel, 409, "RESERVA_NAO_EDITAVEL"),
    (VeiculoInativo, 400, "VEICULO_INATIVO"),
    (CamposObrigatorios, 400, "CAMPOS_OBRIGATORIOS"),
    (CapacidadeExcedida, 400, "CAPACIDADE_EXCEDIDA"),
    (PeriodoInvalido, 400, "PERIODO_INVALIDO"),
    (ReservaInvalida, 400, "RESERVA_INVALIDA"),
]


def _erro(status, codigo, mensagem, **extra):
    corpo = {"sucesso": False, "codigo": codigo, "erro": mensagem, **extra}
    return JsonResponse(corpo, status=status)


def _detalhes(exc):
    if isinstance(exc, CamposObrigatorios):
        return {"campos": exc.campos}
    if isinstance(exc, (ConflitoDeHorario, ConflitoDeMotorista)):
        existente = exc.reserva_existente
        return {
            "conflito": {
                "reserva_id": existente.id,
                "veiculo": existente.veiculo.codigo,
                "data": existente.data.isoformat(),
                "saida": existente.saida.strftime("%H:%M"),
                "retorno": existente.retorno.strftime("%H:%M"),
                "motorista": existente.motorista.matricula if existente.motorista else None,
            }
        }
    return {}


def api(view):
    @wraps(view)
    def envolvida(request, *args, **kwargs):
        resposta = _executar(view, request, *args, **kwargs)
        # Dados de reserva mudam a todo momento: nenhum navegador ou CDN guarda cópia.
        resposta["Cache-Control"] = "no-store"
        return resposta

    return envolvida


def _executar(view, request, *args, **kwargs):
    try:
        return view(request, *args, **kwargs)
    except ReservaNaoEncontrada as exc:
        return _erro(404, "RESERVA_NAO_ENCONTRADA", str(exc))
    except ReservaInvalida as exc:
        for tipo, status, codigo in ERROS_DE_DOMINIO:
            if isinstance(exc, tipo):
                return _erro(
                    status, codigo, exc.mensagem, campo=exc.campo, **_detalhes(exc)
                )
        raise


def _corpo_json(request):
    try:
        return json.loads(request.body)
    except ValueError:
        raise ReservaInvalida("O corpo da requisição não é um JSON válido.") from None


def _sucesso(mensagem, reserva, status=200):
    corpo = {
        "sucesso": True,
        "mensagem": mensagem,
        "reserva": reserva_para_dict(reserva),
    }
    return JsonResponse(corpo, status=status)


@api
@require_GET
def veiculos(request):
    frota = [veiculo_para_dict(v) for v in montar_service().frota()]
    return JsonResponse({"sucesso": True, "total": len(frota), "veiculos": frota})


def _codigo_do_erro(exc):
    for tipo, status, codigo in ERROS_DE_DOMINIO:
        if isinstance(exc, tipo):
            return status, codigo
    return 400, "RESERVA_INVALIDA"


@api
@require_GET
def disponibilidade(request):
    """Simula o pedido sem gravar: o formulário mostra a resposta do servidor em vez
    de repetir as regras de conflito, capacidade e escala no JavaScript."""
    q = request.GET
    obrigatorios = [c for c in ("data", "saida", "retorno") if not q.get(c)]
    if obrigatorios:
        raise CamposObrigatorios(obrigatorios)
    resultado = montar_service().simular(
        data=ler_data(q.get("data")),
        saida=ler_hora(q.get("saida"), "saida"),
        retorno=ler_hora(q.get("retorno"), "retorno"),
        passageiros=max(1, ler_inteiro(q.get("passageiros") or 1, "passageiros")),
        codigo_veiculo=q.get("veiculo") or None,
        categoria=ler_categoria(q.get("categoria")),
        ignorar_id=ler_inteiro(q.get("ignorar"), "ignorar"),
    )
    erros = []
    for exc in resultado.erros:
        status, codigo = _codigo_do_erro(exc)
        erros.append({"codigo": codigo, "status": status, "campo": exc.campo, "erro": exc.mensagem})
    escalado = resultado.motorista
    return JsonResponse({
        "sucesso": True,
        "categoria_minima": resultado.categoria_minima.value if resultado.categoria_minima else None,
        "erros": erros,
        "veiculos": [
            situacao_para_dict(s, "codigo", {"categoria": s.item.categoria.value, "capacidade": s.item.capacidade})
            for s in resultado.veiculos
        ],
        "veiculo": resultado.veiculo.codigo if resultado.veiculo else None,
        "motoristas_cadastrados": resultado.motoristas_cadastrados,
        "motoristas": [
            situacao_para_dict(s, "matricula", {
                "nome": s.item.nome,
                "cnh_categoria": s.item.categoria_cnh.value,
                "escalado": bool(escalado and escalado.matricula == s.item.matricula),
            })
            for s in resultado.motoristas
        ],
        "motorista": (
            {"matricula": escalado.matricula, "nome": escalado.nome,
             "cnh_categoria": escalado.categoria_cnh.value}
            if escalado else None
        ),
    })


@api
@require_GET
def motoristas(request):
    lista = [motorista_para_dict(m) for m in montar_service().motoristas()]
    return JsonResponse({"sucesso": True, "total": len(lista), "motoristas": lista})


@api
@require_GET
def colaboradores(request):
    cadastro = montar_cadastro()
    lista = [
        {"nome": c.nome, "setor": c.setor, "email": c.email, "telefone": c.telefone}
        for c in cadastro.colaboradores(request.GET.get("setor"))
    ]
    return JsonResponse(
        {
            "sucesso": True,
            "total": len(lista),
            "colaboradores": lista,
            "setores": cadastro.setores(),
        }
    )


@require_GET
def app(request):
    """Interface web do PBL 2 (HTML + CSS + JavaScript puro, consumindo a API)."""
    return render(request, "web/app.html")


@api
@require_http_methods(["GET", "POST"])
def reservas(request):
    service = montar_service()
    if request.method == "GET":
        lista = service.listar(ler_data(request.GET.get("data")))
        return JsonResponse(
            {
                "sucesso": True,
                "total": len(lista),
                "reservas": [reserva_para_dict(r) for r in lista],
            }
        )

    reserva, codigo_veiculo, codigo_motorista = reserva_do_payload(_corpo_json(request))
    with transaction.atomic():
        criada = service.criar(reserva, codigo_veiculo, codigo_motorista)
    return _sucesso("Reserva registrada com sucesso.", criada, status=201)


@api
@require_http_methods(["GET", "PUT", "DELETE"])
def reserva_detalhe(request, reserva_id):
    service = montar_service()
    if request.method == "GET":
        return JsonResponse(
            {"sucesso": True, "reserva": reserva_para_dict(service.obter(reserva_id))}
        )

    if request.method == "DELETE":
        with transaction.atomic():
            service.cancelar(reserva_id)
        return JsonResponse(
            {"sucesso": True, "mensagem": f"Reserva {reserva_id} cancelada com sucesso."}
        )

    reserva, codigo_veiculo, codigo_motorista = reserva_do_payload(_corpo_json(request))
    with transaction.atomic():
        atualizada = service.atualizar(reserva_id, reserva, codigo_veiculo, codigo_motorista)
    return _sucesso("Reserva atualizada com sucesso.", atualizada)


@require_GET
def painel(request):
    service = montar_service()
    filtro, aviso = None, None
    try:
        filtro = ler_data(request.GET.get("data"))
    except ReservaInvalida as exc:
        aviso = exc.mensagem
    contexto = {
        "frota": service.frota(),
        "reservas": service.listar(filtro),
        "filtro": filtro,
        "aviso": aviso,
    }
    return render(request, "web/painel.html", contexto)
