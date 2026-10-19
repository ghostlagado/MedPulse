// Camada de acesso à API Flask: um único lugar para URL, timeout e erros.

export class ErroApi extends Error {
    constructor(mensagem, { status = 0, codigo = 'desconhecido' } = {}) {
        super(mensagem);
        this.status = status;
        this.codigo = codigo;
    }
}

const BASE = '/api';

async function requisitar(caminho, { params = null, method = 'GET', corpo = null, tempoLimite = 9000 } = {}) {
    const url = new URL(BASE + caminho, window.location.origin);
    if (params) {
        for (const [chave, valor] of Object.entries(params)) {
            if (valor === null || valor === undefined || valor === '') continue;
            url.searchParams.set(chave, Array.isArray(valor) ? valor.join(',') : valor);
        }
    }

    const controlador = new AbortController();
    const temporizador = setTimeout(() => controlador.abort(), tempoLimite);
    try {
        const resposta = await fetch(url, {
            method,
            signal: controlador.signal,
            headers: corpo ? { 'Content-Type': 'application/json' } : {},
            body: corpo ? JSON.stringify(corpo) : undefined,
        });
        const texto = await resposta.text();
        let dados = {};
        try { dados = texto ? JSON.parse(texto) : {}; }
        catch { /* resposta não-JSON: tratada abaixo */ }

        if (!resposta.ok) {
            throw new ErroApi(dados.erro || `HTTP ${resposta.status}`, {
                status: resposta.status,
                codigo: dados.codigo || 'http',
            });
        }
        return dados;
    } catch (erro_) {
        if (erro_ instanceof ErroApi) throw erro_;
        const nome = erro_ && erro_.name === 'AbortError' ? 'Tempo limite excedido' : 'Sem conexão com a API';
        throw new ErroApi(nome, { status: 0, codigo: erro_ && erro_.name === 'AbortError' ? 'timeout' : 'rede' });
    } finally {
        clearTimeout(temporizador);
    }
}

const lista = (valor) => (valor || []).join(',');

export const api = {
    config: () => requisitar('/config'),
    saude: () => requisitar('/health', { tempoLimite: 5000 }),
    local: (token) => requisitar(`/locais/${token}`),
    resumo: (hospitais, horas) => requisitar('/resumo', { params: { hospitais: lista(hospitais), horas } }),
};

export default api;
