class ReservaInvalida(Exception):
    def __init__(self, mensagem, campo=None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.campo = campo


class CamposObrigatorios(ReservaInvalida):
    def __init__(self, campos):
        self.campos = list(campos)
        super().__init__(
            f"Campos obrigatórios não informados: {', '.join(self.campos)}."
        )


class CapacidadeExcedida(ReservaInvalida):
    pass


class PeriodoInvalido(ReservaInvalida):
    pass


class ConflitoDeHorario(ReservaInvalida):
    def __init__(self, reserva_existente):
        self.reserva_existente = reserva_existente
        veiculo = reserva_existente.veiculo.codigo
        super().__init__(
            f"O veículo {veiculo} já está reservado em "
            f"{reserva_existente.data:%d/%m/%Y} das "
            f"{reserva_existente.saida:%H:%M} às {reserva_existente.retorno:%H:%M}.",
            campo="veiculo",
        )


class SemVeiculoDisponivel(ReservaInvalida):
    def __init__(self, categoria, data, saida, retorno):
        super().__init__(
            f"Não há veículo da categoria {categoria.value} disponível em "
            f"{data:%d/%m/%Y} das {saida:%H:%M} às {retorno:%H:%M}.",
            campo="categoria",
        )


class ReservaNaoEncontrada(Exception):
    def __init__(self, reserva_id):
        self.reserva_id = reserva_id
        super().__init__(f"Reserva {reserva_id} não encontrada.")


class VeiculoInativo(ReservaInvalida):
    def __init__(self, codigo):
        super().__init__(
            f"O veículo {codigo} está inativo (fora de operação) e não pode ser reservado.",
            campo="veiculo",
        )


class ReservaNaoEditavel(ReservaInvalida):
    def __init__(self, reserva_id, status):
        super().__init__(
            f"A reserva {reserva_id} está {status.rotulo} e não pode ser alterada.",
            campo="status",
        )
