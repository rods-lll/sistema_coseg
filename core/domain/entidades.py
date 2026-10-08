from dataclasses import dataclass
from datetime import date, time
from enum import Enum


class CategoriaVeiculo(Enum):
    LEVE = "VL"
    COLETIVO = "VC"

    @property
    def capacidade(self):
        return 4 if self is CategoriaVeiculo.LEVE else 18


@dataclass(frozen=True)
class Veiculo:
    codigo: str
    categoria: CategoriaVeiculo

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
    id: int | None = None

    def conflita_com(self, outra):
        if self.veiculo is None or outra.veiculo is None:
            return False
        # Intervalos semiabertos: retorno às 10h não colide com saída às 10h.
        return (
            self.veiculo.codigo == outra.veiculo.codigo
            and self.data == outra.data
            and self.saida < outra.retorno
            and outra.saida < self.retorno
        )
