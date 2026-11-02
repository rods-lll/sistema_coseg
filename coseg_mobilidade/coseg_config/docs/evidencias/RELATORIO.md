# Evidências de teste da interface (PBL 2)

Gerado por `python tests/e2e/evidencias.py` em 27/10/2026 12:35, num Chromium real, contra o Django com banco temporário e o seed do projeto.

| Grupo | Verificação | Resultado |
|---|---|---|
| Integração | Formulário pede a disponibilidade ao servidor (GET /api/disponibilidade/) (1 consulta(s)) | ✅ ok |
| Integração | util.js não tem mais regra de capacidade/conflito/escala  | ✅ ok |
| Mensagens | Campos obrigatórios vazios aparecem marcados no próprio campo (4 campos) | ✅ ok |
| CRUD | Criar (POST) com 'Qualquer VL' devolve 201 e um VL (#5 VL-01) | ✅ ok |
| Integração | Motorista mostrado antes de enviar é o que o servidor escalou (Beatriz Lopes) | ✅ ok |
| Mensagens | Aviso de sucesso depois da resposta do servidor  | ✅ ok |
| Integração | VL-01 aparece ocupado no mesmo horário (motivo vem do servidor) (VL · Ocupado 08:00–10:00) | ✅ ok |
| Mensagens | Conflito de horário: 409 do servidor aparece no campo do veículo (CONFLITO_DE_HORARIO: O veículo VL-02 já está reservado em 28/10/2026 das 09:00 às 09:30.) | ✅ ok |
| Mensagens | 7 pessoas em 'Qualquer VL': o servidor avisa que excede a capacidade (VL comporta até 4 passageiros e foram informados 7. Utilize a categoria VC.) | ✅ ok |
| Integração | Categoria mínima vira VC e 'Qualquer VL' fica bloqueado  | ✅ ok |
| CRUD | Ler (GET /api/reservas/<id>/) devolve a reserva criada  | ✅ ok |
| CRUD | Editar (PUT) muda o retorno e mantém o motorista (retorno 11:00, motorista Beatriz Lopes) | ✅ ok |
| CRUD | Excluir (DELETE) cancela a reserva e ela fica no histórico  | ✅ ok |
| Integração | Servidor lento: Reservas → Nova reserva rápido mostra a tela certa (tela: Pedir um veículo) | ✅ ok |
| Responsividade | celular 390px: nenhuma tela com rolagem horizontal e o menu inteiro visível  | ✅ ok |
| Responsividade | tablet 768px: nenhuma tela com rolagem horizontal e o menu inteiro visível  | ✅ ok |
| Responsividade | desktop 1366px: nenhuma tela com rolagem horizontal e o menu inteiro visível  | ✅ ok |
| Geral | Nenhum erro de JavaScript no console  | ✅ ok |

## Prints

- [01-formulario-desktop](01-formulario-desktop.png)
- [02-campos-obrigatorios](02-campos-obrigatorios.png)
- [03-criada-na-agenda](03-criada-na-agenda.png)
- [04-veiculo-ocupado](04-veiculo-ocupado.png)
- [05-conflito-409](05-conflito-409.png)
- [06-capacidade](06-capacidade.png)
- [07-editada](07-editada.png)
- [08-confirmar-cancelamento](08-confirmar-cancelamento.png)
- [09-cancelada](09-cancelada.png)
- [resp-celular-agenda](resp-celular-agenda.png)
- [resp-celular-frota](resp-celular-frota.png)
- [resp-celular-inicio](resp-celular-inicio.png)
- [resp-celular-motoristas](resp-celular-motoristas.png)
- [resp-celular-nova](resp-celular-nova.png)
- [resp-celular-reservas](resp-celular-reservas.png)
- [resp-desktop-agenda](resp-desktop-agenda.png)
- [resp-desktop-inicio](resp-desktop-inicio.png)
- [resp-tablet-agenda](resp-tablet-agenda.png)
- [resp-tablet-frota](resp-tablet-frota.png)
- [resp-tablet-inicio](resp-tablet-inicio.png)
- [resp-tablet-motoristas](resp-tablet-motoristas.png)
- [resp-tablet-nova](resp-tablet-nova.png)
- [resp-tablet-reservas](resp-tablet-reservas.png)
