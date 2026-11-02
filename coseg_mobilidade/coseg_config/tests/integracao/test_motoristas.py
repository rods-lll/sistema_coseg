import json
from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from adapters.saida.persistencia.models import MotoristaModel, ReservaModel
from adapters.saida.persistencia.repositorios import obter_ou_criar_colaborador
from adapters.entrada.web.composicao import montar_service
from core.domain.entidades import CategoriaVeiculo, Reserva
from core.domain.excecoes import (
    CnhVencida,
    ConflitoDeMotorista,
    MotoristaInativo,
    MotoristaNaoHabilitado,
    ReservaInvalida,
    SemMotoristaDisponivel,
)

AMANHA = timezone.localdate() + timedelta(days=1)


def pedido(saida=time(8), retorno=time(10), passageiros=3, **extra):
    dados = dict(
        solicitante="Maria Silva", setor="Operações", atividade="Reunião",
        origem="Porto do Itaqui", destino="Centro", data=AMANHA,
        saida=saida, retorno=retorno, passageiros=passageiros,
    )
    dados.update(extra)
    return Reserva(**dados)


class MotoristaServiceTest(TestCase):
    """Seed: MOT-001 Antônio (D), MOT-002 Beatriz (B), MOT-003 Carlos (E)..."""

    def setUp(self):
        call_command("carregar_seed", verbosity=0)
        self.service = montar_service()

    def test_seed_cria_motoristas_sem_duplicar(self):
        call_command("carregar_seed", verbosity=0)
        self.assertEqual(MotoristaModel.objects.count(), 5)

    def test_reserva_com_motorista_e_persistida(self):
        criada = self.service.criar(pedido(), "VL-02", "MOT-002")
        self.assertEqual(criada.motorista.nome, "Beatriz Lopes")
        self.assertEqual(ReservaModel.objects.get(pk=criada.id).motorista.matricula, "MOT-002")

    def test_motorista_inexistente(self):
        with self.assertRaises(ReservaInvalida) as ctx:
            self.service.criar(pedido(), "VL-02", "MOT-999")
        self.assertEqual(ctx.exception.campo, "motorista")

    def test_categoria_b_nao_dirige_coletivo(self):
        with self.assertRaises(MotoristaNaoHabilitado):
            self.service.criar(pedido(passageiros=10), "VC-01", "MOT-002")

    def test_alocacao_automatica_tambem_checa_habilitacao(self):
        with self.assertRaises(MotoristaNaoHabilitado):
            self.service.criar(
                pedido(passageiros=10, categoria=CategoriaVeiculo.COLETIVO),
                codigo_motorista="MOT-002",
            )

    def test_motorista_nao_pode_estar_em_dois_veiculos(self):
        self.service.criar(pedido(), "VL-02", "MOT-001")
        with self.assertRaises(ConflitoDeMotorista):
            self.service.criar(pedido(time(9), time(11)), "VL-03", "MOT-001")
        self.service.criar(pedido(time(10), time(11)), "VL-03", "MOT-001")

    def test_cnh_vencida(self):
        MotoristaModel.objects.filter(matricula="MOT-004").update(cnh_validade=AMANHA - timedelta(days=1))
        with self.assertRaises(CnhVencida):
            self.service.criar(pedido(), "VL-02", "MOT-004")

    def test_motorista_inativo(self):
        MotoristaModel.objects.filter(matricula="MOT-005").update(ativo=False)
        with self.assertRaises(MotoristaInativo):
            self.service.criar(pedido(), "VL-02", "MOT-005")

    def test_editar_mantem_o_motorista_se_ele_ainda_puder(self):
        criada = self.service.criar(pedido(), "VL-02", "MOT-001")
        editada = self.service.atualizar(criada.id, pedido(destino="Terminal"), "VL-02")
        self.assertEqual(editada.motorista.matricula, "MOT-001")

    def test_editar_para_coletivo_troca_motorista_sem_cnh_d(self):
        criada = self.service.criar(pedido(), "VL-02")  # escala Beatriz (CNH B)
        self.assertEqual(criada.motorista.matricula, "MOT-002")
        editada = self.service.atualizar(criada.id, pedido(passageiros=10), "VC-01")
        self.assertIn(editada.motorista.categoria_cnh.value, ("D", "E"))

    def test_cancelar_libera_o_motorista(self):
        criada = self.service.criar(pedido(), "VL-02", "MOT-001")
        self.service.cancelar(criada.id)
        self.service.criar(pedido(), "VL-03", "MOT-001")

    def test_banco_recusa_categoria_de_cnh_invalida(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            MotoristaModel.objects.create(
                matricula="X", nome="X", cnh_categoria="Z", cnh_validade=AMANHA
            )

    def test_motorista_com_reserva_nao_pode_ser_apagado(self):
        from django.db.models import ProtectedError

        self.service.criar(pedido(), "VL-02", "MOT-001")
        with self.assertRaises(ProtectedError):
            MotoristaModel.objects.get(matricula="MOT-001").delete()


class MotoristaApiTest(TestCase):
    def setUp(self):
        call_command("carregar_seed", verbosity=0)
        self.url = reverse("api-reservas")

    def enviar(self, metodo, url, corpo):
        return getattr(self.client, metodo)(url, data=json.dumps(corpo), content_type="application/json")

    def payload(self, **extra):
        dados = {
            "solicitante": "Maria Silva", "setor": "Operações", "atividade": "Reunião",
            "origem": "Porto do Itaqui", "destino": "Centro", "data": AMANHA.isoformat(),
            "saida": "08:00", "retorno": "10:00", "passageiros": 3, "veiculo": "VL-02",
        }
        dados.update(extra)
        return dados

    def test_lista_motoristas(self):
        corpo = self.client.get(reverse("api-motoristas")).json()
        self.assertEqual(corpo["total"], 5)
        antonio = next(m for m in corpo["motoristas"] if m["matricula"] == "MOT-001")
        self.assertEqual(antonio["dirige"], ["VL", "VC"])
        beatriz = next(m for m in corpo["motoristas"] if m["matricula"] == "MOT-002")
        self.assertEqual(beatriz["dirige"], ["VL"])

    def test_motorista_e_escalado_automaticamente(self):
        resposta = self.enviar("post", self.url, self.payload())
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.json()["reserva"]["motorista_nome"], "Beatriz Lopes")

    def test_sem_motorista_livre_retorna_409(self):
        MotoristaModel.objects.exclude(matricula="MOT-002").update(ativo=False)
        self.enviar("post", self.url, self.payload())
        resposta = self.enviar("post", self.url, self.payload(veiculo="VL-03"))
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(resposta.json()["codigo"], "SEM_MOTORISTA_DISPONIVEL")
        self.assertEqual(resposta.json()["campo"], "motorista")

    def test_reserva_com_motorista(self):
        resposta = self.enviar("post", self.url, self.payload(motorista="MOT-002"))
        reserva = resposta.json()["reserva"]
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual((reserva["motorista"], reserva["motorista_nome"]), ("MOT-002", "Beatriz Lopes"))

    def test_conflito_de_motorista_retorna_409(self):
        self.enviar("post", self.url, self.payload(motorista="MOT-001"))
        resposta = self.enviar("post", self.url, self.payload(veiculo="VL-03", motorista="MOT-001"))
        corpo = resposta.json()
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(corpo["codigo"], "CONFLITO_DE_MOTORISTA")
        self.assertEqual(corpo["campo"], "motorista")
        self.assertEqual(corpo["conflito"]["veiculo"], "VL-02")

    def test_habilitacao_retorna_400(self):
        resposta = self.enviar("post", self.url, self.payload(veiculo="VC-01", passageiros=10, motorista="MOT-002"))
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.json()["codigo"], "MOTORISTA_NAO_HABILITADO")


