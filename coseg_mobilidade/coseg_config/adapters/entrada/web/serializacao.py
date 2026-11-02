from datetime import date, time

from django.utils import timezone

from core.domain.entidades import CategoriaVeiculo, Reserva
from core.domain.excecoes import ReservaInvalida


def veiculo_para_dict(veiculo):
    return {
        "codigo": veiculo.codigo,
        "categoria": veiculo.categoria.value,
        "capacidade": veiculo.capacidade,
        "placa": veiculo.placa,
        "modelo": veiculo.modelo,
        "ativo": veiculo.ativo,
    }


def motorista_para_dict(motorista, hoje=None):
    return {
        "matricula": motorista.matricula,
        "nome": motorista.nome,
        "telefone": motorista.telefone,
        "cnh_categoria": motorista.categoria_cnh.value,
        "cnh_validade": motorista.validade_cnh.isoformat(),
        "cnh_valida": motorista.cnh_valida_em(hoje or timezone.localdate()),
        "dirige": [c.value for c in CategoriaVeiculo if motorista.pode_dirigir(c)],
        "ativo": motorista.ativo,
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
        "status": reserva.status.value,
        "motorista": reserva.motorista.matricula if reserva.motorista else None,
        "motorista_nome": reserva.motorista.nome if reserva.motorista else None,
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


def ler_hora(valor, campo):
    return _converter(valor, campo, time.fromisoformat, "HH:MM")


def ler_inteiro(valor, campo):
    return _converter(valor, campo, _inteiro, "um número inteiro")


def ler_categoria(valor):
    return _converter(valor, "categoria", lambda v: CategoriaVeiculo(str(v).upper()), "VL ou VC")


def situacao_para_dict(situacao, chave, extra=None):
    corpo = {
        chave: getattr(situacao.item, "codigo", None) or situacao.item.matricula,
        "livre": situacao.livre,
        "motivo": situacao.motivo,
        "conflito": (
            {"reserva_id": situacao.conflito.id,
             "saida": situacao.conflito.saida.strftime("%H:%M"),
             "retorno": situacao.conflito.retorno.strftime("%H:%M")}
            if situacao.conflito else None
        ),
    }
    corpo.update(extra or {})
    return corpo


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
    return (
        reserva,
        _texto(payload.get("veiculo")) or None,
        _texto(payload.get("motorista")) or None,
    )
