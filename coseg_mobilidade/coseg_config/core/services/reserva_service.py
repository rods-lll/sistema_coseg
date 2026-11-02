from dataclasses import dataclass, field, replace

from core.domain.entidades import Reserva, StatusReserva
from core.domain.excecoes import (
    ReservaInvalida,
    SemMotoristaDisponivel,
    ReservaNaoEditavel,
    ReservaNaoEncontrada,
    SemVeiculoDisponivel,
    VeiculoInativo,
)
from core.domain.validadores import (
    ValidadorCampos,
    ValidadorCapacidade,
    ValidadorConflito,
    ValidadorMotorista,
    ValidadorPeriodo,
    categoria_minima,
    ordem_de_escala,
)


@dataclass
class Situacao:
    """Como um veículo (ou motorista) está para o pedido simulado."""

    item: object
    livre: bool
    motivo: str
    conflito: Reserva | None = None


@dataclass
class Simulacao:
    """Resultado de simular uma reserva sem gravar (usado pelo formulário web)."""

    categoria_minima: object = None
    erros: list = field(default_factory=list)
    veiculos: list = field(default_factory=list)
    veiculo: object = None
    motoristas: list = field(default_factory=list)
    motorista: object = None
    motoristas_cadastrados: int = 0


def _faixa(reserva):
    return f"{reserva.saida:%H:%M}–{reserva.retorno:%H:%M}"


