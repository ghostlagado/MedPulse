// Alternância de tema. Troca apenas o atributo de <html>: todos os componentes lêem
// as mesmas variáveis CSS, então nada precisa recarregar dados ou reabrir o socket.

import { $, el, icone } from './dom.js';
import { definirTema, estado, inscrever } from '../state.js';

function aplicar(tema) {
    document.documentElement.dataset.tema = tema;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', tema === 'claro' ? '#eef5f8' : '#04121f');
}

export function montarTema(container = $('#seletor-tema')) {
    if (!container) return () => {};

    const botao = el('button', {
        classe: 'botao botao--icone',
        atributos: { type: 'button', 'aria-pressed': String(estado.tema === 'claro') },
    });
    container.appendChild(botao);

    function pinta() {
        const claro = estado.tema === 'claro';
        botao.replaceChildren(
            icone(claro ? 'i-sol' : 'i-lua', 16),
            el('span', { classe: 'botao__texto', texto: claro ? 'Claro' : 'Escuro' }),
        );
        botao.setAttribute('aria-pressed', String(claro));
        botao.title = claro ? 'Usar tema escuro' : 'Usar tema claro';
        botao.setAttribute('aria-label', botao.title);
    }

    botao.addEventListener('click', () => definirTema(estado.tema === 'claro' ? 'escuro' : 'claro'));
    inscrever('tema', (tema) => { aplicar(tema); pinta(); });
    aplicar(estado.tema);
    pinta();
    return pinta;
}

export default montarTema;
