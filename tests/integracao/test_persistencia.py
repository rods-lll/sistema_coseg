from datetime import date, time, timedelta

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from adapters.saida.persistencia.models import ReservaModel, VeiculoModel
from adapters.saida.persistencia.repositorios import (
    ReservaDjangoRepository,
    VeiculoDjangoRepository,
)
from core.domain.entidades import CategoriaVeiculo, Reserva
from core.domain.excecoes import (
    CamposObrigatorios,
    CapacidadeExcedida,
    ConflitoDeHorario,
    PeriodoInvalido,
    ReservaInvalida,
    ReservaNaoEncontrada,
    SemVeiculoDisponivel,
)
from core.services.reserva_service import ReservaService

AMANHA = date.today() + timedelta(days=1)


def novo_pedido(saida=time(8), retorno=time(10), passageiros=3, **extra):
    dados = dict(
        solicitante="Maria Silva",
        setor="Operações",
        atividade="Reunião externa",
        origem="Porto do Itaqui",
        destino="Centro",
        data=AMANHA,
        saida=saida,
        retorno=retorno,
        passageiros=passageiros,
    )
    dados.update(extra)
    return Reserva(**dados)


class BaseIntegracao(TestCase):
    def setUp(self):
        call_command("carregar_seed", verbosity=0)
        self.reservas = ReservaDjangoRepository()
        self.veiculos = VeiculoDjangoRepository()
        self.service = ReservaService(self.reservas, self.veiculos)


class SeedTest(BaseIntegracao):
    def test_frota_e_reservas_iniciais_do_enunciado(self):
        self.assertEqual(VeiculoModel.objects.filter(categoria="VL").count(), 8)
        self.assertEqual(VeiculoModel.objects.filter(categoria="VC").count(), 2)
        self.assertEqual(ReservaModel.objects.count(), 4)
        vl01 = ReservaModel.objects.get(veiculo__codigo="VL-01")
        self.assertEqual(
            (vl01.data, vl01.saida, vl01.retorno),
            (date(2026, 8, 18), time(8), time(10)),
        )

    def test_seed_e_idempotente(self):
        call_command("carregar_seed", verbosity=0)
        self.assertEqual(VeiculoModel.objects.count(), 10)
        self.assertEqual(ReservaModel.objects.count(), 4)

    def test_conflito_do_enunciado_contra_o_seed(self):
        agosto = ReservaService(
            self.reservas, self.veiculos, hoje=lambda: date(2026, 8, 1)
        )
        sobreposta = novo_pedido(time(9), time(11), data=date(2026, 8, 18))
        with self.assertRaises(ConflitoDeHorario):
            agosto.criar(sobreposta, codigo_veiculo="VL-01")
        livre = novo_pedido(time(10, 30), time(12), data=date(2026, 8, 18))
        self.assertIsNotNone(agosto.criar(livre, codigo_veiculo="VL-01").id)


