// Helpers de DOM e formatação compartilhados pelos componentes.

import { agoraServidor, horaCurta } from '../relogio.js';

export const $ = (seletor, escopo = document) => escopo.querySelector(seletor);
export const $$ = (seletor, escopo = document) => [...escopo.querySelectorAll(seletor)];

export function el(tag, opcoes = {}, ...filhos) {
    const no = document.createElement(tag);
    const { classe, texto, atributos = {}, dataset = {}, oculto = false, evento = {} } = opcoes;
    if (classe) no.className = classe;
    if (texto !== undefined) no.textContent = texto;
    if (oculto) no.hidden = true;
    for (const [chave, valor] of Object.entries(atributos)) no.setAttribute(chave, valor);
    for (const [chave, valor] of Object.entries(dataset)) no.dataset[chave] = valor;
    for (const [nome, handler] of Object.entries(evento)) no.addEventListener(nome, handler);
    for (const filho of filhos.flat()) {
        if (filho === null || filho === undefined || filho === false) continue;
        no.appendChild(typeof filho === 'string' ? document.createTextNode(filho) : filho);
    }
    return no;
}

export function icone(id, tamanho = 15, cor = 'currentColor') {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'ico');
    svg.setAttribute('width', tamanho);
    svg.setAttribute('height', tamanho);
    svg.setAttribute('aria-hidden', 'true');
    if (cor !== 'currentColor') svg.style.color = cor;
    const uso = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    uso.setAttribute('href', `#${id}`);
    svg.appendChild(uso);
    return svg;
}

export function limpar(no) {
    while (no && no.firstChild) no.removeChild(no.firstChild);
    return no;
}

export function minutosFmt(minutos) {
    if (minutos === null || minutos === undefined || Number.isNaN(minutos)) return '—';
    const total = Math.max(0, Math.round(minutos));
    if (total < 60) return `${total}min`;
    const h = Math.floor(total / 60);
    const m = total % 60;
    return m ? `${h}h${String(m).padStart(2, '0')}` : `${h}h`;
}

// Toda hora exibida sai do relógio do servidor, no fuso da operação.
export function horaFmt(iso) {
    return iso ? horaCurta(iso) : '—';
}

export function emRelacao(iso) {
    if (!iso) return '—';
    // A diferença é medida contra o relógio do servidor: a TV pode estar desajustada.
    const diff = (agoraServidor().getTime() - new Date(iso).getTime()) / 60000;
    if (diff < 1) return 'agora';
    return `há ${minutosFmt(diff)}`;
}

export function corPrioridade(prioridade) {
    return `var(--p-${prioridade || 'sem_triagem'})`;
}

export function corSobrePrioridade(prioridade) {
    return `var(--p-${prioridade || 'sem_triagem'}-fg)`;
}

export function esqueletoLinha() {
    return el('div', { classe: 'esqueleto-linha' },
        el('div', { classe: 'esqueleto' }),
        el('div', { classe: 'esqueleto' }),
        el('div', { classe: 'esqueleto' }));
}

export function esqueletoLista(n = 5) {
    const frag = document.createDocumentFragment();
    for (let i = 0; i < n; i++) frag.appendChild(esqueletoLinha());
    return frag;
}

export function vazio(mensagem, iconeId = 'i-pessoas') {
    return el('div', { classe: 'vazio' },
        icone(iconeId, 26, 'var(--texto-3)'),
        el('span', { texto: mensagem }));
}

export function erro(mensagem) {
    return el('div', { classe: 'erro-estado' },
        icone('i-alerta', 24, 'var(--perigo)'),
        el('span', { texto: mensagem }));
}
