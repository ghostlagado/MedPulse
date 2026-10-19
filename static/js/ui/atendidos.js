// Indicador de pacientes atendidos no período, por prioridade. Vem de
// resumo.por_prioridade.atendidos: contagens agregadas, sem nenhum registro individual.

import { $, el, esqueletoLista, vazio, corPrioridade, corSobrePrioridade } from './dom.js';
import { estado, inscrever, PESO_PRIORIDADE, rotulo } from '../state.js';

function bloco(prioridade, quantidade, total) {
    const parcela = total ? Math.round((quantidade / total) * 100) : 0;
    return el('div', { classe: 'atendido' },
        el('span', {
            classe: 'atendido__marca',
            atributos: { style: `--cor:${corPrioridade(prioridade)};--fg:${corSobrePrioridade(prioridade)}` },
            texto: rotulo(prioridade),
        }),
        el('b', { classe: 'atendido__num', texto: String(quantidade) }),
        el('span', { classe: 'atendido__pct', texto: `${parcela}%` }),
    );
}

export function montarAtendidos(container = $('#atendidos')) {
    if (!container) return () => {};

    function atualizar() {
        if (estado.carregando && !estado.resumo) {
            container.replaceChildren(esqueletoLista(4));
            return;
        }
        const porPrioridade = estado.resumo?.por_prioridade || {};
        const ordem = Object.keys(PESO_PRIORIDADE)
            .filter((p) => p in porPrioridade)
            .sort((a, b) => PESO_PRIORIDADE[a] - PESO_PRIORIDADE[b]);
        const valores = ordem.map((p) => porPrioridade[p].atendidos || 0);
        const total = valores.reduce((acc, v) => acc + v, 0);

        if (!total) {
            container.replaceChildren(vazio('Nenhum atendimento concluído no período', 'i-check'));
            return;
        }
        container.replaceChildren(
            ...ordem.map((p, i) => bloco(p, valores[i], total)),
            el('div', { classe: 'fila-status__total' },
                el('span', { texto: `Total em ${estado.resumo?.janela_horas || 24}h` }),
                el('b', { texto: String(total) })),
        );
    }

    inscrever(['resumo', 'config', 'tema'], atualizar);
    atualizar();
    return atualizar;
}

export default montarAtendidos;
