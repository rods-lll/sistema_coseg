from django.db import models

from core.domain.entidades import CategoriaVeiculo, StatusReserva

CATEGORIAS = [(c.value, c.name.title()) for c in CategoriaVeiculo]
STATUS = [(s.value, s.rotulo.capitalize()) for s in StatusReserva]


class SetorModel(models.Model):
    nome = models.CharField(max_length=80, unique=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "setor"
        verbose_name_plural = "setores"

    def __str__(self):
        return self.nome


class ColaboradorModel(models.Model):
    nome = models.CharField(max_length=120)
    setor = models.ForeignKey(
        SetorModel, on_delete=models.PROTECT, related_name="colaboradores"
    )
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "colaborador"
        verbose_name_plural = "colaboradores"
        constraints = [
            models.UniqueConstraint(
                fields=["nome", "setor"], name="colaborador_unico_no_setor"
            )
        ]

    def __str__(self):
        return f"{self.nome} ({self.setor})"


class VeiculoModel(models.Model):
    codigo = models.CharField(max_length=10, unique=True)
    categoria = models.CharField(max_length=2, choices=CATEGORIAS)
    placa = models.CharField(max_length=8, unique=True, null=True, blank=True)
    modelo = models.CharField(max_length=60, blank=True)
    ativo = models.BooleanField(
        default=True, help_text="Desmarque quando o veículo estiver fora de operação."
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "veículo"
        verbose_name_plural = "veículos"

    def __str__(self):
        return self.codigo


class ReservaModel(models.Model):
    colaborador = models.ForeignKey(
        ColaboradorModel, on_delete=models.PROTECT, related_name="reservas"
    )
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
    status = models.CharField(
        max_length=10, choices=STATUS, default=StatusReserva.CONFIRMADA.value
    )
    cancelada_em = models.DateTimeField(null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["data", "saida"]
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        indexes = [models.Index(fields=["veiculo", "data"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(retorno__gt=models.F("saida")),
                name="retorno_posterior_a_saida",
            ),
            models.CheckConstraint(
                condition=models.Q(passageiros__gte=1),
                name="ao_menos_um_passageiro",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=[s.value for s in StatusReserva]),
                name="status_valido",
            ),
        ]

    def __str__(self):
        return f"{self.veiculo} {self.data:%d/%m/%Y} {self.saida:%H:%M}-{self.retorno:%H:%M}"
