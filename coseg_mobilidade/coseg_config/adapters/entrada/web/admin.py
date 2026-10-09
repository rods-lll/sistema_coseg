from django import forms
from django.contrib import admin, messages
from django.db.models import Count
from django.utils import timezone

from adapters.saida.persistencia.models import (
    ColaboradorModel,
    ReservaModel,
    SetorModel,
    VeiculoModel,
)
from core.domain.entidades import CategoriaVeiculo, Reserva, StatusReserva
from core.domain.excecoes import CamposObrigatorios, ReservaInvalida

from .composicao import montar_service

# Nome usado nas exceções do domínio -> nome do campo no formulário do Admin.
CAMPO_NO_FORM = {
    "categoria": "categoria_pretendida",
    "veiculo ou categoria": "veiculo",
    "solicitante": "colaborador",
    "setor": "colaborador",
}


@admin.register(SetorModel)
class SetorAdmin(admin.ModelAdmin):
    list_display = ("nome", "total_colaboradores")
    search_fields = ("nome",)

    def get_queryset(self, request):
        return (
            super().get_queryset(request).annotate(total=Count("colaboradores")).order_by("nome")
        )

    @admin.display(description="Colaboradores", ordering="total")
    def total_colaboradores(self, obj):
        return obj.total


@admin.register(ColaboradorModel)
class ColaboradorAdmin(admin.ModelAdmin):
    list_display = ("nome", "setor", "email", "telefone", "total_reservas")
    list_filter = ("setor",)
    search_fields = ("nome", "email", "setor__nome")
    list_select_related = ("setor",)

    def get_queryset(self, request):
        return (
            super().get_queryset(request).annotate(total=Count("reservas")).order_by("nome")
        )

    @admin.display(description="Reservas", ordering="total")
    def total_reservas(self, obj):
        return obj.total


class VeiculoAdminForm(forms.ModelForm):
    class Meta:
        model = VeiculoModel
        fields = ("codigo", "categoria", "placa", "modelo", "ativo")
        labels = {"codigo": "Código"}

    def clean_placa(self):
        placa = self.cleaned_data.get("placa")
        return placa.strip().upper() if placa else None


@admin.register(VeiculoModel)
class VeiculoAdmin(admin.ModelAdmin):
    form = VeiculoAdminForm
    list_display = ("codigo", "categoria", "capacidade", "placa", "modelo", "ativo")
    list_editable = ("ativo",)
    list_filter = ("categoria", "ativo")
    search_fields = ("codigo", "placa", "modelo")

    @admin.display(description="Capacidade")
    def capacidade(self, obj):
        return f"{CategoriaVeiculo(obj.categoria).capacidade} passageiros"


class ReservaAdminForm(forms.ModelForm):
    """Formulário do Admin que passa pelas mesmas regras da API (ReservaService)."""

    class Meta:
        model = ReservaModel
        fields = (
            "colaborador",
            "atividade",
            "origem",
            "destino",
            "data",
            "saida",
            "retorno",
            "passageiros",
            "veiculo",
            "categoria_pretendida",
            "observacoes",
            "status",
        )
        labels = {
            "colaborador": "Solicitante",
            "saida": "Saída",
            "veiculo": "Veículo",
            "categoria_pretendida": "Categoria pretendida",
            "observacoes": "Observações",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["veiculo"].required = False
        self.fields["veiculo"].help_text = (
            "Deixe vazio e escolha a categoria para o sistema alocar "
            "o primeiro veículo livre."
        )

    def clean(self):
        dados = super().clean()
        if self.errors:
            # Algum campo já veio com formato inválido; o Django mostra o erro.
            return dados
        if dados.get("status") != StatusReserva.CONFIRMADA.value:
            # Cancelar ou concluir só muda o status; não revalida a agenda.
            if dados.get("veiculo") is None:
                self.add_error("veiculo", "Informe o veículo.")
            return dados

        veiculo = dados.get("veiculo")
        colaborador = dados["colaborador"]
        pretendida = dados.get("categoria_pretendida")
        reserva = Reserva(
            id=self.instance.pk,
            solicitante=colaborador.nome,
            setor=colaborador.setor.nome,
            atividade=dados.get("atividade"),
            origem=dados.get("origem"),
            destino=dados.get("destino"),
            data=dados.get("data"),
            saida=dados.get("saida"),
            retorno=dados.get("retorno"),
            passageiros=dados.get("passageiros"),
            categoria=CategoriaVeiculo(pretendida) if pretendida else None,
            observacoes=dados.get("observacoes") or "",
        )

        try:
            montar_service().validar(reserva, veiculo.codigo if veiculo else None)
        except CamposObrigatorios as exc:
            for campo in exc.campos:
                self.add_error(CAMPO_NO_FORM.get(campo, campo), "Campo obrigatório.")
        except ReservaInvalida as exc:
            campo = CAMPO_NO_FORM.get(exc.campo, exc.campo)
            self.add_error(campo if campo in self.fields else None, exc.mensagem)
        else:
            if veiculo is None:
                # Pedido só por categoria: grava o veículo que o service alocou.
                dados["veiculo"] = VeiculoModel.objects.get(codigo=reserva.veiculo.codigo)
        return dados


@admin.register(ReservaModel)
class ReservaAdmin(admin.ModelAdmin):
    form = ReservaAdminForm
    list_display = (
        "data",
        "saida",
        "retorno",
        "veiculo",
        "atividade",
        "colaborador",
        "setor",
        "passageiros",
        "status",
    )
    list_filter = ("status", "data", "veiculo__categoria", "veiculo", "colaborador__setor")
    search_fields = (
        "colaborador__nome",
        "colaborador__setor__nome",
        "atividade",
        "origem",
        "destino",
    )
    date_hierarchy = "data"
    list_select_related = ("veiculo", "colaborador__setor")
    autocomplete_fields = ("colaborador",)
    readonly_fields = ("cancelada_em", "criada_em", "atualizada_em")
    actions = ("cancelar_reservas", "concluir_reservas")

    @admin.display(description="Setor", ordering="colaborador__setor__nome")
    def setor(self, obj):
        return obj.colaborador.setor

    def has_delete_permission(self, request, obj=None):
        # Reserva não é apagada: é cancelada e fica no histórico.
        return False

    def save_model(self, request, obj, form, change):
        if obj.status == StatusReserva.CANCELADA.value:
            obj.cancelada_em = obj.cancelada_em or timezone.now()
        else:
            obj.cancelada_em = None
        super().save_model(request, obj, form, change)

    def _aplicar(self, request, queryset, acao, verbo):
        service = montar_service()
        feitas = 0
        for reserva in queryset:
            try:
                getattr(service, acao)(reserva.pk)
                feitas += 1
            except ReservaInvalida as exc:
                self.message_user(request, exc.mensagem, messages.WARNING)
        if feitas:
            self.message_user(request, f"{feitas} reserva(s) {verbo}.", messages.SUCCESS)

    @admin.action(description="Cancelar reservas selecionadas")
    def cancelar_reservas(self, request, queryset):
        self._aplicar(request, queryset, "cancelar", "cancelada(s)")

    @admin.action(description="Marcar como concluídas")
    def concluir_reservas(self, request, queryset):
        self._aplicar(request, queryset, "concluir", "concluída(s)")
