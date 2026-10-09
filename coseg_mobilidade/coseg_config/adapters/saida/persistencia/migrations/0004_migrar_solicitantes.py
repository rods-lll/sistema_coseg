"""Converte o solicitante e o setor gravados como texto em registros de
SetorModel e ColaboradorModel, ligando cada reserva ao seu colaborador."""

from django.db import migrations


def texto_para_tabelas(apps, schema_editor):
    Setor = apps.get_model("persistencia", "SetorModel")
    Colaborador = apps.get_model("persistencia", "ColaboradorModel")
    Reserva = apps.get_model("persistencia", "ReservaModel")

    for reserva in Reserva.objects.all():
        nome_setor = " ".join(reserva.setor.split()) or "Não informado"
        nome = " ".join(reserva.solicitante.split()) or "Não informado"
        setor = Setor.objects.filter(nome__iexact=nome_setor).first()
        if setor is None:
            setor = Setor.objects.create(nome=nome_setor)
        colaborador = Colaborador.objects.filter(nome__iexact=nome, setor=setor).first()
        if colaborador is None:
            colaborador = Colaborador.objects.create(nome=nome, setor=setor)
        reserva.colaborador = colaborador
        reserva.save(update_fields=["colaborador"])


def tabelas_para_texto(apps, schema_editor):
    Reserva = apps.get_model("persistencia", "ReservaModel")
    for reserva in Reserva.objects.select_related("colaborador__setor"):
        reserva.solicitante = reserva.colaborador.nome
        reserva.setor = reserva.colaborador.setor.nome
        reserva.save(update_fields=["solicitante", "setor"])


class Migration(migrations.Migration):

    dependencies = [
        ("persistencia", "0003_setor_colaborador_status"),
    ]

    operations = [
        migrations.RunPython(texto_para_tabelas, tabelas_para_texto),
    ]
