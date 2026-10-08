from core.domain.entidades import CategoriaVeiculo, Reserva, Veiculo

from .models import ReservaModel, VeiculoModel


def _veiculo_para_dominio(modelo):
    return Veiculo(modelo.codigo, CategoriaVeiculo(modelo.categoria))


def _reserva_para_dominio(modelo):
    pretendida = modelo.categoria_pretendida
    return Reserva(
        id=modelo.id,
        solicitante=modelo.solicitante,
        setor=modelo.setor,
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
    )


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
            codigo=veiculo.codigo, defaults={"categoria": veiculo.categoria.value}
        )
        return veiculo


class ReservaDjangoRepository:
    def _consulta(self):
        return ReservaModel.objects.select_related("veiculo")

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
            "solicitante": reserva.solicitante,
            "setor": reserva.setor,
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
        }
        if reserva.id is None:
            modelo = ReservaModel.objects.create(**valores)
        else:
            ReservaModel.objects.filter(pk=reserva.id).update(**valores)
            modelo = self._consulta().get(pk=reserva.id)
        return _reserva_para_dominio(modelo)

    def excluir(self, reserva_id):
        apagadas, _ = ReservaModel.objects.filter(pk=reserva_id).delete()
        return apagadas > 0
