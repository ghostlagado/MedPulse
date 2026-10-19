// KPIs do topo. Todos os números vêm prontos de /api/resumo (ou do snapshot do
// WebSocket) — o navegador só formata e compara a série horária já calculada.

import { $, el, esqueletoLista, minutosFmt } from './dom.js';
import { estado, inscrever } from '../state.js';

function corDaVariavel(nome) {
    return getComputedStyle(document.documentElement).getPropertyValue(nome).trim() || '#00b4c0';
}

function spark(valores, cor) {
    if (!valores || !valores.length) return null;
    const max = Math.max(...valores, 1);
    const passo = 30 / Math.max(valores.length - 1, 1);
    const pontos = valores.map((v, i) => `${(i * passo).toFixed(1)},${(18 - (v / max) * 16).toFixed(1)}`).join(' ');
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'kpi__spark');
    svg.setAttribute('width', '30');
    svg.setAttribute('height', '20');
    svg.setAttribute('viewBox', '0 0 30 20');
    svg.setAttribute('aria-hidden', 'true');
    const linha = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    linha.setAttribute('points', pontos);
    linha.setAttribute('fill', 'none');
    linha.setAttribute('stroke', cor);
    linha.setAttribute('stroke-width', '1.6');
    linha.setAttribute('stroke-linecap', 'round');
    svg.appendChild(linha);
    return svg;
}

function cartao({ rotulo, valor, unidade = '', rodape, tom = '', serie = null, corVar = '--teal-500' }) {
    const no = el('article', { classe: ['cartao', 'kpi', tom].filter(Boolean).join(' ') },
        el('span', { classe: 'kpi__rotulo', texto: rotulo }),
        el('span', { classe: 'kpi__valor' }, String(valor), unidade ? el('span', { classe: 'kpi__unidade', texto: unidade }) : null),
        el('span', { classe: 'kpi__rodape' },
            rodape?.delta !== undefined && rodape.delta !== null
                ? el('span', {
                    classe: `kpi__delta kpi__delta--${rodape.delta >= 0 ? 'sobe' : 'desce'}`,
                    texto: `${rodape.delta >= 0 ? '+' : ''}${rodape.delta}`,
                })
                : null,
            el('span', { texto: rodape?.texto ?? '' }),
        ),
    );
    const grafico = spark(serie, corDaVariavel(corVar));
    if (grafico) no.appendChild(grafico);
    return no;
}

function ultimoDelta(serie, campo) {
    if (!serie || serie.length < 2) return null;
    return serie[serie.length - 1][campo] - serie[serie.length - 2][campo];
}

function tomEspera(minutos) {
    if (minutos >= 90) return 'kpi--perigo';
    if (minutos >= 45) return 'kpi--alerta';
    return 'kpi--ok';
}

export function montarKpis(container = $('#kpis')) {
    if (!container) return () => {};

    function atualizar() {
        if (estado.carregando && !estado.resumo) {
            container.replaceChildren(esqueletoLista(3));
            return;
        }
        const r = estado.resumo;
        if (!r) return;
        const k = r.kpis;
        const serie = r.serie || [];
        const janela = r.janela_horas || 24;

        container.replaceChildren(
            cartao({
                rotulo: 'Aguardando triagem',
                valor: k.aguardando,
                tom: k.aguardando > 60 ? 'kpi--perigo' : 'kpi--alerta',
                rodape: { texto: `fila atual · ${k.total_abertos} em aberto` },
                serie: serie.map((s) => s.fila),
                corVar: '--p-intermediaria',
            }),
            cartao({
                rotulo: 'Em atendimento',
                valor: k.em_atendimento,
                rodape: { texto: `permanência média ${minutosFmt(k.permanencia_media_min)}` },
                serie: serie.map((s) => s.novos),
            }),
            cartao({
                rotulo: `Atendidos · ${janela}h`,
                valor: k.atendidos_periodo,
                tom: 'kpi--ok',
                rodape: {
                    texto: `taxa de conclusão ${k.taxa_conclusao === null ? '—' : `${k.taxa_conclusao}%`}`,
                    delta: ultimoDelta(serie, 'concluidos'),
                },
                serie: serie.map((s) => s.concluidos),
                corVar: '--p-baixa',
            }),
            cartao({
                rotulo: 'Espera média',
                valor: minutosFmt(k.espera_media_min),
                tom: tomEspera(k.espera_media_min),
                rodape: { texto: `mais antigo na fila ${minutosFmt(k.espera_max_min)}` },
            }),
            cartao({
                rotulo: 'Tempo em atendimento',
                valor: minutosFmt(k.tempo_atendido_min),
                rodape: { texto: `duração média ${minutosFmt(k.duracao_media_min)}` },
            }),
            cartao({
                rotulo: 'Projeção da fila',
                valor: k.projecao_fila_min === null ? '—' : minutosFmt(k.projecao_fila_min),
                tom: k.projecao_fila_min > 240 ? 'kpi--perigo' : '',
                rodape: { texto: `ritmo das últimas ${janela}h` },
            }),
        );
    }

    // As cores do sparkline vêm das variáveis CSS: o gráfico desenhado no SVG precisa
    // ser refeito quando o tema muda, sem tocar nos dados.
    inscrever(['resumo', 'meta'], atualizar);
    inscrever(['tema'], atualizar);
    atualizar();
    return atualizar;
}

export default montarKpis;
