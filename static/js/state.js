// Store único do painel. O escopo é agregado: apenas indicadores calculados pelo
// servidor entram aqui. Nenhum registro individual de paciente — e portanto nenhum
// dado pessoal — existe no estado do navegador.

const CHAVE_SELECAO = 'medpulse:selecao';
const CHAVE_TEMA = 'medpulse:tema';

export const PESO_PRIORIDADE = {
    alta: 0, intermediaria: 1, baixa: 2, nao_urgente: 3, sem_triagem: 4,
};

const ouvintes = new Map();

function notificar(canal, dado) {
    for (const fn of ouvintes.get(canal) || []) {
        try { fn(dado); } catch (e) { console.error(`[${canal}]`, e); }
    }
}

export function inscrever(canais, fn) {
    const lista = [].concat(canais);
    lista.forEach((canal) => {
        if (!ouvintes.has(canal)) ouvintes.set(canal, new Set());
        ouvintes.get(canal).add(fn);
    });
    return () => lista.forEach((canal) => ouvintes.get(canal)?.delete(fn));
}

export const estado = {
    hospitais: [],
    selecao: [],
    resumo: null,
    config: null,
    tema: 'escuro',
    // Dois estados apenas: 'online' significa WebSocket estabelecido e funcional.
    conexao: 'offline',
    detalheConexao: 'abertura de canal…',
    transporte: 'socket',
    carregando: true,
    erro: null,
    contadores: { eventos: 0, snapshots: 0, ignorados: 0 },
    sincronizadoEm: null,
};

export function rotulo(chave, tipo = 'prioridade') {
    const mapa = estado.config?.[`rotulos_${tipo}`] || {};
    return mapa[chave] || chave;
}

export function definirHospitais(hospitais) {
    estado.hospitais = hospitais || [];
    notificar('hospitais', estado.hospitais);
}

export function definirConfig(config) {
    estado.config = config;
    notificar('config', config);
}

export function definirTema(tema) {
    estado.tema = tema === 'claro' ? 'claro' : 'escuro';
    try { localStorage.setItem(CHAVE_TEMA, estado.tema); }
    catch { /* sem persistência: o tema vale só para esta sessão */ }
    notificar('tema', estado.tema);
    return estado.tema;
}

export function lerTemaSalvo() {
    try { return localStorage.getItem(CHAVE_TEMA); }
    catch { return null; }
}

function chaveSelecao() {
    const token = window.MEDPULSE?.localToken || 'padrao';
    return `${CHAVE_SELECAO}:${token}`;
}

export function lembrarSelecao() {
    try { localStorage.setItem(chaveSelecao(), JSON.stringify(estado.selecao)); }
    catch { /* modo privado: seleção segue apenas em memória */ }
}

export function restaurarSelecao() {
    try {
        const salvo = JSON.parse(localStorage.getItem(chaveSelecao()) || 'null');
        if (Array.isArray(salvo)) return salvo.map(Number).filter((n) => !Number.isNaN(n));
    } catch { /* dados antigos corrompidos: ignora */ }
    return null;
}

export function selecionar(ids, { persistir = true } = {}) {
    const validos = new Set(estado.hospitais.map((h) => h.id));
    estado.selecao = [...new Set(ids.map(Number))].filter((id) => validos.has(id));
    if (persistir) lembrarSelecao();
    notificar('selecao', estado.selecao);
    return estado.selecao;
}

export function iniciarSelecao() {
    const salvos = restaurarSelecao();
    const validos = new Set(estado.hospitais.map((h) => h.id));
    if (salvos && salvos.some((id) => validos.has(id))) return selecionar(salvos.filter((id) => validos.has(id)));
    const preferido = estado.hospitais.find((h) => h.demo) || estado.hospitais[0];
    return selecionar(preferido ? [preferido.id] : []);
}

export function hospitaisDemo() {
    return estado.hospitais.filter((h) => h.demo).map((h) => h.id);
}

// O servidor devolve o escopo junto de cada agregado (`hospitais`). Uma mudança de
// seleção dispara mais de uma requisição e um re-subscribe, então respostas podem
// chegar fora de ordem: um payload de outra combinação de hospitais é descartado em
// vez de sobrecrever os números da seleção atual.
function escopoAtual(pagado) {
    const veio = (pagado?.hospitais || []).map(Number).sort((a, b) => a - b);
    const esperado = [...estado.selecao].sort((a, b) => a - b);
    return veio.length === esperado.length && veio.every((id, i) => id === esperado[i]);
}

export function aplicarSnapshot(snapshot) {
    if (!snapshot) return;
    if (!escopoAtual(snapshot)) {
        estado.contadores.ignorados += 1;
        return;
    }
    if (snapshot.resumo) estado.resumo = snapshot.resumo;
    estado.sincronizadoEm = snapshot.emitido_em || new Date().toISOString();
    estado.contadores.snapshots += 1;
    estado.carregando = false;
    estado.erro = null;
    notificar('resumo', estado.resumo);
    notificar('meta', estado);
}

// Eventos de paciente chegam já sem identificação. O painel não os Armazena: eles só
// confirmam que o canal está vivo; os números vêm logo em seguida em resumo:atualizado.
export function registrarEvento(atendimento) {
    if (!atendimento || atendimento.id === undefined) return false;
    if (estado.selecao.length && !estado.selecao.includes(atendimento.hospital_id)) {
        estado.contadores.ignorados += 1;   // fora da seleção: descartado
        return false;
    }
    estado.contadores.eventos += 1;
    notificar('meta', estado);
    return true;
}

export function aplicarResumo(resumo) {
    if (!resumo) return;
    if (!escopoAtual(resumo)) {
        estado.contadores.ignorados += 1;
        return;
    }
    estado.resumo = resumo;
    estado.sincronizadoEm = resumo.gerado_em || new Date().toISOString();
    notificar('resumo', resumo);
    notificar('meta', estado);
}

export function definirConexao(conexao, detalhe = '', transporte = 'socket') {
    estado.conexao = conexao === 'online' ? 'online' : 'offline';
    estado.detalheConexao = detalhe;
    estado.transporte = transporte;
    notificar('conexao', { conexao: estado.conexao, detalhe, transporte });
}

export function definirErro(erro) {    estado.erro = erro;
    estado.carregando = false;
    notificar('erro', erro);
}

export default estado;
