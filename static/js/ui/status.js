// Barra de status: selo de conexão (online/offline), faixa de falha, relógio do
// servidor, tema parede e rodapé de sincronismo.

import { $, el, emRelacao } from './dom.js';
import { estado, inscrever } from '../state.js';
import { dataCurta, horaCurta } from '../relogio.js';

const ROTULOS = {
    online: 'Online',
    offline: 'Offline',
};

export function montarStatus() {
    const selo = $('#estado-conexao');
    const texto = $('#estado-conexao-texto');
    const faixa = $('#faixa-status');
    const faixaTexto = $('#faixa-status-texto');
    const relogio = $('#relogio');
    const rodape = $('#rodape-sincronismo');

    function pintaConexao({ conexao, detalhe = '', transporte = 'socket' }) {
        if (selo) {
            selo.dataset.estado = conexao;
            texto.textContent = ROTULOS[conexao] || conexao;
            selo.title = detalhe || '';
            selo.setAttribute('aria-label', `Conexão ${ROTULOS[conexao] || conexao}`);
        }
        if (faixa) {
            faixa.hidden = conexao !== 'offline';
            if (faixaTexto) {
                const reserva = transporte === 'polling'
                    ? ' Os números continuam chegando por consulta periódica (modo reserva).'
                    : '';
                faixaTexto.textContent = `${detalhe || 'Sem comunicação com o servidor.'} Reconexão automática em andamento.${reserva}`;
            }
        }
        pintaRodape();
    }

    function pintaRodape() {
        if (!rodape) return;
        const transporte = estado.transporte === 'polling' ? 'REST (modo reserva)' : 'WebSocket';
        rodape.textContent = estado.sincronizadoEm
            ? `sincronizado ${emRelacao(estado.sincronizadoEm)} · ${estado.contadores.eventos} evento(s) · ${transporte}`
            : 'aguardando primeiro snapshot…';
    }

    const tela = $('#botao-tela-cheia');
    if (tela) {
        const painel = $('#painel');
        const alternar = () => {
            if (document.fullscreenElement) document.exitFullscreen();
            else painel?.requestFullscreen?.().catch(() => {});
        };
        tela.addEventListener('click', alternar);
        document.addEventListener('fullscreenchange', () => {
            const cheio = Boolean(document.fullscreenElement);
            tela.setAttribute('aria-pressed', String(cheio));
            tela.title = cheio ? 'Sair do modo parede' : 'Modo parede (tela cheia)';
        });
    }

    if (relogio) {
        const [hora, data] = relogio.children;
        const anda = () => {
            hora.textContent = horaCurta();
            data.textContent = dataCurta();
        };
        anda();
        setInterval(anda, 1000);
    }

    inscrever(['conexao'], pintaConexao);
    inscrever(['meta', 'resumo'], pintaRodape);
    setInterval(pintaRodape, 20000);
    pintaConexao({ conexao: estado.conexao, detalhe: estado.detalheConexao });

    return { pintaConexao, pintaRodape };
}

export default montarStatus;
