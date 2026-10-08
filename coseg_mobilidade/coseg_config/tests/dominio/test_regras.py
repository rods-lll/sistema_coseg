import unittest
from datetime import date, time, timedelta

from core.domain.entidades import CategoriaVeiculo, Reserva, Veiculo
from core.domain.excecoes import (
    CamposObrigatorios,
    CapacidadeExcedida,
    ConflitoDeHorario,
    PeriodoInvalido,
)
from core.domain.validadores import (
    ValidadorCampos,
    ValidadorCapacidade,
    ValidadorConflito,
    ValidadorPeriodo,
    categoria_minima,
)

VL01 = Veiculo("VL-01", CategoriaVeiculo.LEVE)
VL02 = Veiculo("VL-02", CategoriaVeiculo.LEVE)
VC01 = Veiculo("VC-01", CategoriaVeiculo.COLETIVO)
AMANHA = date.today() + timedelta(days=1)


def reserva(saida=time(8), retorno=time(10), veiculo=VL01, passageiros=3, **extra):
    dados = dict(
        solicitante="Maria",
        setor="Operações",
        atividade="Reunião",
        origem="Itaqui",
        destino="Centro",
        data=AMANHA,
        saida=saida,
        retorno=retorno,
        passageiros=passageiros,
        veiculo=veiculo,
    )
    dados.update(extra)
    return Reserva(**dados)


class ConflitoTest(unittest.TestCase):
    def setUp(self):
        self.existente = reserva(time(8), time(10), id=1)
        self.validador = ValidadorConflito()

    def test_sobreposicao_parcial_conflita(self):
        with self.assertRaises(ConflitoDeHorario):
            self.validador.validar(reserva(time(9), time(11)), [self.existente])

    def test_periodo_posterior_nao_conflita(self):
        self.validador.validar(reserva(time(10, 30), time(12)), [self.existente])

    def test_retorno_igual_a_saida_nao_conflita(self):
        self.validador.validar(reserva(time(10), time(12)), [self.existente])

    def test_periodo_contido_conflita(self):
        with self.assertRaises(ConflitoDeHorario):
            self.validador.validar(reserva(time(8, 30), time(9)), [self.existente])

    def test_outro_veiculo_nao_conflita(self):
        self.validador.validar(reserva(veiculo=VL02), [self.existente])

    def test_outra_data_nao_conflita(self):
        outra = reserva(data=AMANHA + timedelta(days=1))
        self.validador.validar(outra, [self.existente])

    def test_edicao_ignora_a_propria_reserva(self):
        editada = reserva(time(8), time(11), id=1)
        self.validador.validar(editada, [self.existente])

    def test_mensagem_identifica_o_veiculo_e_o_periodo(self):
        with self.assertRaises(ConflitoDeHorario) as ctx:
            self.validador.validar(reserva(), [self.existente])
        self.assertIn("VL-01", ctx.exception.mensagem)
        self.assertIn("08:00", ctx.exception.mensagem)


class CapacidadeTest(unittest.TestCase):
    def setUp(self):
        self.validador = ValidadorCapacidade()

    def test_leve_aceita_ate_quatro(self):
        self.validador.validar(reserva(passageiros=4))

    def test_leve_rejeita_cinco(self):
        with self.assertRaises(CapacidadeExcedida) as ctx:
            self.validador.validar(reserva(passageiros=5))
        self.assertIn("VC", ctx.exception.mensagem)

    def test_coletivo_aceita_dezoito(self):
        self.validador.validar(reserva(veiculo=VC01, passageiros=18))

    def test_acima_de_dezoito_e_rejeitado_mesmo_no_coletivo(self):
        with self.assertRaises(CapacidadeExcedida):
            self.validador.validar(reserva(veiculo=VC01, passageiros=19))

    def test_categoria_sem_veiculo_tambem_e_validada(self):
        pedido = reserva(veiculo=None, categoria=CategoriaVeiculo.LEVE, passageiros=7)
        with self.assertRaises(CapacidadeExcedida):
            self.validador.validar(pedido)

    def test_categoria_minima(self):
        self.assertIs(categoria_minima(4), CategoriaVeiculo.LEVE)
        self.assertIs(categoria_minima(5), CategoriaVeiculo.COLETIVO)
        with self.assertRaises(CapacidadeExcedida):
            categoria_minima(19)


class PeriodoTest(unittest.TestCase):
    def setUp(self):
        self.validador = ValidadorPeriodo()

    def test_data_passada_e_rejeitada(self):
        ontem = date.today() - timedelta(days=1)
        with self.assertRaises(PeriodoInvalido):
            self.validador.validar(reserva(data=ontem))

    def test_hoje_e_aceito(self):
        self.validador.validar(reserva(data=date.today()))

    def test_retorno_igual_a_saida_e_rejeitado(self):
        with self.assertRaises(PeriodoInvalido):
            self.validador.validar(reserva(time(9), time(9)))

    def test_retorno_antes_da_saida_e_rejeitado(self):
        with self.assertRaises(PeriodoInvalido):
            self.validador.validar(reserva(time(10), time(8)))

    def test_relogio_injetavel(self):
        validador = ValidadorPeriodo(hoje=lambda: date(2026, 8, 19))
        with self.assertRaises(PeriodoInvalido):
            validador.validar(reserva(data=date(2026, 8, 18)))


class CamposTest(unittest.TestCase):
    def setUp(self):
        self.validador = ValidadorCampos()

    def test_reserva_completa_passa(self):
        self.validador.validar(reserva())

    def test_lista_todos_os_campos_ausentes(self):
        with self.assertRaises(CamposObrigatorios) as ctx:
            self.validador.validar(
                reserva(setor="  ", destino="", data=None, veiculo=None)
            )
        self.assertEqual(
            ctx.exception.campos,
            ["setor", "destino", "data", "veiculo ou categoria"],
        )

    def test_categoria_basta_sem_veiculo(self):
        pedido = reserva(veiculo=None, categoria=CategoriaVeiculo.LEVE)
        self.validador.validar(pedido)

    def test_zero_passageiros_e_rejeitado(self):
        with self.assertRaises(Exception) as ctx:
            self.validador.validar(reserva(passageiros=0))
        self.assertEqual(ctx.exception.campo, "passageiros")


if __name__ == "__main__":
    unittest.main()
