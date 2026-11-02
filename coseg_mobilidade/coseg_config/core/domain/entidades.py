from dataclasses import dataclass
from datetime import date, time
from enum import Enum


class CategoriaVeiculo(Enum):
    LEVE = "VL"
    COLETIVO = "VC"

    @property
    def capacidade(self):
        return 4 if self is CategoriaVeiculo.LEVE else 18


class StatusReserva(Enum):
    CONFIRMADA = "CONFIRMADA"
    CANCELADA = "CANCELADA"
    CONCLUIDA = "CONCLUIDA"

    @property
    def rotulo(self):
        return {"CONFIRMADA": "confirmada", "CANCELADA": "cancelada", "CONCLUIDA": "concluída"}[
            self.value
        ]


class CategoriaCnh(Enum):
    B = "B"
    C = "C"
    D = "D"
    E = "E"

    def habilita(self, categoria_veiculo):
        """Leve (até 4 pessoas) pede B ou superior; coletivo (até 18) pede D ou E."""
        if categoria_veiculo is CategoriaVeiculo.COLETIVO:
            return self in (CategoriaCnh.D, CategoriaCnh.E)
        return True

    @property
    def nivel(self):
        """Ordem das categorias: B < C < D < E (usada para poupar quem dirige o coletivo)."""
        return "BCDE".index(self.value)

    @staticmethod
    def exigida(categoria_veiculo):
        return "D ou E" if categoria_veiculo is CategoriaVeiculo.COLETIVO else "B ou superior"


@dataclass(frozen=True)
class Motorista:
    matricula: str
    nome: str
    categoria_cnh: CategoriaCnh
    validade_cnh: date
    telefone: str = ""
    ativo: bool = True

    def pode_dirigir(self, categoria_veiculo):
        return self.categoria_cnh.habilita(categoria_veiculo)

    def cnh_valida_em(self, dia):
        return dia <= self.validade_cnh

    def pode_ser_escalado_para(self, categoria_veiculo, dia):
        return self.ativo and self.pode_dirigir(categoria_veiculo) and self.cnh_valida_em(dia)


@dataclass(frozen=True)
class Colaborador:
    nome: str
    setor: str
    email: str = ""
    telefone: str = ""


@dataclass(frozen=True)
class Veiculo:
    codigo: str
    categoria: CategoriaVeiculo
    placa: str | None = None
    modelo: str = ""
    ativo: bool = True

    @property
    def capacidade(self):
        return self.categoria.capacidade


@dataclass
class Reserva:
    solicitante: str
    setor: str
    atividade: str
    origem: str
    destino: str
    data: date
    saida: time
    retorno: time
    passageiros: int
    veiculo: Veiculo | None = None
    categoria: CategoriaVeiculo | None = None
    observacoes: str = ""
    status: StatusReserva = StatusReserva.CONFIRMADA
    motorista: Motorista | None = None
    id: int | None = None

    @property
    def duracao_minutos(self):
        return (self.retorno.hour * 60 + self.retorno.minute) - (
            self.saida.hour * 60 + self.saida.minute
        )

    def _sobrepoe(self, outra):
        # Reserva cancelada não ocupa mais ninguém.
        if StatusReserva.CANCELADA in (self.status, outra.status):
            return False
        # Intervalos semiabertos: retorno às 10h não colide com saída às 10h.
        return (
            self.data == outra.data
            and self.saida < outra.retorno
            and outra.saida < self.retorno
        )

    def conflita_com(self, outra):
        """Mesmo veículo em períodos que se sobrepõem."""
        if self.veiculo is None or outra.veiculo is None:
            return False
        return self.veiculo.codigo == outra.veiculo.codigo and self._sobrepoe(outra)

    def conflita_motorista_com(self, outra):
        """Mesmo motorista escalado em períodos que se sobrepõem."""
        if self.motorista is None or outra.motorista is None:
            return False
        return self.motorista.matricula == outra.motorista.matricula and self._sobrepoe(outra)