class PersistenciaECrudTest(BaseIntegracao):
    def test_reserva_criada_e_lida_por_outra_instancia_do_repositorio(self):
        criada = self.service.criar(
            novo_pedido(observacoes="Levar crachá"), codigo_veiculo="VL-02"
        )
        lida = ReservaDjangoRepository().obter(criada.id)
        self.assertEqual(lida, criada)
        self.assertEqual(lida.veiculo.codigo, "VL-02")
        self.assertEqual(lida.observacoes, "Levar crachá")

    def test_listar_filtra_por_data(self):
        self.service.criar(novo_pedido(), codigo_veiculo="VL-02")
        self.assertEqual(len(self.service.listar(AMANHA)), 1)
        self.assertEqual(len(self.service.listar()), 5)

    def test_atualizar_altera_a_reserva_persistida(self):
        criada = self.service.criar(novo_pedido(), codigo_veiculo="VL-02")
        pedido = novo_pedido(time(9), time(12), destino="Distrito Industrial")
        self.service.atualizar(criada.id, pedido, codigo_veiculo="VL-02")
        lida = self.service.obter(criada.id)
        self.assertEqual((lida.saida, lida.retorno), (time(9), time(12)))
        self.assertEqual(lida.destino, "Distrito Industrial")

    def test_atualizar_para_horario_ocupado_e_rejeitado_e_nao_altera(self):
        self.service.criar(novo_pedido(time(8), time(10)), codigo_veiculo="VL-02")
        segunda = self.service.criar(
            novo_pedido(time(11), time(12)), codigo_veiculo="VL-02"
        )
        with self.assertRaises(ConflitoDeHorario):
            self.service.atualizar(
                segunda.id, novo_pedido(time(9), time(12)), codigo_veiculo="VL-02"
            )
        self.assertEqual(self.service.obter(segunda.id).saida, time(11))

    def test_excluir_remove_e_libera_o_horario(self):
        criada = self.service.criar(novo_pedido(), codigo_veiculo="VL-02")
        self.service.excluir(criada.id)
        with self.assertRaises(ReservaNaoEncontrada):
            self.service.obter(criada.id)
        self.service.criar(novo_pedido(), codigo_veiculo="VL-02")

    def test_excluir_inexistente(self):
        with self.assertRaises(ReservaNaoEncontrada):
            self.service.excluir(9999)

    def test_veiculo_fora_da_frota(self):
        with self.assertRaises(ReservaInvalida) as ctx:
            self.service.criar(novo_pedido(), codigo_veiculo="VL-99")
        self.assertEqual(ctx.exception.campo, "veiculo")

    def test_banco_recusa_retorno_anterior_a_saida(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReservaModel.objects.create(
                solicitante="x",
                setor="x",
                atividade="x",
                origem="x",
                destino="x",
                data=AMANHA,
                saida=time(10),
                retorno=time(9),
                passageiros=1,
                veiculo=VeiculoModel.objects.get(codigo="VL-01"),
            )


class RegrasNoServidorTest(BaseIntegracao):
    def assertNadaPersistido(self):
        self.assertEqual(ReservaModel.objects.count(), 4)

    def test_leve_rejeita_cinco_passageiros(self):
        with self.assertRaises(CapacidadeExcedida):
            self.service.criar(novo_pedido(passageiros=5), codigo_veiculo="VL-02")
        self.assertNadaPersistido()

    def test_coletivo_aceita_dezoito_e_rejeita_dezenove(self):
        self.service.criar(novo_pedido(passageiros=18), codigo_veiculo="VC-02")
        with self.assertRaises(CapacidadeExcedida):
            self.service.criar(
                novo_pedido(time(14), time(16), passageiros=19),
                codigo_veiculo="VC-02",
            )

    def test_data_passada_e_rejeitada(self):
        ontem = date.today() - timedelta(days=1)
        with self.assertRaises(PeriodoInvalido):
            self.service.criar(novo_pedido(data=ontem), codigo_veiculo="VL-02")
        self.assertNadaPersistido()

    def test_retorno_nao_posterior_a_saida(self):
        with self.assertRaises(PeriodoInvalido):
            self.service.criar(
                novo_pedido(time(10), time(10)), codigo_veiculo="VL-02"
            )

    def test_campos_obrigatorios(self):
        with self.assertRaises(CamposObrigatorios) as ctx:
            self.service.criar(novo_pedido(setor="", destino=""), codigo_veiculo="VL-02")
        self.assertEqual(ctx.exception.campos, ["setor", "destino"])

    def test_conflito_por_sobreposicao_e_sem_conflito_apos_o_retorno(self):
        self.service.criar(novo_pedido(time(8), time(10)), codigo_veiculo="VL-02")
        with self.assertRaises(ConflitoDeHorario):
            self.service.criar(novo_pedido(time(9), time(11)), codigo_veiculo="VL-02")
        self.service.criar(novo_pedido(time(10, 30), time(12)), codigo_veiculo="VL-02")

    def test_atraso_no_retorno_e_considerado_no_intervalo_todo(self):
        self.service.criar(novo_pedido(time(12), time(14)), codigo_veiculo="VL-02")
        with self.assertRaises(ConflitoDeHorario):
            self.service.criar(novo_pedido(time(13), time(15)), codigo_veiculo="VL-02")

    def test_mesmo_horario_em_veiculos_diferentes(self):
        self.service.criar(novo_pedido(), codigo_veiculo="VL-02")
        self.service.criar(novo_pedido(), codigo_veiculo="VL-04")


class AlocacaoPorCategoriaTest(BaseIntegracao):
    def test_categoria_recebe_o_primeiro_veiculo_livre(self):
        self.service.criar(novo_pedido(), codigo_veiculo="VL-01")
        pedido = novo_pedido(categoria=CategoriaVeiculo.LEVE)
        criada = self.service.criar(pedido)
        self.assertEqual(criada.veiculo.codigo, "VL-02")
        self.assertIs(criada.categoria, CategoriaVeiculo.LEVE)

    def test_sem_veiculo_livre_na_categoria(self):
        for n in range(1, 9):
            self.service.criar(novo_pedido(), codigo_veiculo=f"VL-{n:02d}")
        with self.assertRaises(SemVeiculoDisponivel):
            self.service.criar(novo_pedido(categoria=CategoriaVeiculo.LEVE))

    def test_grupo_maior_que_a_categoria_pretendida(self):
        pedido = novo_pedido(passageiros=7, categoria=CategoriaVeiculo.LEVE)
        with self.assertRaises(CapacidadeExcedida):
            self.service.criar(pedido)
