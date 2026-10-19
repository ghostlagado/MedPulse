// Relógio do painel: a referência temporal é o servidor, nunca o computador que abre
// a página (a TV de um hospital pode estar sem hora, sem fuso ou em outro continente).
//
// O deslocamento servidor−navegador é recalculado a cada snapshot/resumo que já passa
// pelo WebSocket, então não há requisição extra de horário.

let deslocamentoMs = 0;
let fuso = 'UTC';
let formatadorHora = null;
let formatadorData = null;

function montarFormatadores() {
    const base = { timeZone: fuso, hour12: false };
    try {
        formatadorHora = new Intl.DateTimeFormat('pt-BR', { ...base, hour: '2-digit', minute: '2-digit', second: '2-digit' });
        formatadorData = new Intl.DateTimeFormat('pt-BR', { ...base, weekday: 'short', day: '2-digit', month: 'short' });
    } catch {
        // Fuso desconhecido pelo navegador: ainda assim mostramos a hora do servidor.
        formatadorHora = new Intl.DateTimeFormat('pt-BR', { hour12: false });
        formatadorData = new Intl.DateTimeFormat('pt-BR', { weekday: 'short', day: '2-digit', month: 'short' });
    }
}

montarFormatadores();

export function definirFuso(nome) {
    if (!nome || nome === fuso) return;
    fuso = nome;
    montarFormatadores();
}

export function sincronizarRelogio(isoDoServidor) {
    if (!isoDoServidor) return;
    const momento = Date.parse(isoDoServidor);
    if (Number.isNaN(momento)) return;
    deslocamentoMs = momento - Date.now();
}

export function agoraServidor() {
    return new Date(Date.now() + deslocamentoMs);
}

export function horaCurta(iso) {
    const momento = iso ? new Date(iso) : agoraServidor();
    if (Number.isNaN(momento.getTime())) return '—';
    return formatadorHora.format(momento);
}

export function horaCurtaSemSegundos(iso) {
    const momento = iso ? new Date(iso) : agoraServidor();
    if (Number.isNaN(momento.getTime())) return '—';
    return formatadorHora.format(momento).slice(0, 5);
}

export function dataCurta() {
    return formatadorData.format(agoraServidor());
}

export function horaDoBucket(iso) {
    const momento = new Date(iso);
    if (Number.isNaN(momento.getTime())) return '';
    return `${horaCurta(iso).slice(0, 2)}h`;
}

export default { definirFuso, sincronizarRelogio, agoraServidor, horaCurta, dataCurta, horaDoBucket };
