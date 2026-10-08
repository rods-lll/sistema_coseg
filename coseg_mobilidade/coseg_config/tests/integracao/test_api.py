import json
from datetime import date, timedelta

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from adapters.saida.persistencia.models import ReservaModel

AMANHA = date.today() + timedelta(days=1)


def payload(**extra):
    dados = {
        "solicitante": "Maria Silva",
        "setor": "Operações",
        "atividade": "Reunião externa",
        "origem": "Porto do Itaqui",
        "destino": "Centro",
        "data": AMANHA.isoformat(),
        "saida": "08:00",
        "retorno": "10:00",
        "passageiros": 3,
        "veiculo": "VL-02",
        "observacoes": "",
    }
    dados.update(extra)
    return {k: v for k, v in dados.items() if v is not None}


class ApiTest(TestCase):
    def setUp(self):
        call_command("carregar_seed", verbosity=0)
        self.url = reverse("api-reservas")

    def enviar(self, metodo, url, corpo=None):
        dados = corpo if isinstance(corpo, str) else json.dumps(corpo)
        return getattr(self.client, metodo)(
            url, data=dados, content_type="application/json"
        )

    def criar(self, **extra):
        return self.enviar("post", self.url, payload(**extra))


class VeiculosEListagemTest(ApiTest):
    def test_lista_a_frota_completa(self):
        resposta = self.client.get(reverse("api-veiculos"))
        corpo = resposta.json()
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(corpo["total"], 10)
        vc = [v for v in corpo["veiculos"] if v["categoria"] == "VC"]
        self.assertEqual([v["capacidade"] for v in vc], [18, 18])

    def test_lista_reservas_e_filtra_por_data(self):
        self.assertEqual(self.client.get(self.url).json()["total"], 4)
        filtradas = self.client.get(self.url, {"data": "2026-08-18"}).json()
        self.assertEqual(filtradas["total"], 2)

    def test_filtro_de_data_invalido(self):
        resposta = self.client.get(self.url, {"data": "18/08/2026"})
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.json()["campo"], "data")


class CriacaoTest(ApiTest):
    def test_criacao_com_sucesso(self):
        resposta = self.criar()
        corpo = resposta.json()
        self.assertEqual(resposta.status_code, 201)
        self.assertTrue(corpo["sucesso"])
        self.assertEqual(corpo["reserva"]["veiculo"], "VL-02")
        self.assertTrue(ReservaModel.objects.filter(pk=corpo["reserva"]["id"]).exists())

    def test_conflito_retorna_409_com_detalhes(self):
        self.criar()
        resposta = self.criar(saida="09:00", retorno="11:00")
        corpo = resposta.json()
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(corpo["codigo"], "CONFLITO_DE_HORARIO")
        self.assertEqual(corpo["conflito"]["veiculo"], "VL-02")
        self.assertEqual(corpo["conflito"]["saida"], "08:00")
        self.assertEqual(ReservaModel.objects.count(), 5)

    def test_horario_logo_apos_o_retorno_e_aceito(self):
        self.criar()
        self.assertEqual(self.criar(saida="10:30", retorno="12:00").status_code, 201)

    def test_capacidade_excedida_retorna_400(self):
        resposta = self.criar(passageiros=5)
        corpo = resposta.json()
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(corpo["codigo"], "CAPACIDADE_EXCEDIDA")
        self.assertIn("VC", corpo["erro"])

    def test_mais_de_dezoito_passageiros(self):
        resposta = self.criar(veiculo="VC-01", passageiros=19)
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.json()["codigo"], "CAPACIDADE_EXCEDIDA")

    def test_data_passada(self):
        ontem = (date.today() - timedelta(days=1)).isoformat()
        resposta = self.criar(data=ontem)
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.json()["codigo"], "PERIODO_INVALIDO")

    def test_retorno_nao_posterior_a_saida(self):
        resposta = self.criar(saida="10:00", retorno="09:00")
        self.assertEqual(resposta.json()["campo"], "retorno")

    def test_campos_obrigatorios_listados(self):
        resposta = self.criar(setor="", destino=None)
        corpo = resposta.json()
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(corpo["codigo"], "CAMPOS_OBRIGATORIOS")
        self.assertEqual(corpo["campos"], ["setor", "destino"])

    def test_categoria_sem_veiculo_aloca_automaticamente(self):
        resposta = self.criar(veiculo=None, categoria="vl")
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.json()["reserva"]["veiculo"], "VL-01")

    def test_formatos_invalidos(self):
        for campo, valor in [("data", "amanhã"), ("saida", "8h"), ("passageiros", "tres")]:
            with self.subTest(campo=campo):
                resposta = self.criar(**{campo: valor})
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.json()["campo"], campo)

    def test_json_invalido_e_corpo_que_nao_e_objeto(self):
        self.assertEqual(self.enviar("post", self.url, "{quebrado").status_code, 400)
        self.assertEqual(self.enviar("post", self.url, [1, 2]).status_code, 400)

    def test_veiculo_inexistente(self):
        resposta = self.criar(veiculo="VL-99")
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.json()["campo"], "veiculo")

    def test_metodo_nao_permitido(self):
        self.assertEqual(self.client.delete(self.url).status_code, 405)


