from django.urls import path

from . import views

urlpatterns = [
    path("", views.app, name="app"),
    path("painel/", views.painel, name="painel"),
    path("api/veiculos/", views.veiculos, name="api-veiculos"),
    path("api/motoristas/", views.motoristas, name="api-motoristas"),
    path("api/disponibilidade/", views.disponibilidade, name="api-disponibilidade"),
    path("api/colaboradores/", views.colaboradores, name="api-colaboradores"),
    path("api/reservas/", views.reservas, name="api-reservas"),
    path("api/reservas/<int:reserva_id>/", views.reserva_detalhe, name="api-reserva"),
]