class MotoristaAdminTest(TestCase):
    def setUp(self):
        call_command("carregar_seed", verbosity=0)
        self.client.force_login(User.objects.create_superuser("admin", "a@a.com", "x"))

    def test_lista_de_motoristas_abre(self):
        resposta = self.client.get(reverse("admin:persistencia_motoristamodel_changelist"))
        self.assertContains(resposta, "Antônio Ferreira")

    def test_formulario_de_reserva_valida_o_motorista(self):
        maria = obter_ou_criar_colaborador("Maria Silva", "Operações")
        from adapters.saida.persistencia.models import VeiculoModel

        dados = {
            "colaborador": maria.pk, "atividade": "Treino", "origem": "Porto", "destino": "Centro",
            "data": AMANHA.isoformat(), "saida": "08:00", "retorno": "10:00", "passageiros": "10",
            "veiculo": VeiculoModel.objects.get(codigo="VC-01").pk,
            "motorista": MotoristaModel.objects.get(matricula="MOT-002").pk,
            "categoria_pretendida": "", "observacoes": "", "status": "CONFIRMADA",
        }
        resposta = self.client.post(reverse("admin:persistencia_reservamodel_add"), dados)
        erros = resposta.context["adminform"].form.errors
        self.assertIn("D ou E", erros["motorista"][0])


