from dataclasses import replace
from datetime import date

from core.domain.excecoes import (
    ReservaInvalida,
    ReservaNaoEncontrada,
    SemVeiculoDisponivel,
)
from core.domain.validadores import (
    ValidadorCampos,
    ValidadorCapacidade,
    ValidadorConflito,
    ValidadorPeriodo,
)


class ReservaService:
    def __init__(self, reservas, veiculos, hoje=date.today):
        self._reservas = reservas
        self._veiculos = veiculos
        self._campos = ValidadorCampos()
        self._capacidade = ValidadorCapacidade()
        self._periodo = ValidadorPeriodo(hoje)
        self._conflito = ValidadorConflito()

    def frota(self):
        return self._veiculos.listar()

    def listar(self, data=None):
        return self._reservas.listar(data)

    def obter(self, reserva_id):
        reserva = self._reservas.obter(reserva_id)
        if reserva is None:
            raise ReservaNaoEncontrada(reserva_id)
        return reserva

    def criar(self, reserva, codigo_veiculo=None):
        self._preparar(reserva, codigo_veiculo)
        return self._reservas.salvar(reserva)

    def atualizar(self, reserva_id, reserva, codigo_veiculo=None):
        self.obter(reserva_id)
        reserva.id = reserva_id
        self._preparar(reserva, codigo_veiculo)
        return self._reservas.salvar(reserva)

    def excluir(self, reserva_id):
        if not self._reservas.excluir(reserva_id):
            raise ReservaNaoEncontrada(reserva_id)

    def _preparar(self, reserva, codigo_veiculo):
        if codigo_veiculo:
            reserva.veiculo = self._buscar_veiculo(codigo_veiculo)
        self._campos.validar(reserva)
        self._capacidade.validar(reserva)
        self._periodo.validar(reserva)
        if reserva.veiculo is None:
            reserva.veiculo = self._alocar(reserva)
            return
        existentes = self._reservas.listar_do_veiculo_na_data(
            reserva.veiculo.codigo, reserva.data
        )
        self._conflito.validar(reserva, existentes)

    def _buscar_veiculo(self, codigo):
        veiculo = self._veiculos.obter(codigo)
        if veiculo is None:
            raise ReservaInvalida(
                f"O veículo {codigo} não está cadastrado na frota.", campo="veiculo"
            )
        return veiculo

    def _alocar(self, reserva):
        for candidato in self._veiculos.listar_por_categoria(reserva.categoria):
            existentes = self._reservas.listar_do_veiculo_na_data(
                candidato.codigo, reserva.data
            )
            tentativa = replace(reserva, veiculo=candidato)
            if self._conflito.localizar(tentativa, existentes) is None:
                return candidato
        raise SemVeiculoDisponivel(
            reserva.categoria, reserva.data, reserva.saida, reserva.retorno
        )
