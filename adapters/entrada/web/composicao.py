from adapters.saida.persistencia.repositorios import (
    ReservaDjangoRepository,
    VeiculoDjangoRepository,
)
from core.services.reserva_service import ReservaService


def montar_service():
    return ReservaService(ReservaDjangoRepository(), VeiculoDjangoRepository())
