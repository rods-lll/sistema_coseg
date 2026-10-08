from django.db import models

from core.domain.entidades import CategoriaVeiculo

CATEGORIAS = [(c.value, c.name.title()) for c in CategoriaVeiculo]


class VeiculoModel(models.Model):
    codigo = models.CharField(max_length=10, unique=True)
    categoria = models.CharField(max_length=2, choices=CATEGORIAS)

    class Meta:
        ordering = ["codigo"]

    def __str__(self):
        return self.codigo


class ReservaModel(models.Model):
    solicitante = models.CharField(max_length=120)
    setor = models.CharField(max_length=80)
    atividade = models.CharField(max_length=120)
    origem = models.CharField(max_length=120)
    destino = models.CharField(max_length=120)
    data = models.DateField()
    saida = models.TimeField()
    retorno = models.TimeField()
    passageiros = models.PositiveSmallIntegerField()
    veiculo = models.ForeignKey(
        VeiculoModel, on_delete=models.PROTECT, related_name="reservas"
    )
    categoria_pretendida = models.CharField(
        max_length=2, choices=CATEGORIAS, blank=True
    )
    observacoes = models.TextField(blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["data", "saida"]
        indexes = [models.Index(fields=["veiculo", "data"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(retorno__gt=models.F("saida")),
                name="retorno_posterior_a_saida",
            )
        ]

    def __str__(self):
        return f"{self.veiculo} {self.data:%d/%m/%Y} {self.saida:%H:%M}-{self.retorno:%H:%M}"
