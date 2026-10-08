from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="painel")),
    path("painel/", views.painel, name="painel"),
    path("api/veiculos/", views.veiculos, name="api-veiculos"),
    path("api/reservas/", views.reservas, name="api-reservas"),
    path("api/reservas/<int:reserva_id>/", views.reserva_detalhe, name="api-reserva"),
]
