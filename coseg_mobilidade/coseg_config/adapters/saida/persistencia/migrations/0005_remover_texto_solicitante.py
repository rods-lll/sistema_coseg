import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("persistencia", "0004_migrar_solicitantes"),
    ]

    operations = [
        # Default vazio só para a migração poder ser desfeita (recria as colunas).
        migrations.AlterField(
            model_name="reservamodel",
            name="solicitante",
            field=models.CharField(default="", max_length=120),
        ),
        migrations.AlterField(
            model_name="reservamodel",
            name="setor",
            field=models.CharField(default="", max_length=80),
        ),
        migrations.RemoveField(
            model_name="reservamodel",
            name="solicitante",
        ),
        migrations.RemoveField(
            model_name="reservamodel",
            name="setor",
        ),
        migrations.AlterField(
            model_name="reservamodel",
            name="colaborador",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reservas",
                to="persistencia.colaboradormodel",
            ),
        ),
    ]
