// Comunicação com a API do PBL 1. Toda resposta de erro vira um ErroApi
// com o corpo padronizado do servidor: { sucesso, codigo, erro, campo, campos? }.

export class ErroApi extends Error {
  constructor(status, corpo) {
    super(corpo?.erro || "Erro inesperado no servidor.");
    this.status = status;
    this.corpo = corpo || {};
  }
}

async function pedir(metodo, url, dados) {
  let resposta;
  try {
    resposta = await fetch(url, {
      method: metodo,
      cache: "no-store",
      headers: dados ? { "Content-Type": "application/json" } : {},
      body: dados ? JSON.stringify(dados) : undefined,
    });
  } catch {
    throw new ErroApi(0, { erro: "Não consegui falar com o servidor. Ele está rodando?" });
  }

  let corpo = null;
  try { corpo = await resposta.json(); } catch { /* resposta sem JSON */ }
  if (!resposta.ok) {
    throw new ErroApi(resposta.status, corpo || { erro: `Erro ${resposta.status} no servidor.` });
  }
  return corpo;
}

export const api = {
  veiculos: () => pedir("GET", "/api/veiculos/").then((c) => c.veiculos),
  motoristas: () => pedir("GET", "/api/motoristas/").then((c) => c.motoristas),
  reservas: (data) => pedir("GET", `/api/reservas/${data ? `?data=${data}` : ""}`).then((c) => c.reservas),
  reserva: (id) => pedir("GET", `/api/reservas/${id}/`).then((c) => c.reserva),
  colaboradores: () => pedir("GET", "/api/colaboradores/"),
  disponibilidade: (params) => pedir("GET", `/api/disponibilidade/?${new URLSearchParams(params)}`),
  criar: (dados) => pedir("POST", "/api/reservas/", dados),
  atualizar: (id, dados) => pedir("PUT", `/api/reservas/${id}/`, dados),
  cancelar: (id) => pedir("DELETE", `/api/reservas/${id}/`),
};
