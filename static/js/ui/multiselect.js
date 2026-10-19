// Multiselect de hospitais: mantém a seleção ativa (uma ou várias unidades) e é a
// única origem do escopo usado por API, WebSocket e componentes.
//
// O painel suspenso é montado no <body> com posição fixa. Dentro do cabeçalho ele
// ficava preso ao contexto de empilhamento do header (que tem fundo e desfoque), e o
// Firefox não pintava o excesso fora da caixa — o dropdown simplesmente não abria.

import { $, el, icone } from './dom.js';
import { estado, hospitaisDemo, inscrever, selecionar } from '../state.js';

const ROTULO = 'Hospitais';

export function montarMultiselect(container = $('#seletor-hospitais')) {
    if (!container) return () => {};

    container.classList.add('multiselect');
    let aberto = false;
    let renderizado = null;

    const gatilho = el('button', {
        classe: 'multiselect__gatilho',
        atributos: { type: 'button', 'aria-expanded': 'false', 'aria-haspopup': 'true' },
    });
    const painel = el('div', {
        classe: 'multiselect__painel',
        atributos: { role: 'group', 'aria-label': `${ROTULO} monitorados` },
        oculto: true,
    });
    const lista = el('div', { classe: 'multiselect__lista', atributos: { role: 'listbox' } });
    const rodape = el('div', { classe: 'multiselect__rodape' });
    painel.append(lista, rodape);

    container.appendChild(gatilho);
    document.body.appendChild(painel);

    const acao = (rotulo, fn) => el('button', {
        classe: 'botao botao--mini',
        atributos: { type: 'button' },
        texto: rotulo,
        evento: { click: fn },
    });
    const botaoTodos = acao('Todos', () => selecionar(estado.hospitais.map((h) => h.id)));
    const botaoDemo = acao('Somente demo', () => selecionar(hospitaisDemo()));

    function nome(id) {
        return estado.hospitais.find((h) => h.id === id)?.nome || `#${id}`;
    }

    function titulo() {
        if (!estado.selecao.length) return 'Nenhum hospital';
        if (estado.selecao.length === 1) return nome(estado.selecao[0]);
        return `${estado.selecao.length} hospitais`;
    }

    function reposicionar() {
        // Em tela cheia o navegador só pinta o elemento fullscreen: o painel precisa
        // ser filho dele, não do <body>, para continuar visível.
        const dono = document.fullscreenElement || document.body;
        if (painel.parentElement !== dono) dono.appendChild(painel);
        const caixa = gatilho.getBoundingClientRect();
        const largura = Math.max(caixa.width, 260);
        painel.style.left = `${Math.max(8, Math.min(caixa.left, window.innerWidth - largura - 8))}px`;
        painel.style.top = `${caixa.bottom + 8}px`;
        painel.style.width = `${largura}px`;
        painel.style.maxHeight = `${Math.max(180, window.innerHeight - caixa.bottom - 24)}px`;
    }

    function renderGatilho() {
        gatilho.replaceChildren(
            icone('i-hospital', 16, 'var(--acento)'),
            el('span', {},
                el('span', { classe: 'multiselect__rotulo', texto: ROTULO }),
                el('span', { classe: 'multiselect__valor', texto: titulo() }),
            ),
            el('span', { classe: 'multiselect__seta' }, icone('i-seta', 16)),
        );
        gatilho.setAttribute('aria-expanded', String(aberto));
    }

    function opcao(h) {
        const entrada = el('input', {
            atributos: { type: 'checkbox' },
            evento: { change: (e) => toggle(h.id, e.target.checked) },
        });
        // Sem [for]: o rótulo já envolve o campo. Repetir a associação faz o clique
        // disparar duas vezes quando a ativação vem de script ou de tecnologia
        // assistiva, desfazendo a própria marcação.
        return el('label', { classe: 'multiselect__opcao' },
            entrada,
            el('span', { classe: 'multiselect__nome', texto: h.nome }),
            h.demo ? el('span', { classe: 'marca-demo', texto: 'DEMO' }) : null,
        );
    }

    function renderLista() {
        const chave = estado.hospitais.map((h) => `${h.id}:${h.nome}`).join('|');
        if (chave !== renderizado) {
            renderizado = chave;
            lista.replaceChildren(...(estado.hospitais.length
                ? estado.hospitais.map(opcao)
                : [el('p', { classe: 'fila-status__vazia', texto: 'Nenhum hospital neste local' })]));
            rodape.replaceChildren(botaoTodos, ...(hospitaisDemo().length ? [botaoDemo] : []));
        }
        // Marcar no lugar: reconstruir a lista a cada mudança jogaria fora o nó que o
        // usuário acabou de acionar, perdendo o foco do teclado e o ponto de rolagem.
        estado.hospitais.forEach((h, i) => {
            const entrada = lista.children[i]?.querySelector('input');
            if (entrada) entrada.checked = estado.selecao.includes(h.id);
        });
    }

    function toggle(id, ligado) {
        const proximo = ligado ? [...estado.selecao, id] : estado.selecao.filter((v) => v !== id);
        if (!proximo.length) return;         // o painel nunca fica sem escopo
        selecionar(proximo);
    }

    function abrir(sim) {
        aberto = Boolean(sim);
        painel.hidden = !aberto;
        if (aberto) { renderLista(); reposicionar(); }
        renderGatilho();
    }

    gatilho.addEventListener('click', (e) => { e.stopPropagation(); abrir(!aberto); });

    // Capture + composedPath: funciona mesmo com o clique vindo de um <label>/<svg>,
    // cujo alvo o Firefox reescreve quando há shadow DOM.
    document.addEventListener('pointerdown', (e) => {
        if (!aberto) return;
        const caminho = e.composedPath();
        if (caminho.includes(container) || caminho.includes(painel)) return;
        abrir(false);
    }, true);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') abrir(false); });
    window.addEventListener('resize', () => { if (aberto) reposicionar(); });

    function atualizar() {
        renderGatilho();
        if (aberto) { renderLista(); reposicionar(); }
    }

    inscrever(['hospitais', 'selecao'], atualizar);
    atualizar();
    return atualizar;
}

export default montarMultiselect;
