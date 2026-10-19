// Fila por prioridade: matriz prioridade × etapa, montada a partir de
// resumo.por_prioridade e resumo.filas — ambos calculados no servidor. Nada é
// agregado nem ordenado no navegador, e não há nenhum registro individual.

import { $, el, esqueletoLista, minutosFmt, corPrioridade, corSobrePrioridade, vazio } from './dom.js';
import { estado, inscrever, PESO_PRIORIDADE, rotulo } from '../state.js';

const ETAPAS = ['fila', 'em_atendimento', 'atendidos'];

function tempoMedio(filas, status, prioridade) {
    const item = (filas || []).find((f) => f.status === status && f.prioridade === prioridade);
    return item ? item.tempo_medio_min : null;
}

function linha(prioridade, dados, filas, emAberto) {
    const celulas = ETAPAS.map((etapa) => el('span', {
        classe: `matriz__num${dados[etapa] ? '' : ' matriz__num--zero'}`,
        texto: String(dados[etapa] || 0),
    }));
    return el('div', {
        classe: 'matriz__linha',
        dataset: { aberto: String(emAberto) },
    },
        el('span', { classe: 'matriz__prioridade' },
            el('i', {
                classe: 'ponto-prioridade',
                atributos: { style: `--cor:${corPrioridade(prioridade)};--fg:${corSobrePrioridade(prioridade)}` },
            }),
            el('b', { texto: rotulo(prioridade) }),
        ),
        ...celulas,
        el('span', {
            classe: 'matriz__tempo',
            texto: minutosFmt(tempoMedio(filas, 'aguardando', prioridade)
                ?? tempoMedio(filas, 'triagem', prioridade) ?? 0),
        }),
    );
}

function cabecalho() {
    return el('div', { classe: 'matriz__linha matriz__linha--cabecalho' },
        el('span', { texto: 'Prioridade' }),
        el('span', { texto: 'Fila' }),
        el('span', { texto: 'Atend.' }),
        el('span', { texto: 'Concl.' }),
        el('span', { texto: 'Espera' }));
}

export function montarFilas(container = $('#filas-abertas')) {
    if (!container) return () => {};

    function atualizar() {
        if (estado.carregando && !estado.resumo) {
            container.replaceChildren(esqueletoLista(5));
            return;
        }
        const porPrioridade = estado.resumo?.por_prioridade || {};
        const filas = estado.resumo?.filas || [];
        const ordem = Object.keys(PESO_PRIORIDADE)
            .filter((p) => p in porPrioridade)
            .sort((a, b) => PESO_PRIORIDADE[a] - PESO_PRIORIDADE[b]);

        const algum = ordem.some((p) => (porPrioridade[p].fila || 0) + (porPrioridade[p].em_atendimento || 0) > 0);
        if (!algum) {
            container.replaceChildren(cabecalho(), vazio('Nenhum atendimento em aberto na seleção atual', 'i-pessoas'));
            return;
        }

        container.replaceChildren(
            cabecalho(),
            ...ordem.map((p) => linha(p, porPrioridade[p], filas,
                (porPrioridade[p].fila || 0) + (porPrioridade[p].em_atendimento || 0) > 0)),
        );
    }

    inscrever(['resumo', 'config'], atualizar);
    atualizar();
    return atualizar;
}

export default montarFilas;
