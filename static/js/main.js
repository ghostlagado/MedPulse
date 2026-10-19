// Ponto de entrada do painel de triagem: carrega a configuração da API, define o
// escopo de hospitais, liga o tempo real e distribui os agregados aos componentes.

import api from './api.js';
import { criarTempoReal } from './realtime.js';
import { sincronizarRelogio, definirFuso } from './relogio.js';
import {
    aplicarResumo, aplicarSnapshot, definirConfig, definirConexao, definirErro,
    definirHospitais, definirTema, estado, inscrever, iniciarSelecao, lerTemaSalvo,
    registrarEvento,
} from './state.js';
import { montarMultiselect } from './ui/multiselect.js';
import { montarTema } from './ui/tema.js';
import { montarStatus } from './ui/status.js';
import { montarKpis } from './ui/kpis.js';
import { montarFilas } from './ui/filas.js';
import { montarEspera } from './ui/espera.js';
import { montarAtendidos } from './ui/atendidos.js';
import { montarHospitais } from './ui/hospitais.js';
import { montarAlertas } from './ui/alertas.js';
import { montarGraficos } from './ui/graficos.js';

const INFO = window.MEDPULSE || {};

definirTema(lerTemaSalvo() || 'escuro');
document.documentElement.dataset.tema = estado.tema;

// 1. escopo inicial: hospitais do local já vêm renderizados pela template engine
definirHospitais(INFO.hospitais || []);
iniciarSelecao();

const tempoReal = criarTempoReal({
    onSnapshot: (snapshot) => {
        if (!snapshot) return;
        sincronizarRelogio(snapshot.emitido_em);
        aplicarSnapshot(snapshot);
    },
    onAtendimento: (atendimento) => registrarEvento(atendimento),
    onResumo: (resumo) => {
        if (resumo) {
            sincronizarRelogio(resumo.gerado_em);
            resumo.transporte = tempoReal.transporte();
        }
        aplicarResumo(resumo);
    },
    onConexao: ({ estado: nome, detalhe, transporte }) => definirConexao(nome, detalhe, transporte),
});

function sincronizar() {
    tempoReal.sincronizar();
}

// 2. componentes se inscrevem no store antes da primeira carga
montarMultiselect();
montarTema();
montarStatus();
montarKpis();
montarFilas();
montarEspera();
montarAtendidos();
montarHospitais();
montarAlertas();
montarGraficos();

// 3. vocabulário (status/prioridades/rótulos) e fuso vêm da API: o frontend não
//    duplica a máquina de estados nem inventa o próprio relógio
async function carregarConfig() {
    try {
        const config = await api.config();
        definirConfig(config);
        definirFuso(config.fuso_horario);
        sincronizarRelogio(config.agora_utc);
    } catch (e) {
        definirConexao('offline', `configuração indisponível: ${e.message}`);
    }
}

// 4. mudança de escopo: reassina o socket e traece o agregado imediatamente, para o
//    painel refletir a seleção mesmo se o tempo real estiver caindo
async function recarregar() {
    const escopo = [...estado.selecao];
    tempoReal.selecionar(escopo);
    if (!escopo.length) {
        definirErro('Selecione ao menos um hospital para monitorar.');
        return;
    }
    try {
        const resumo = await api.resumo(escopo);
        sincronizarRelogio(resumo.gerado_em);
        // O escopo anunciado na resposta é o do cálculo, não o da seleção de agora:
        // respostas de cliques anteriores podem chegar por último e o store usa isso
        // para descartar o que não pertence mais à seleção.
        aplicarSnapshot({ hospitais: resumo.hospitais, resumo, emitido_em: resumo.gerado_em });
    } catch (e) {
        estado.carregando = false;
        definirErro(e.message || 'Falha ao carregar os dados do painel.');
    }
}

inscrever('selecao', recarregar);

carregarConfig();
recarregar();
tempoReal.iniciar();

// 5. volta de aba em segundo plano: snapshot novo evita números defasados
document.addEventListener('visibilitychange', () => {
    if (!document.hidden) sincronizar();
});
