// Conexão em tempo real. O Socket.IO é o transporte primário e a consulta REST é o
// plano B; o selo do painel reflete apenas o estado real do WebSocket, com duas
// possibilidades: online (canal estabelecido) ou offline (indisponível ou perdido).

const EVENTO_SNAPSHOT = 'painel:snapshot';
const EVENTO_RESUMO = 'resumo:atualizado';
const EVENTOS_ATENDIMENTO = ['atendimento:novo', 'atendimento:atualizado'];

const SONDA_MS = 7000;
const PACIENCIA_SOCKET_MS = 4500;

import api from './api.js';

export function criarTempoReal({ onSnapshot, onAtendimento, onResumo, onConexao }) {
    let socket = null;
    let hospitais = [];
    let sonda = null;
    let espera = null;
    let transporte = 'socket';

    // 'online' só quando o socket está de fato estabelecido; o resto é offline.
    function avisar(detalhe = '') {
        const online = Boolean(socket?.connected);
        onConexao({ estado: online ? 'online' : 'offline', detalhe, transporte });
    }

    function pararSonda() {
        if (!sonda) return;
        clearInterval(sonda);
        sonda = null;
    }

    async function sondar() {
        if (!hospitais.length) return;
        try {
            const dados = await api.resumo(hospitais);
            onResumo(dados);
        } catch (e) {
            avisar(e.message || 'API indisponível');
        }
    }

    function iniciarSonda(motivo) {
        if (sonda) return;
        transporte = 'polling';
        avisar(motivo);
        sondar();
        sonda = setInterval(sondar, SONDA_MS);
    }

    function assinar() {
        if (!socket?.connected || !hospitais.length) return;
        socket.emit('subscribe', { hospitais });
    }

    function conectar() {
        if (typeof window.io !== 'function') {
            iniciarSonda('cliente de tempo real não carregou');
            return;
        }

        socket = window.io({
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionDelay: 700,
            reconnectionDelayMax: 15000,
            randomizationFactor: 0.4,
            timeout: 6000,
        });

        socket.on('connect', () => {
            clearTimeout(espera);
            pararSonda();
            transporte = 'socket';
            avisar('sincronizando…');
            assinar();
        });

        socket.on('disconnect', (motivo) => {
            avisar(`conexão perdida (${motivo}); reconectando…`);
            clearTimeout(espera);
            espera = setTimeout(() => {
                if (!socket?.connected) iniciarSonda('sem tempo real no momento');
            }, PACIENCIA_SOCKET_MS);
        });

        socket.on('connect_error', () => avisar('buscando o servidor…'));
        socket.on('reconnect_failed', () => iniciarSonda('não foi possível reconectar'));

        socket.on(EVENTO_SNAPSHOT, (snapshot) => {
            pararSonda();
            transporte = 'socket';
            onSnapshot(snapshot);
            avisar();
        });

        socket.on(EVENTO_RESUMO, (resumo) => {
            onResumo(resumo);
            avisar();
        });

        for (const nome of EVENTOS_ATENDIMENTO) {
            socket.on(nome, (payload) => onAtendimento(payload?.atendimento, payload?.acao || 'atualizado'));
        }
    }

    return {
        iniciar() {
            conectar();
            clearTimeout(espera);
            espera = setTimeout(() => {
                if (!socket?.connected) iniciarSonda('estabelecendo sincronização alternativa');
            }, PACIENCIA_SOCKET_MS * 2);
        },
        selecionar(ids) {
            const proxima = [...new Set(ids.map(Number))].sort((a, b) => a - b);
            const igual = proxima.length === hospitais.length && proxima.every((v, i) => v === hospitais[i]);
            hospitais = proxima;
            if (!igual) {
                assinar();
                if (sonda) sondar();
            }
        },
        sincronizar() {
            if (socket?.connected) assinar();
            else sondar();
        },
        transporte() {
            return transporte;
        },
        online() {
            return Boolean(socket?.connected);
        },
        parar() {
            clearTimeout(espera);
            pararSonda();
            socket?.close();
            socket = null;
        },
    };
}

export default criarTempoReal;