class EscalaAutomaticaTest(TestCase):
    """Seed: Antônio (D), Beatriz (B), Carlos (E), Daniela (B), Edson (D)."""

    def setUp(self):
        call_command("carregar_seed", verbosity=0)
        self.service = montar_service()

    def escala(self, *args, **extra):
        return self.service.criar(pedido(**extra), *args).motorista

    def test_veiculo_leve_prefere_cnh_b(self):
        # Poupa quem tem D/E para o coletivo.
        self.assertEqual(self.escala("VL-02").categoria_cnh.value, "B")

    def test_coletivo_so_escala_d_ou_e_e_prefere_d(self):
        motorista = self.escala("VC-01", passageiros=10)
        self.assertEqual(motorista.categoria_cnh.value, "D")

    def test_divide_o_trabalho_no_dia(self):
        primeira = self.escala("VL-02", saida=time(7), retorno=time(9))
        segunda = self.escala("VL-03", saida=time(14), retorno=time(16))
        self.assertNotEqual(primeira.matricula, segunda.matricula)
        self.assertEqual({primeira.nome, segunda.nome}, {"Beatriz Lopes", "Daniela Costa"})

    def test_quando_os_b_estao_ocupados_usa_um_d(self):
        self.escala("VL-02")
        self.escala("VL-03")
        terceira = self.escala("VL-04")
        self.assertEqual(terceira.categoria_cnh.value, "D")

    def test_pula_cnh_vencida_e_inativo(self):
        MotoristaModel.objects.filter(matricula="MOT-002").update(ativo=False)
        MotoristaModel.objects.filter(matricula="MOT-004").update(cnh_validade=AMANHA - timedelta(days=1))
        self.assertEqual(self.escala("VL-02").categoria_cnh.value, "D")

    def test_sem_ninguem_habilitado_e_livre(self):
        # Só o Antônio (D) fica disponível para o coletivo.
        MotoristaModel.objects.filter(matricula__in=["MOT-003", "MOT-005"]).update(ativo=False)
        self.assertEqual(self.escala("VC-01", passageiros=10).matricula, "MOT-001")
        # Mesmo horário, outro coletivo: os B não podem e o Antônio está ocupado.
        with self.assertRaises(SemMotoristaDisponivel):
            self.service.criar(pedido(passageiros=10), "VC-02")

    def test_cancelar_devolve_o_motorista_para_a_escala(self):
        criada = self.service.criar(pedido(), "VL-02")
        self.service.cancelar(criada.id)
        de_novo = self.escala("VL-03")
        self.assertEqual(de_novo.matricula, criada.motorista.matricula)

    def test_sem_motoristas_cadastrados_reserva_segue_sem_escala(self):
        MotoristaModel.objects.all().delete()
        self.assertIsNone(self.escala("VL-02"))

    def test_indicacao_manual_ainda_vale(self):
        self.assertEqual(self.escala("VL-02", "MOT-003").matricula, "MOT-003")
