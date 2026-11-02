from adapters.saida.persistencia.repositorios import (
    ColaboradorDjangoRepository,
    MotoristaDjangoRepository,
    ReservaDjangoRepository,
    VeiculoDjangoRepository,
)
from django.utils import timezone

from core.services.cadastro_service import CadastroService
from core.services.reserva_service import ReservaService


def montar_service():
    return ReservaService(
        ReservaDjangoRepository(),
        VeiculoDjangoRepository(),
        motoristas=MotoristaDjangoRepository(),
        # Hora de São Paulo (TIME_ZONE), não a do servidor: na Vercel o relógio é UTC.
        agora=lambda: timezone.localtime().replace(tzinfo=None),
    )


def montar_cadastro():
    return CadastroService(ColaboradorDjangoRepository())
