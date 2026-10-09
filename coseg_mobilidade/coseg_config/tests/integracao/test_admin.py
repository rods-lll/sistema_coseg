from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from adapters.saida.persistencia.models import ReservaModel, VeiculoModel
from adapters.saida.persistencia.repositorios import obter_ou_criar_colaborador

AMANHA = date.today() + timedelta(days=1)


class AdminTest(TestCase):
    def setUp(self):
        call_command("carregar_seed", verbosity=0)
        admin = User.objects.create_superuser("admin", "admin@coseg.local", "senha")
        self.client.force_login(admin)
        self.url_nova = reverse("admin:persistencia_reservamodel_add")
        self.maria = obter_ou_criar_colaborador("Maria Silva", "Operações")

    def formulario(self, **extra):
        dados = {
            "colaborador": str(self.maria.pk),
            "atividade": "Reunião externa",
            "origem": "Porto do Itaqui",
            "destino": "Centro",
            "data": AMANHA.isoformat(),
            "saida": "08:00",
            "retorno": "10:00",
            "passageiros": "3",
            "veiculo": str(VeiculoModel.objects.get(codigo="VL-02").pk),
            "categoria_pretendida": "",
            "observacoes": "",
            "status": "CONFIRMADA",
        }
        dados.update(extra)
        return dados

    def test_listas_do_admin_abrem(self):
        for nome in (
            "persistencia_reservamodel",
            "persistencia_veiculomodel",
            "persistencia_setormodel",
            "persistencia_colaboradormodel",
        ):
            with self.subTest(nome=nome):
                resposta = self.client.get(reverse(f"admin:{nome}_changelist"))
                self.assertEqual(resposta.status_code, 200)

    def test_cria_reserva_valida(self):
        resposta = self.client.post(self.url_nova, self.formulario())
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(ReservaModel.objects.count(), 5)

    def test_conflito_aparece_no_campo_veiculo(self):
        self.client.post(self.url_nova, self.formulario())
        resposta = self.client.post(
            self.url_nova, self.formulario(saida="09:00", retorno="11:00")
        )
        self.assertEqual(resposta.status_code, 200)
        erros = resposta.context["adminform"].form.errors
        self.assertIn("já está reservado", erros["veiculo"][0])
        self.assertEqual(ReservaModel.objects.count(), 5)

    def test_capacidade_aparece_no_campo_passageiros(self):
        resposta = self.client.post(self.url_nova, self.formulario(passageiros="5"))
        erros = resposta.context["adminform"].form.errors
        self.assertIn("Utilize a categoria VC", erros["passageiros"][0])

    def test_so_categoria_aloca_veiculo_livre(self):
        resposta = self.client.post(
            self.url_nova, self.formulario(veiculo="", categoria_pretendida="VL")
        )
        self.assertEqual(resposta.status_code, 302)
        nova = ReservaModel.objects.latest("id")
        self.assertEqual(nova.veiculo.codigo, "VL-01")

    def test_sem_veiculo_e_sem_categoria(self):
        resposta = self.client.post(self.url_nova, self.formulario(veiculo=""))
        erros = resposta.context["adminform"].form.errors
        self.assertIn("veiculo", erros)

    def test_editar_mantendo_o_horario_nao_conflita_consigo(self):
        self.client.post(self.url_nova, self.formulario())
        reserva = ReservaModel.objects.latest("id")
        url = reverse("admin:persistencia_reservamodel_change", args=[reserva.pk])
        resposta = self.client.post(url, self.formulario(destino="Terminal"))
        self.assertEqual(resposta.status_code, 302)
        reserva.refresh_from_db()
        self.assertEqual(reserva.destino, "Terminal")

    def test_acao_cancelar_mantem_a_reserva(self):
        self.client.post(self.url_nova, self.formulario())
        reserva = ReservaModel.objects.latest("id")
        self.client.post(
            reverse("admin:persistencia_reservamodel_changelist"),
            {"action": "cancelar_reservas", "_selected_action": [reserva.pk]},
        )
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, "CANCELADA")
        self.assertIsNotNone(reserva.cancelada_em)

    def test_cancelar_pelo_formulario_nao_revalida_a_agenda(self):
        antiga = ReservaModel.objects.get(veiculo__codigo="VL-01")  # agosto, já passou
        url = reverse("admin:persistencia_reservamodel_change", args=[antiga.pk])
        dados = self.formulario(
            colaborador=str(antiga.colaborador.pk),
            data=antiga.data.isoformat(),
            veiculo=str(antiga.veiculo.pk),
            status="CANCELADA",
        )
        self.assertEqual(self.client.post(url, dados).status_code, 302)
        antiga.refresh_from_db()
        self.assertEqual(antiga.status, "CANCELADA")

    def test_reserva_nao_pode_ser_apagada(self):
        self.client.post(self.url_nova, self.formulario())
        reserva = ReservaModel.objects.latest("id")
        url = reverse("admin:persistencia_reservamodel_delete", args=[reserva.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
