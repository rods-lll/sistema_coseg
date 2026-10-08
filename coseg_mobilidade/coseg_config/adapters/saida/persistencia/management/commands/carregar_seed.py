from datetime import date, time

from django.core.management.base import BaseCommand
from django.db import transaction

from adapters.saida.persistencia.models import ReservaModel, VeiculoModel

FROTA = [(f"VL-{n:02d}", "VL") for n in range(1, 9)] + [
    (f"VC-{n:02d}", "VC") for n in range(1, 3)
]

# (veículo, data, saída, retorno, atividade, passageiros)
RESERVAS_INICIAIS = [
    ("VL-01", date(2026, 8, 18), time(8), time(10), "Reunião administrativa", 3),
    ("VL-03", date(2026, 8, 18), time(13), time(15), "Inspeção técnica", 2),
    ("VC-01", date(2026, 8, 19), time(9), time(12), "Treinamento", 12),
    ("VL-05", date(2026, 8, 20), time(14), time(17), "Visita externa", 4),
]


class Command(BaseCommand):
    help = "Carrega a frota do COSEG e as reservas iniciais do enunciado do PBL 1."

    @transaction.atomic
    def handle(self, *args, **options):
        veiculos = {}
        for codigo, categoria in FROTA:
            veiculos[codigo], _ = VeiculoModel.objects.update_or_create(
                codigo=codigo, defaults={"categoria": categoria}
            )

        criadas = 0
        for codigo, data, saida, retorno, atividade, passageiros in RESERVAS_INICIAIS:
            # Grava pelo ORM, sem o ReservaService: as datas de agosto/2026
            # já passaram e seriam barradas pela regra data >= hoje.
            _, nova = ReservaModel.objects.get_or_create(
                veiculo=veiculos[codigo],
                data=data,
                saida=saida,
                retorno=retorno,
                defaults={
                    "solicitante": "Carga inicial COSEG",
                    "setor": "COSEG",
                    "atividade": atividade,
                    "origem": "Porto do Itaqui",
                    "destino": "A definir",
                    "passageiros": passageiros,
                },
            )
            criadas += nova

        if options["verbosity"] > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Frota: {len(FROTA)} veículos. Reservas novas: {criadas} "
                    f"de {len(RESERVAS_INICIAIS)}."
                )
            )
