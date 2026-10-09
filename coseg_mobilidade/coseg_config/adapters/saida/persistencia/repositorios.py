from django.utils import timezone

from core.domain.entidades import CategoriaVeiculo, Reserva, StatusReserva, Veiculo

from .models import ColaboradorModel, ReservaModel, SetorModel, VeiculoModel


def _normalizar(texto):
    return " ".join((texto or "").split())


def _veiculo_para_dominio(modelo):
    return Veiculo(
        codigo=modelo.codigo,
        categoria=CategoriaVeiculo(modelo.categoria),
        placa=modelo.placa,
        modelo=modelo.modelo,
        ativo=modelo.ativo,
    )


def _reserva_para_dominio(modelo):
    pretendida = modelo.categoria_pretendida
    return Reserva(
        id=modelo.id,
        solicitante=modelo.colaborador.nome,
        setor=modelo.colaborador.setor.nome,
        atividade=modelo.atividade,
        origem=modelo.origem,
        destino=modelo.destino,
        data=modelo.data,
        saida=modelo.saida,
        retorno=modelo.retorno,
        passageiros=modelo.passageiros,
        veiculo=_veiculo_para_dominio(modelo.veiculo),
        categoria=CategoriaVeiculo(pretendida) if pretendida else None,
        observacoes=modelo.observacoes,
        status=StatusReserva(modelo.status),
    )


def obter_ou_criar_colaborador(nome, nome_setor):
    """A API recebe solicitante e setor como texto: reaproveita o cadastro
    existente (sem diferenciar maiúsculas) ou cria um novo."""
    nome, nome_setor = _normalizar(nome), _normalizar(nome_setor)
    setor = SetorModel.objects.filter(nome__iexact=nome_setor).first()
    if setor is None:
        setor = SetorModel.objects.create(nome=nome_setor)
    colaborador = ColaboradorModel.objects.filter(nome__iexact=nome, setor=setor).first()
    if colaborador is None:
        colaborador = ColaboradorModel.objects.create(nome=nome, setor=setor)
    return colaborador


class VeiculoDjangoRepository:
    def listar(self):
        return [_veiculo_para_dominio(m) for m in VeiculoModel.objects.all()]

    def listar_por_categoria(self, categoria):
        consulta = VeiculoModel.objects.filter(categoria=categoria.value)
        return [_veiculo_para_dominio(m) for m in consulta]

    def obter(self, codigo):
        modelo = VeiculoModel.objects.filter(codigo=codigo).first()
        return _veiculo_para_dominio(modelo) if modelo else None

    def salvar(self, veiculo):
        VeiculoModel.objects.update_or_create(
            codigo=veiculo.codigo,
            defaults={
                "categoria": veiculo.categoria.value,
                "placa": veiculo.placa,
                "modelo": veiculo.modelo,
                "ativo": veiculo.ativo,
            },
        )
        return veiculo


class ReservaDjangoRepository:
    def _consulta(self):
        return ReservaModel.objects.select_related("veiculo", "colaborador__setor")

    def listar(self, data=None):
        consulta = self._consulta()
        if data is not None:
            consulta = consulta.filter(data=data)
        return [_reserva_para_dominio(m) for m in consulta]

    def listar_do_veiculo_na_data(self, codigo, data):
        consulta = self._consulta().filter(veiculo__codigo=codigo, data=data)
        return [_reserva_para_dominio(m) for m in consulta]

    def obter(self, reserva_id):
        modelo = self._consulta().filter(pk=reserva_id).first()
        return _reserva_para_dominio(modelo) if modelo else None

    def salvar(self, reserva):
        valores = {
            "colaborador": obter_ou_criar_colaborador(reserva.solicitante, reserva.setor),
            "atividade": reserva.atividade,
            "origem": reserva.origem,
            "destino": reserva.destino,
            "data": reserva.data,
            "saida": reserva.saida,
            "retorno": reserva.retorno,
            "passageiros": reserva.passageiros,
            "veiculo": VeiculoModel.objects.get(codigo=reserva.veiculo.codigo),
            "categoria_pretendida": reserva.categoria.value if reserva.categoria else "",
            "observacoes": reserva.observacoes,
            "status": reserva.status.value,
        }
        if reserva.id is None:
            modelo = ReservaModel.objects.create(**valores)
        else:
            modelo = ReservaModel.objects.get(pk=reserva.id)
            if (
                reserva.status is StatusReserva.CANCELADA
                and modelo.cancelada_em is None
            ):
                valores["cancelada_em"] = timezone.now()
            for campo, valor in valores.items():
                setattr(modelo, campo, valor)
            modelo.save()
        return self.obter(modelo.pk)
