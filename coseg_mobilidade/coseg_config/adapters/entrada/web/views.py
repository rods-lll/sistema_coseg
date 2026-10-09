import json
from functools import wraps

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods

from core.domain.excecoes import (
    CamposObrigatorios,
    CapacidadeExcedida,
    ConflitoDeHorario,
    PeriodoInvalido,
    ReservaInvalida,
    ReservaNaoEditavel,
    ReservaNaoEncontrada,
    SemVeiculoDisponivel,
    VeiculoInativo,
)

from .composicao import montar_service
from .serializacao import (
    ler_data,
    reserva_do_payload,
    reserva_para_dict,
    veiculo_para_dict,
)

# Subclasses antes da base: a primeira correspondência vence.
ERROS_DE_DOMINIO = [
    (ConflitoDeHorario, 409, "CONFLITO_DE_HORARIO"),
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
    if isinstance(exc, ConflitoDeHorario):
        existente = exc.reserva_existente
        return {
            "conflito": {
                "reserva_id": existente.id,
                "veiculo": existente.veiculo.codigo,
                "data": existente.data.isoformat(),
                "saida": existente.saida.strftime("%H:%M"),
                "retorno": existente.retorno.strftime("%H:%M"),
            }
        }
    return {}


def api(view):
    @wraps(view)
    def envolvida(request, *args, **kwargs):
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

    return envolvida


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

    reserva, codigo_veiculo = reserva_do_payload(_corpo_json(request))
    with transaction.atomic():
        criada = service.criar(reserva, codigo_veiculo)
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

    reserva, codigo_veiculo = reserva_do_payload(_corpo_json(request))
    with transaction.atomic():
        atualizada = service.atualizar(reserva_id, reserva, codigo_veiculo)
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
