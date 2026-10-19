// Comparativo entre as unidades da seleção atual. Vem de resumo.por_hospital,
// calculado no servidor junto dos demais indicadores.

import { $, el, vazio } from './dom.js';
import { estado, inscrever } from '../state.js';

function linha(h) {
    const demo = estado.hospitais.find((x) => x.id === h.id)?.demo;
    return el('div', { classe: 'unidade' },
        el('span', { classe: 'unidade__nome' },
            el('b', { texto: h.nome }),
            demo ? el('span', { classe: 'marca-demo', texto: 'DEMO' }) : null),
        el('span', { classe: 'unidade__num', texto: String(h.aguardando), atributos: { title: 'aguardando' } }),
        el('span', { classe: 'unidade__num', texto: String(h.em_atendimento), atributos: { title: 'em atendimento' } }),
        el('span', { classe: 'unidade__num unidade__num--ok', texto: String(h.atendidos_24h), atributos: { title: 'atendidos no período' } }),
    );
}

export function montarHospitais(container = $('#por-hospital')) {
    if (!container) return () => {};

    function atualizar() {
        const itens = estado.resumo?.por_hospital || [];
        if (!itens.length) {
            container.replaceChildren(vazio('Nenhuma unidade na seleção atual', 'i-hospital'));
            return;
        }
        container.replaceChildren(
            el('div', { classe: 'unidade unidade--cabecalho' },
                el('span', { texto: 'Unidade' }),
                el('span', { texto: 'Fila' }),
                el('span', { texto: 'Atend.' }),
                el('span', { texto: 'Concl.' })),
            ...itens.map(linha),
        );
    }

    inscrever(['resumo', 'hospitais'], atualizar);
    atualizar();
    return atualizar;
}

export default montarHospitais;