class DetalheTest(ApiTest):
    def setUp(self):
        super().setUp()
        self.id = self.criar().json()["reserva"]["id"]
        self.url_detalhe = reverse("api-reserva", args=[self.id])

    def test_consulta(self):
        corpo = self.client.get(self.url_detalhe).json()
        self.assertEqual(corpo["reserva"]["atividade"], "Reunião externa")

    def test_alteracao(self):
        resposta = self.enviar("put", self.url_detalhe, payload(destino="Terminal"))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["reserva"]["destino"], "Terminal")

    def test_alteracao_mantendo_o_proprio_horario_nao_conflita(self):
        resposta = self.enviar("put", self.url_detalhe, payload(retorno="11:00"))
        self.assertEqual(resposta.status_code, 200)

    def test_alteracao_para_horario_ocupado(self):
        outra = self.criar(saida="12:00", retorno="14:00").json()["reserva"]["id"]
        resposta = self.enviar(
            "put",
            reverse("api-reserva", args=[outra]),
            payload(saida="09:00", retorno="13:00"),
        )
        self.assertEqual(resposta.status_code, 409)

    def test_cancelamento_libera_o_horario(self):
        resposta = self.client.delete(self.url_detalhe)
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("cancelada", resposta.json()["mensagem"])
        self.assertEqual(self.client.get(self.url_detalhe).status_code, 404)
        self.assertEqual(self.criar().status_code, 201)

    def test_reserva_inexistente_retorna_404(self):
        url = reverse("api-reserva", args=[99999])
        for metodo in ("get", "delete"):
            with self.subTest(metodo=metodo):
                resposta = getattr(self.client, metodo)(url)
                self.assertEqual(resposta.status_code, 404)
                self.assertEqual(resposta.json()["codigo"], "RESERVA_NAO_ENCONTRADA")
        self.assertEqual(self.enviar("put", url, payload()).status_code, 404)


class PainelTest(ApiTest):
    def test_painel_mostra_frota_e_reservas_do_seed(self):
        resposta = self.client.get(reverse("painel"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "VC-02")
        self.assertContains(resposta, "Reunião administrativa")
        self.assertContains(resposta, "18/08/2026")

    def test_painel_filtra_por_data(self):
        resposta = self.client.get(reverse("painel"), {"data": "2026-08-19"})
        self.assertContains(resposta, "Treinamento")
        self.assertNotContains(resposta, "Inspeção técnica")

    def test_painel_avisa_data_invalida_sem_quebrar(self):
        resposta = self.client.get(reverse("painel"), {"data": "xx"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "AAAA-MM-DD")

    def test_raiz_redireciona_para_o_painel(self):
        self.assertRedirects(self.client.get("/"), reverse("painel"))
