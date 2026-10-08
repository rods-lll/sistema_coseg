from datetime import date

from core.domain.entidades import CategoriaVeiculo
from core.domain.excecoes import (
    CamposObrigatorios,
    CapacidadeExcedida,
    ConflitoDeHorario,
    PeriodoInvalido,
    ReservaInvalida,
)

CAMPOS_TEXTO = ("solicitante", "setor", "atividade", "origem", "destino")
CAMPOS_PERIODO = ("data", "saida", "retorno")


def limite_da_frota():
    return max(categoria.capacidade for categoria in CategoriaVeiculo)


def categoria_minima(passageiros):
    for categoria in sorted(CategoriaVeiculo, key=lambda c: c.capacidade):
        if passageiros <= categoria.capacidade:
            return categoria
    raise CapacidadeExcedida(
        f"Solicitações acima de {limite_da_frota()} passageiros não podem "
        "ser atendidas pela frota.",
        campo="passageiros",
    )


class ValidadorCampos:
    def validar(self, reserva):
        ausentes = [
            campo
            for campo in CAMPOS_TEXTO
            if not (getattr(reserva, campo) or "").strip()
        ]
        ausentes += [c for c in CAMPOS_PERIODO if getattr(reserva, c) is None]
        if reserva.passageiros is None:
            ausentes.append("passageiros")
        if reserva.veiculo is None and reserva.categoria is None:
            ausentes.append("veiculo ou categoria")
        if ausentes:
            raise CamposObrigatorios(ausentes)
        if reserva.passageiros < 1:
            raise ReservaInvalida(
                "Informe ao menos 1 passageiro.", campo="passageiros"
            )


class ValidadorCapacidade:
    def validar(self, reserva):
        categoria_minima(reserva.passageiros)
        categoria = reserva.veiculo.categoria if reserva.veiculo else reserva.categoria
        if reserva.passageiros > categoria.capacidade:
            alvo = reserva.veiculo.codigo if reserva.veiculo else categoria.value
            sugerida = categoria_minima(reserva.passageiros).value
            raise CapacidadeExcedida(
                f"{alvo} comporta até {categoria.capacidade} passageiros e "
                f"foram informados {reserva.passageiros}. "
                f"Utilize a categoria {sugerida}.",
                campo="passageiros",
            )


class ValidadorPeriodo:
    def __init__(self, hoje=date.today):
        self._hoje = hoje

    def validar(self, reserva):
        if reserva.data < self._hoje():
            raise PeriodoInvalido(
                "A data da reserva não pode estar no passado.", campo="data"
            )
        if reserva.retorno <= reserva.saida:
            raise PeriodoInvalido(
                "O horário de retorno deve ser posterior ao de saída.",
                campo="retorno",
            )


class ValidadorConflito:
    def localizar(self, reserva, existentes):
        for outra in existentes:
            if reserva.id is not None and outra.id == reserva.id:
                continue
            if reserva.conflita_com(outra):
                return outra
        return None

    def validar(self, reserva, existentes):
        conflito = self.localizar(reserva, existentes)
        if conflito is not None:
            raise ConflitoDeHorario(conflito)
