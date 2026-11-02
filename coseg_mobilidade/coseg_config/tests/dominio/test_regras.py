import unittest
from datetime import date, datetime, time, timedelta

from core.domain.entidades import (
    CategoriaCnh,
    CategoriaVeiculo,
    Motorista,
    Reserva,
    StatusReserva,
    Veiculo,
)
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
    ValidadorMotorista,
    ValidadorPeriodo,
    categoria_minima,
)
from core.domain.excecoes import (
    CnhVencida,
    ConflitoDeMotorista,
    MotoristaInativo,
    MotoristaNaoHabilitado,
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

    def test_reserva_cancelada_nao_ocupa_o_veiculo(self):
        cancelada = reserva(time(8), time(10), id=1, status=StatusReserva.CANCELADA)
        self.validador.validar(reserva(time(9), time(11)), [cancelada])

    def test_reserva_concluida_continua_ocupando(self):
        concluida = reserva(time(8), time(10), id=1, status=StatusReserva.CONCLUIDA)
        with self.assertRaises(ConflitoDeHorario):
            self.validador.validar(reserva(time(9), time(11)), [concluida])

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


class HorarioQueJaPassouTest(unittest.TestCase):
    """Com relógio (agora = 27/10/2026 12:22), a saída de hoje não pode ter passado."""

    HOJE = date(2026, 10, 27)

    def setUp(self):
        self.validador = ValidadorPeriodo(agora=lambda: datetime(2026, 10, 27, 12, 22, 40))

    def test_saida_hoje_antes_de_agora_e_rejeitada_no_campo_saida(self):
        with self.assertRaises(PeriodoInvalido) as ctx:
            self.validador.validar(reserva(time(11), time(12), data=self.HOJE))
        self.assertEqual(ctx.exception.campo, "saida")
        self.assertIn("12:22", ctx.exception.mensagem)

    def test_saida_no_minuto_atual_ou_depois_e_aceita(self):
        self.validador.validar(reserva(time(12, 22), time(13), data=self.HOJE))
        self.validador.validar(reserva(time(15), time(16), data=self.HOJE))

    def test_amanha_cedo_e_aceito(self):
        self.validador.validar(reserva(time(6), time(7), data=self.HOJE + timedelta(days=1)))

    def test_data_de_hoje_vem_do_relogio(self):
        with self.assertRaises(PeriodoInvalido) as ctx:
            self.validador.validar(reserva(data=self.HOJE - timedelta(days=1)))
        self.assertEqual(ctx.exception.campo, "data")

    def test_editar_reserva_que_ja_saiu_sem_mudar_a_saida_e_aceito(self):
        original = reserva(time(11), time(12), data=self.HOJE)
        self.validador.validar(reserva(time(11), time(14), data=self.HOJE), original)

    def test_mudar_a_saida_para_outro_horario_passado_e_rejeitado(self):
        original = reserva(time(11), time(12), data=self.HOJE)
        with self.assertRaises(PeriodoInvalido):
            self.validador.validar(reserva(time(11, 30), time(12), data=self.HOJE), original)


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



ANA_B = Motorista("MOT-1", "Ana", CategoriaCnh.B, AMANHA + timedelta(days=365))
JOAO_D = Motorista("MOT-2", "João", CategoriaCnh.D, AMANHA + timedelta(days=365))


class MotoristaTest(unittest.TestCase):
    def setUp(self):
        self.validador = ValidadorMotorista()

    def test_sem_motorista_nao_valida_nada(self):
        self.validador.validar(reserva(), [])

    def test_categoria_b_dirige_leve(self):
        self.validador.validar(reserva(motorista=ANA_B), [])

    def test_categoria_b_nao_dirige_coletivo(self):
        with self.assertRaises(MotoristaNaoHabilitado) as ctx:
            self.validador.validar(reserva(veiculo=VC01, motorista=ANA_B), [])
        self.assertIn("D ou E", ctx.exception.mensagem)

    def test_categorias_d_e_e_dirigem_coletivo(self):
        self.validador.validar(reserva(veiculo=VC01, motorista=JOAO_D), [])
        carlos = Motorista("MOT-3", "Carlos", CategoriaCnh.E, AMANHA)
        self.validador.validar(reserva(veiculo=VC01, motorista=carlos), [])

    def test_cnh_vencida_na_data_da_reserva(self):
        vencida = Motorista("MOT-4", "Bia", CategoriaCnh.B, AMANHA - timedelta(days=1))
        with self.assertRaises(CnhVencida):
            self.validador.validar(reserva(motorista=vencida), [])

    def test_cnh_vence_no_proprio_dia_ainda_vale(self):
        no_limite = Motorista("MOT-5", "Edu", CategoriaCnh.B, AMANHA)
        self.validador.validar(reserva(motorista=no_limite), [])

    def test_motorista_inativo(self):
        inativo = Motorista("MOT-6", "Gil", CategoriaCnh.D, AMANHA, ativo=False)
        with self.assertRaises(MotoristaInativo):
            self.validador.validar(reserva(motorista=inativo), [])

    def test_motorista_em_dois_lugares_ao_mesmo_tempo(self):
        existente = reserva(time(8), time(10), veiculo=VL02, motorista=ANA_B, id=1)
        with self.assertRaises(ConflitoDeMotorista) as ctx:
            self.validador.validar(reserva(time(9), time(11), motorista=ANA_B), [existente])
        self.assertIn("Ana", ctx.exception.mensagem)

    def test_motorista_livre_depois_do_retorno(self):
        existente = reserva(time(8), time(10), veiculo=VL02, motorista=ANA_B, id=1)
        self.validador.validar(reserva(time(10), time(12), motorista=ANA_B), [existente])

    def test_reserva_cancelada_libera_o_motorista(self):
        cancelada = reserva(time(8), time(10), motorista=ANA_B, id=1, status=StatusReserva.CANCELADA)
        self.validador.validar(reserva(time(9), time(11), motorista=ANA_B), [cancelada])

    def test_edicao_ignora_a_propria_reserva(self):
        existente = reserva(time(8), time(10), motorista=ANA_B, id=1)
        self.validador.validar(reserva(time(8), time(11), motorista=ANA_B, id=1), [existente])

if __name__ == "__main__":
    unittest.main()
