// Distribuição do tempo de espera por faixa. Vem de resumo.tempo_na_fila, calculada
// no servidor: mostra há quanto tempo a fila espera sem expor nenhum paciente.

import { $, el, esqueletoLista, vazio } from './dom.js';
import { estado, inscrever } from '../state.js';

function linha(item, maximo) {
    const fila = item.fila || 0;
    const atendendo = item.em_atendimento || 0;
    const larguraFila = maximo ? (fila / maximo) * 100 : 0;
    const larguraAtend = maximo ? (atendendo / maximo) * 100 : 0;

    return el('div', { classe: 'espera__linha' },
        el('span', { classe: 'espera__faixa', texto: item.faixa }),
        el('div', { classe: 'espera__barra' },
            el('span', {
                classe: 'espera__trecho espera__trecho--fila',
                atributos: { style: `width:${larguraFila.toFixed(1)}%`, title: `${fila} aguardando` },
            }),
            el('span', {
                classe: 'espera__trecho espera__trecho--atend',
                atributos: { style: `width:${larguraAtend.toFixed(1)}%`, title: `${atendendo} em atendimento` },
            }),
        ),
        el('span', { classe: 'espera__num', texto: String(fila + atendendo) }),
    );
}

export function montarEspera(container = $('#espera')) {
    if (!container) return () => {};

    function atualizar() {
        if (estado.carregando && !estado.resumo) {
            container.replaceChildren(esqueletoLista(4));
            return;
        }
        const itens = estado.resumo?.tempo_na_fila || [];
        if (!itens.some((i) => (i.fila || 0) + (i.em_atendimento || 0) > 0)) {
            container.replaceChildren(vazio('Fila vazia na seleção atual', 'i-relogio'));
            return;
        }
        const maximo = Math.max(1, ...itens.map((i) => (i.fila || 0) + (i.em_atendimento || 0)));
        container.replaceChildren(
            el('div', { classe: 'espera__cabecalho' },
                el('span', { texto: 'Faixa de espera' }),
                el('span', { texto: 'Aguardando · em atendimento' }),
                el('span', { classe: 'espera__num', texto: 'Total' })),
            ...itens.map((item) => linha(item, maximo)),
        );
    }

    inscrever(['resumo', 'meta'], atualizar);
    atualizar();
    return atualizar;
}

export default montarEspera;