class ReservaService:
    def __init__(self, reservas, veiculos, hoje=None, motoristas=None, agora=None):
        self._reservas = reservas
        self._veiculos = veiculos
        self._motoristas = motoristas
        self._motorista = ValidadorMotorista()
        self._campos = ValidadorCampos()
        self._capacidade = ValidadorCapacidade()
        self._periodo = ValidadorPeriodo(hoje=hoje, agora=agora)
        self._conflito = ValidadorConflito()

    def frota(self):
        return self._veiculos.listar()

    def motoristas(self):
        return self._motoristas.listar() if self._motoristas else []

    def listar(self, data=None):
        return self._reservas.listar(data)

    def obter(self, reserva_id):
        reserva = self._reservas.obter(reserva_id)
        if reserva is None:
            raise ReservaNaoEncontrada(reserva_id)
        return reserva

    def validar(self, reserva, codigo_veiculo=None, codigo_motorista=None):
        """Aplica todas as regras sem gravar (usado pelo Django Admin)."""
        self._preparar(reserva, codigo_veiculo, codigo_motorista)
        return reserva

    def criar(self, reserva, codigo_veiculo=None, codigo_motorista=None):
        self._preparar(reserva, codigo_veiculo, codigo_motorista)
        return self._reservas.salvar(reserva)

    def atualizar(self, reserva_id, reserva, codigo_veiculo=None, codigo_motorista=None):
        atual = self._obter_confirmada(reserva_id)
        reserva.id = reserva_id
        reserva.status = atual.status
        self._preparar(reserva, codigo_veiculo, codigo_motorista, preferido=atual.motorista, original=atual)
        return self._reservas.salvar(reserva)

    def cancelar(self, reserva_id):
        """Cancela sem apagar: a reserva fica no histórico e libera o horário."""
        return self._mudar_status(reserva_id, StatusReserva.CANCELADA)

    def concluir(self, reserva_id):
        return self._mudar_status(reserva_id, StatusReserva.CONCLUIDA)

    def _mudar_status(self, reserva_id, novo_status):
        reserva = self._obter_confirmada(reserva_id)
        reserva.status = novo_status
        return self._reservas.salvar(reserva)

    def _obter_confirmada(self, reserva_id):
        reserva = self.obter(reserva_id)
        if reserva.status is not StatusReserva.CONFIRMADA:
            raise ReservaNaoEditavel(reserva_id, reserva.status)
        return reserva

    def _preparar(self, reserva, codigo_veiculo, codigo_motorista=None, preferido=None, original=None):
        if codigo_veiculo:
            reserva.veiculo = self._buscar_veiculo(codigo_veiculo)
        if codigo_motorista:
            reserva.motorista = self._buscar_motorista(codigo_motorista)
        self._campos.validar(reserva)
        self._capacidade.validar(reserva)
        self._periodo.validar(reserva, original)
        if reserva.veiculo is None:
            reserva.veiculo = self._alocar(reserva)
        else:
            existentes = self._reservas.listar_do_veiculo_na_data(
                reserva.veiculo.codigo, reserva.data
            )
            self._conflito.validar(reserva, existentes)
        if reserva.motorista is not None:
            # Motorista indicado à mão (admin do COSEG): só confere as regras.
            agenda = self._reservas.listar_do_motorista_na_data(
                reserva.motorista.matricula, reserva.data
            )
            self._motorista.validar(reserva, agenda)
        else:
            reserva.motorista = self._escalar(reserva, preferido)

    def _situacao_dos_motoristas(self, reserva):
        """Avalia cada motorista para a reserva (mesmas regras do ValidadorMotorista)."""
        categoria = reserva.veiculo.categoria
        situacoes = []
        for motorista in self._motoristas.listar():
            if not motorista.ativo:
                situacoes.append((Situacao(motorista, False, "Inativo"), 0))
                continue
            if not motorista.pode_dirigir(categoria):
                situacoes.append((Situacao(motorista, False, f"Não dirige {categoria.value}"), 0))
                continue
            if not motorista.cnh_valida_em(reserva.data):
                situacoes.append((Situacao(motorista, False, "CNH vencida"), 0))
                continue
            agenda = [
                r for r in self._reservas.listar_do_motorista_na_data(motorista.matricula, reserva.data)
                if r.id != reserva.id
            ]
            tentativa = replace(reserva, motorista=motorista)
            choque = next((r for r in agenda if tentativa.conflita_motorista_com(r)), None)
            carga = sum(r.duracao_minutos for r in agenda if r.status is not StatusReserva.CANCELADA)
            if choque:
                situacoes.append((Situacao(motorista, False, f"Escalado {_faixa(choque)}", choque), carga))
            else:
                situacoes.append((Situacao(motorista, True, "Livre"), carga))
        return situacoes

    def _escalar(self, reserva, preferido=None):
        """Escala automaticamente um motorista habilitado e livre no horário."""
        if self._motoristas is None or not self._motoristas.listar():
            return None  # sistema sem motoristas cadastrados: reserva segue sem escala
        livres = [
            (ordem_de_escala(sit.item, carga, preferido), sit.item)
            for sit, carga in self._situacao_dos_motoristas(reserva)
            if sit.livre
        ]
        if not livres:
            raise SemMotoristaDisponivel(
                reserva.veiculo.categoria, reserva.data, reserva.saida, reserva.retorno
            )
        return min(livres, key=lambda par: par[0])[1]

    def _buscar_motorista(self, matricula):
        motorista = self._motoristas.obter(matricula) if self._motoristas else None
        if motorista is None:
            raise ReservaInvalida(
                f"O motorista {matricula} não está cadastrado.", campo="motorista"
            )
        return motorista

    def _buscar_veiculo(self, codigo):
        veiculo = self._veiculos.obter(codigo)
        if veiculo is None:
            raise ReservaInvalida(
                f"O veículo {codigo} não está cadastrado na frota.", campo="veiculo"
            )
        if not veiculo.ativo:
            raise VeiculoInativo(codigo)
        return veiculo

    def _alocar(self, reserva):
        for candidato in self._veiculos.listar_por_categoria(reserva.categoria):
            if not candidato.ativo:
                continue
            existentes = self._reservas.listar_do_veiculo_na_data(
                candidato.codigo, reserva.data
            )
            tentativa = replace(reserva, veiculo=candidato)
            if self._conflito.localizar(tentativa, existentes) is None:
                return candidato
        raise SemVeiculoDisponivel(
            reserva.categoria, reserva.data, reserva.saida, reserva.retorno
        )

    # ------------------------------------------------------------ simulação ---
    def simular(self, data, saida, retorno, passageiros, codigo_veiculo=None,
                categoria=None, ignorar_id=None):
        """Responde, sem gravar nada, o que aconteceria com este pedido: situação de
        cada veículo e motorista, o veículo alocado e o motorista que seria escalado.
        O formulário web mostra isto em vez de repetir as regras no JavaScript."""
        resultado = Simulacao()
        try:
            resultado.categoria_minima = categoria_minima(passageiros)
        except ReservaInvalida as exc:
            resultado.erros.append(exc)
        alvo = categoria or resultado.categoria_minima
        tentativa = Reserva(
            solicitante="", setor="", atividade="", origem="", destino="",
            data=data, saida=saida, retorno=retorno, passageiros=passageiros,
            categoria=alvo, id=ignorar_id,
        )
        periodo_ok = True
        original = self._reservas.obter(ignorar_id) if ignorar_id else None
        try:
            self._periodo.validar(tentativa, original)
        except ReservaInvalida as exc:
            resultado.erros.append(exc)
            periodo_ok = tentativa.retorno > tentativa.saida  # data passada ainda mostra a agenda

        for veiculo in self._veiculos.listar():
            if not veiculo.ativo:
                resultado.veiculos.append(Situacao(veiculo, False, "Inativo"))
            elif passageiros > veiculo.capacidade:
                resultado.veiculos.append(Situacao(veiculo, False, f"Só {veiculo.capacidade} lugares"))
            elif not periodo_ok:
                resultado.veiculos.append(Situacao(veiculo, False, "Ajuste o horário"))
            else:
                existentes = self._reservas.listar_do_veiculo_na_data(veiculo.codigo, data)
                choque = self._conflito.localizar(replace(tentativa, veiculo=veiculo), existentes)
                if choque:
                    resultado.veiculos.append(Situacao(veiculo, False, f"Ocupado {_faixa(choque)}", choque))
                else:
                    resultado.veiculos.append(Situacao(veiculo, True, "Livre"))

        # Veículo que o servidor usaria: o escolhido, ou o primeiro livre da categoria.
        if codigo_veiculo:
            escolhido = next((s for s in resultado.veiculos if s.item.codigo == codigo_veiculo), None)
            resultado.veiculo = escolhido.item if escolhido and escolhido.livre else None
        elif alvo and periodo_ok:
            resultado.veiculo = next(
                (s.item for s in resultado.veiculos if s.livre and s.item.categoria is alvo), None
            )
        # Mesma ordem do _preparar: capacidade antes de procurar veículo livre.
        escolhido_pedido = next((s.item for s in resultado.veiculos if s.item.codigo == codigo_veiculo), None)
        capacidade_ok = True
        if alvo or escolhido_pedido:
            try:
                self._capacidade.validar(replace(tentativa, veiculo=escolhido_pedido))
            except ReservaInvalida as exc:
                capacidade_ok = False
                if exc not in resultado.erros and not any(
                    type(e) is type(exc) for e in resultado.erros
                ):
                    resultado.erros.append(exc)
        if resultado.veiculo is None and alvo and periodo_ok and capacidade_ok and not codigo_veiculo:
            resultado.erros.append(SemVeiculoDisponivel(alvo, data, saida, retorno))

        # Motorista que seria escalado.
        if self._motoristas is not None:
            resultado.motoristas_cadastrados = len(self._motoristas.listar())
        if resultado.veiculo is not None and periodo_ok and resultado.motoristas_cadastrados:
            tentativa = replace(tentativa, veiculo=resultado.veiculo)
            preferido = self._reservas.obter(ignorar_id).motorista if ignorar_id else None
            resultado.motoristas = [sit for sit, _ in self._situacao_dos_motoristas(tentativa)]
            try:
                resultado.motorista = self._escalar(tentativa, preferido)
            except ReservaInvalida as exc:
                resultado.erros.append(exc)
        return resultado
