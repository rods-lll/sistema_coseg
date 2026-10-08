from datetime import date, time

from core.domain.entidades import CategoriaVeiculo, Reserva
from core.domain.excecoes import ReservaInvalida


def veiculo_para_dict(veiculo):
    return {
        "codigo": veiculo.codigo,
        "categoria": veiculo.categoria.value,
        "capacidade": veiculo.capacidade,
    }


def reserva_para_dict(reserva):
    return {
        "id": reserva.id,
        "solicitante": reserva.solicitante,
        "setor": reserva.setor,
        "atividade": reserva.atividade,
        "origem": reserva.origem,
        "destino": reserva.destino,
        "data": reserva.data.isoformat(),
        "saida": reserva.saida.strftime("%H:%M"),
        "retorno": reserva.retorno.strftime("%H:%M"),
        "passageiros": reserva.passageiros,
        "veiculo": reserva.veiculo.codigo if reserva.veiculo else None,
        "categoria": reserva.categoria.value if reserva.categoria else None,
        "observacoes": reserva.observacoes,
    }


def _inteiro(valor):
    if isinstance(valor, bool) or (isinstance(valor, float) and not valor.is_integer()):
        raise ValueError(valor)
    return int(valor)


def _converter(valor, campo, conversor, formato):
    if valor is None or valor == "":
        return None
    try:
        return conversor(valor)
    except (ValueError, TypeError):
        raise ReservaInvalida(
            f"Valor inválido para '{campo}': use {formato}.", campo=campo
        ) from None


def ler_data(valor, campo="data"):
    return _converter(valor, campo, date.fromisoformat, "AAAA-MM-DD")


def _texto(valor):
    return None if valor is None else str(valor)


def reserva_do_payload(payload):
    if not isinstance(payload, dict):
        raise ReservaInvalida("O corpo da requisição deve ser um objeto JSON.")
    reserva = Reserva(
        solicitante=_texto(payload.get("solicitante")),
        setor=_texto(payload.get("setor")),
        atividade=_texto(payload.get("atividade")),
        origem=_texto(payload.get("origem")),
        destino=_texto(payload.get("destino")),
        data=ler_data(payload.get("data")),
        saida=_converter(payload.get("saida"), "saida", time.fromisoformat, "HH:MM"),
        retorno=_converter(
            payload.get("retorno"), "retorno", time.fromisoformat, "HH:MM"
        ),
        passageiros=_converter(
            payload.get("passageiros"), "passageiros", _inteiro, "um número inteiro"
        ),
        categoria=_converter(
            payload.get("categoria"),
            "categoria",
            lambda v: CategoriaVeiculo(str(v).upper()),
            "VL ou VC",
        ),
        observacoes=_texto(payload.get("observacoes")) or "",
    )
    return reserva, _texto(payload.get("veiculo")) or None
