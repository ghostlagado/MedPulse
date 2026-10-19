// Gráfico de fluxo (Chart.js vendorizado). Recebe apenas números do servidor; a camada
// de visualização formata rótulos e cores, nunca recalcula indicadores. O único
// gráfico do painel é o de evolução temporal — o mix de prioridades foi removido por
// redundância com a fila por prioridade.

import { $ } from './dom.js';
import { estado, inscrever } from '../state.js';
import { horaDoBucket } from '../relogio.js';

function cor(variavel, padrao) {
    const valor = getComputedStyle(document.documentElement).getPropertyValue(variavel).trim();
    return valor || padrao;
}

// Fonte do gráfico acompanha a escala tipográfica da tela: painel de TV é lido de longe.
function corpo() {
    const base = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    return Math.max(12, Math.round(base * 0.82));
}

function tema() {
    return {
        texto: cor('--texto-2', '#9fb3c8'),
        textoFraco: cor('--texto-3', '#7c93a8'),
        linha: cor('--linha', 'rgba(255,255,255,.08)'),
        superficie: cor('--cartao', 'rgba(6,25,44,.95)'),
        borda: cor('--borda-forte', 'rgba(0,180,192,.45)'),
        chegada: cor('--serie-chegada', '#00b4c0'),
        conclusao: cor('--serie-conclusao', '#8b5cf6'),
        fila: cor('--serie-fila', '#eaf6f9'),
        corpo: corpo(),
    };
}

function baseOpcoes(t) {
    const fonte = { size: t.corpo };
    return {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
            legend: {
                display: true,
                labels: { color: t.texto, boxWidth: 12, boxHeight: 12, usePointStyle: true, font: fonte },
            },
            tooltip: {
                backgroundColor: t.superficie,
                borderColor: t.borda,
                borderWidth: 1,
                titleColor: t.texto,
                bodyColor: t.texto,
                padding: 12,
                cornerRadius: 10,
                displayColors: true,
                boxPadding: 4,
            },
        },
        scales: {
            x: {
                grid: { display: false },
                border: { display: false },
                ticks: { color: t.textoFraco, font: fonte, maxRotation: 0, autoSkipPadding: 14 },
            },
            y: {
                beginAtZero: true,
                grid: { color: t.linha },
                border: { display: false },
                ticks: { color: t.textoFraco, font: fonte, precision: 0 },
            },
        },
    };
}

function desenharFluxo(chart, serie, t) {
    if (!chart) return;
    chart.data.labels = (serie || []).map((s) => horaDoBucket(s.hora));
    chart.data.datasets = [
        {
            type: 'bar',
            label: 'Chegadas',
            data: (serie || []).map((s) => s.novos),
            backgroundColor: t.chegada,
            borderRadius: 3,
            barPercentage: 0.7,
            categoryPercentage: 0.8,
            yAxisID: 'y',
            order: 3,
        },
        {
            type: 'bar',
            label: 'Conclusões',
            data: (serie || []).map((s) => s.concluidos),
            backgroundColor: t.conclusao,
            borderRadius: 3,
            barPercentage: 0.7,
            categoryPercentage: 0.8,
            yAxisID: 'y',
            order: 2,
        },
        {
            type: 'line',
            label: 'Fila',
            data: (serie || []).map((s) => s.fila),
            borderColor: t.fila,
            backgroundColor: 'transparent',
            borderWidth: 3,
            pointRadius: 0,
            tension: 0.35,
            fill: false,
            yAxisID: 'y1',
            order: 1,
        },
    ];
    chart.options.scales.y1 = {
        position: 'right',
        beginAtZero: true,
        grid: { display: false },
        border: { display: false },
        ticks: { color: t.fila, font: { size: t.corpo }, precision: 0 },
    };
    chart.update('none');
}

export function montarGraficos() {
    if (typeof window.Chart !== 'function') return () => {};
    window.Chart.defaults.font.family = 'Inter, system-ui, -apple-system, sans-serif';

    const caixa = $('#grafico-fluxo');
    if (!caixa) return () => {};

    let t = tema();
    window.Chart.defaults.color = t.texto;
    const fluxo = new window.Chart(caixa, {
        type: 'bar',
        data: { labels: [], datasets: [] },
        options: baseOpcoes(t),
    });

    function reaplicarTema() {
        t = tema();
        window.Chart.defaults.color = t.texto;
        const opcoes = baseOpcoes(t);
        fluxo.options.plugins.legend = opcoes.plugins.legend;
        fluxo.options.plugins.tooltip = opcoes.plugins.tooltip;
        fluxo.options.scales.x.ticks.color = t.textoFraco;
        fluxo.options.scales.y.ticks.color = t.textoFraco;
        fluxo.options.scales.y.grid.color = t.linha;
        if (fluxo.options.scales.y1) {
            fluxo.options.scales.y1.ticks.color = t.fila;
            fluxo.options.scales.y1.ticks.font = { size: t.corpo };
        }
        fluxo.options.scales.x.ticks.font = { size: t.corpo };
        fluxo.options.scales.y.ticks.font = { size: t.corpo };
    }

    function atualizar() {
        if (!estado.resumo) return;
        reaplicarTema();
        desenharFluxo(fluxo, estado.resumo.serie, t);
    }

    inscrever(['resumo', 'tema'], atualizar);
    atualizar();
    return atualizar;
}

export default montarGraficos;
