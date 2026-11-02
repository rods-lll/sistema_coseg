from datetime import date, time

from django.core.management.base import BaseCommand
from django.db import transaction

from adapters.saida.persistencia.models import MotoristaModel, ReservaModel, VeiculoModel
from adapters.saida.persistencia.repositorios import obter_ou_criar_colaborador

FROTA = [(f"VL-{n:02d}", "VL") for n in range(1, 9)] + [
    (f"VC-{n:02d}", "VC") for n in range(1, 3)
]

# Motoristas FICTÍCIOS, só para demonstração (o enunciado não traz motoristas).
# (matrícula, nome, categoria da CNH, validade da CNH, telefone)
MOTORISTAS = [
    ("MOT-001", "Antônio Ferreira", "D", date(2028, 5, 10), "(98) 90000-0001"),
    ("MOT-002", "Beatriz Lopes", "B", date(2027, 11, 30), "(98) 90000-0002"),
    ("MOT-003", "Carlos Nunes", "E", date(2029, 2, 14), "(98) 90000-0003"),
    ("MOT-004", "Daniela Costa", "B", date(2026, 12, 20), "(98) 90000-0004"),
    ("MOT-005", "Edson Ribeiro", "D", date(2027, 8, 1), "(98) 90000-0005"),
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

        for matricula, nome, categoria, validade, telefone in MOTORISTAS:
            MotoristaModel.objects.get_or_create(
                matricula=matricula,
                defaults={
                    "nome": nome,
                    "cnh_categoria": categoria,
                    "cnh_validade": validade,
                    "telefone": telefone,
                },
            )

        coseg = obter_ou_criar_colaborador("Carga inicial COSEG", "COSEG")
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
                    "colaborador": coseg,
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
                    f"Frota: {len(FROTA)} veículos. Motoristas: {len(MOTORISTAS)}. "
                    f"Reservas novas: {criadas} "
                    f"de {len(RESERVAS_INICIAIS)}."
                )
            )
