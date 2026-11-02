"""A rota de disponibilidade usa as mesmas regras do ReservaService (sem gravar)."""
import json
from datetime import date, timedelta

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from adapters.saida.persistencia.models import ReservaModel

AMANHA = (timezone.localdate() + timedelta(days=1)).isoformat()


class DisponibilidadeTest(TestCase):
    def setUp(self):
        call_command("carregar_seed", verbosity=0)
        self.url = reverse("api-disponibilidade")

    def consultar(self, **params):
        base = {"data": AMANHA, "saida": "08:00", "retorno": "10:00", "passageiros": 2}
        base.update(params)
        return self.client.get(self.url, {k: v for k, v in base.items() if v is not None})

    def criar(self, **extra):
        dados = {
            "solicitante": "Maria", "setor": "Operações", "atividade": "Reunião",
            "origem": "Porto", "destino": "Centro", "data": AMANHA,
            "saida": "08:00", "retorno": "10:00", "passageiros": 2, "veiculo": "VL-01",
        }
        dados.update(extra)
        return self.client.post(reverse("api-reservas"), json.dumps(dados), content_type="application/json").json()

    def situacao(self, corpo, codigo):
        return next(v for v in corpo["veiculos"] if v["codigo"] == codigo)

    def test_nao_grava_nada(self):
        antes = ReservaModel.objects.count()
        self.consultar()
        self.assertEqual(ReservaModel.objects.count(), antes)

    def test_veiculo_ocupado_aparece_com_o_horario_do_conflito(self):
        criada = self.criar()
        corpo = self.consultar(saida="09:00", retorno="11:00").json()
        vl01 = self.situacao(corpo, "VL-01")
        self.assertFalse(vl01["livre"])
        self.assertEqual(vl01["motivo"], "Ocupado 08:00–10:00")
        self.assertEqual(vl01["conflito"]["reserva_id"], criada["reserva"]["id"])
        self.assertEqual(corpo["veiculo"], "VL-02")  # primeiro VL livre

    def test_retorno_igual_a_saida_de_outra_nao_conflita(self):
        self.criar()
        corpo = self.consultar(saida="10:00", retorno="11:00").json()
        self.assertTrue(self.situacao(corpo, "VL-01")["livre"])

    def test_capacidade_e_categoria_minima(self):
        corpo = self.consultar(passageiros=10).json()
        self.assertEqual(corpo["categoria_minima"], "VC")
        self.assertEqual(self.situacao(corpo, "VL-01")["motivo"], "Só 4 lugares")
        self.assertEqual(corpo["veiculo"], "VC-01")

    def test_categoria_leve_pedida_para_grupo_grande_vira_erro(self):
        corpo = self.consultar(passageiros=7, categoria="VL").json()
        self.assertIn("CAPACIDADE_EXCEDIDA", [e["codigo"] for e in corpo["erros"]])

    def test_mais_de_18(self):
        corpo = self.consultar(passageiros=19).json()
        self.assertIsNone(corpo["categoria_minima"])
        self.assertIn("CAPACIDADE_EXCEDIDA", [e["codigo"] for e in corpo["erros"]])

    def test_periodo_invalido(self):
        corpo = self.consultar(saida="10:00", retorno="09:00").json()
        self.assertEqual(corpo["erros"][0]["campo"], "retorno")
        self.assertIsNone(corpo["veiculo"])

    def test_data_passada(self):
        ontem = (timezone.localdate() - timedelta(days=1)).isoformat()
        corpo = self.consultar(data=ontem).json()
        self.assertIn("PERIODO_INVALIDO", [e["codigo"] for e in corpo["erros"]])

    def test_motorista_previsto_e_o_mesmo_que_o_servidor_escala(self):
        previsto = self.consultar(veiculo="VL-03").json()["motorista"]["matricula"]
        criada = self.criar(veiculo="VL-03")
        self.assertEqual(criada["reserva"]["motorista"], previsto)

    def test_coletivo_lista_quem_nao_dirige(self):
        corpo = self.consultar(passageiros=10).json()
        beatriz = next(m for m in corpo["motoristas"] if m["matricula"] == "MOT-002")
        self.assertEqual(beatriz["motivo"], "Não dirige VC")
        self.assertEqual(corpo["motorista"]["cnh_categoria"], "D")

    def test_edicao_ignora_a_propria_reserva_e_mantem_o_motorista(self):
        criada = self.criar()["reserva"]
        corpo = self.consultar(veiculo="VL-01", ignorar=criada["id"]).json()
        self.assertTrue(self.situacao(corpo, "VL-01")["livre"])
        self.assertEqual(corpo["motorista"]["matricula"], criada["motorista"])

    def test_parametros_obrigatorios_e_formatos(self):
        resposta = self.client.get(self.url, {"data": AMANHA})
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.json()["codigo"], "CAMPOS_OBRIGATORIOS")
        resposta = self.consultar(saida="8h")
        self.assertEqual(resposta.json()["campo"], "saida")
