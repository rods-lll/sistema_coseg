class CadastroService:
    """Consultas aos cadastros de apoio (colaboradores e setores)."""

    def __init__(self, colaboradores):
        self._colaboradores = colaboradores

    def colaboradores(self, setor=None):
        return self._colaboradores.listar(setor)

    def setores(self):
        return sorted({c.setor for c in self._colaboradores.listar()}, key=str.lower)
