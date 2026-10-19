// Alertas operacionais: o servidor avalia as regras (services/metricas._alertas) e o
// painel apenas apresenta. Sem alertas, mostra o estado positivo de operação.

import { $, el, icone } from './dom.js';
import { estado, inscrever } from '../state.js';

function item(alerta) {
    return el('div', { classe: `alerta-item alerta-item--${alerta.nivel || 'medio'}` },
        el('span', { classe: 'alerta-item__icone' }, icone('i-alerta', 15)),
        el('div', {},
            el('strong', { texto: alerta.titulo }),
            el('p', { texto: alerta.descricao }),
        ),
    );
}

export function montarAlertas(container = $('#alertas')) {
    if (!container) return () => {};

    function atualizar() {
        const alertas = estado.resumo?.alertas || [];
        if (!alertas.length) {
            container.replaceChildren(el('div', { classe: 'alertas__vazio' },
                icone('i-check', 22, 'var(--ok)'),
                el('div', { texto: 'Nenhum alerta ativo. Fila dentro dos parâmetros avaliados pelo servidor.' })));
            return;
        }
        container.replaceChildren(...alertas.map(item));
    }

    inscrever('resumo', atualizar);
    atualizar();
    return atualizar;
}

export default montarAlertas;
