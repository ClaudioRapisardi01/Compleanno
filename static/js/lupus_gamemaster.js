// Salva questo file come static/js/lupus_gamemaster.js

let gameData = null;
let refreshInterval = null;
let pendingAction = null;
let configurations = [];

// Inizializzazione
window.onload = function() {
    loadConfigurations();
    loadGameStatus();
    startPeriodicUpdates();
};

// Carica configurazioni disponibili
function loadConfigurations() {
    fetch('/api/gamemaster/lupus-configs')
        .then(response => response.json())
        .then(data => {
            configurations = data;
            updateConfigSelector(data);
        })
        .catch(error => {
            console.error('Errore caricamento configurazioni:', error);
            showNotification('Errore caricamento configurazioni', 'error');
        });
}

function updateConfigSelector(configs) {
    const selector = document.getElementById('config-selector');
    selector.innerHTML = '<option value="">Seleziona configurazione...</option>';

    configs.forEach(config => {
        const option = document.createElement('option');
        option.value = config.id;
        option.textContent = `${config.nome} (${config.min_giocatori}-${config.max_giocatori} giocatori)`;
        selector.appendChild(option);
    });
}

// Avvia nuova partita
function startLupusGame() {
    const configId = document.getElementById('config-selector').value;

    if (!configId) {
        showNotification('Seleziona una configurazione', 'error');
        return;
    }

    showConfirmModal(
        'Avviare una nuova partita di Lupus in Fabula? Questo terminerà eventuali partite in corso.',
        () => executeStartGame(configId)
    );
}

function executeStartGame(configId) {
    showLoading('Avvio partita...');

    fetch('/api/gamemaster/lupus-start', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ config_id: parseInt(configId) })
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        if (data.success) {
            showNotification(`🐺 Partita avviata! ${data.giocatori_assegnati} giocatori pronti`);
            loadGameStatus();
        } else {
            showNotification(data.error || 'Errore avvio partita', 'error');
        }
    })
    .catch(error => {
        hideLoading();
        showNotification('Errore di connessione', 'error');
    });
}

// Carica stato della partita
function loadGameStatus() {
    fetch('/api/gamemaster/lupus-status')
        .then(response => response.json())
        .then(data => {
            gameData = data;
            updateGameDisplay(data);
        })
        .catch(error => {
            console.error('Errore caricamento stato:', error);
        });
}

function updateGameDisplay(data) {
    const statusEl = document.getElementById('game-status');
    const setupSection = document.getElementById('setup-section');
    const phaseControlsSection = document.getElementById('phase-controls-section');

    if (!data.game_active) {
        // Nessuna partita attiva
        statusEl.className = 'game-status waiting';
        document.getElementById('status-title').textContent = '⏳ Nessuna partita attiva';
        document.getElementById('status-description').textContent = 'Avvia una nuova partita per iniziare';

        setupSection.style.display = 'block';
        phaseControlsSection.style.display = 'none';

        resetDisplayValues();
        updatePlayersList([]);
        updateEventsList([]);
        return;
    }

    // Partita attiva
    statusEl.className = 'game-status active';
    setupSection.style.display = 'none';
    phaseControlsSection.style.display = 'block';

    // Aggiorna status
    const phaseNames = {
        'setup': '⚙️ Preparazione',
        'night': '🌙 Notte',
        'day': '☀️ Giorno',
        'voting': '🗳️ Votazione',
        'ended': '🏁 Terminata'
    };

    document.getElementById('status-title').textContent = phaseNames[data.fase_corrente] || data.fase_corrente;
    document.getElementById('status-description').textContent = `Turno ${data.turno} - ${data.partecipanti.length} giocatori`;

    // Aggiorna valori
    document.getElementById('total-players').textContent = data.partecipanti.length;
    document.getElementById('alive-players').textContent = data.partecipanti.filter(p => p.stato === 'vivo').length;
    document.getElementById('wolves-count').textContent = data.vivi_lupi;
    document.getElementById('citizens-count').textContent = data.vivi_cittadini;
    document.getElementById('current-turn').textContent = data.turno;
    document.getElementById('current-phase').textContent = phaseNames[data.fase_corrente] || data.fase_corrente;

    // Aggiorna timer
    updateTimer(data.tempo_rimanente, data.fase_corrente);

    // Aggiorna bottoni fase
    updatePhaseButtons(data.fase_corrente);

    // Aggiorna lista giocatori
    updatePlayersList(data.partecipanti);

    // Aggiorna condizioni vittoria
    updateWinConditions(data.vivi_lupi, data.vivi_cittadini);

    // Carica eventi
    loadGameEvents();
}

function resetDisplayValues() {
    document.getElementById('total-players').textContent = '0';
    document.getElementById('alive-players').textContent = '0';
    document.getElementById('wolves-count').textContent = '0';
    document.getElementById('citizens-count').textContent = '0';
    document.getElementById('current-turn').textContent = '0';
    document.getElementById('current-phase').textContent = 'Setup';
    document.getElementById('timer').textContent = '🐺 --:--';
}

function updateTimer(timeRemaining, phase) {
    const timer = document.getElementById('timer');

    if (!timeRemaining) {
        timer.textContent = '🐺 --:--';
        timer.className = 'timer-display';
        return;
    }

    const minutes = Math.floor(timeRemaining / 60);
    const seconds = Math.floor(timeRemaining % 60);
    const timeStr = `${minutes}:${seconds.toString().padStart(2, '0')}`;

    const phaseEmoji = {
        'night': '🌙',
        'day': '☀️',
        'voting': '🗳️',
        'setup': '⚙️'
    }[phase] || '🐺';

    timer.textContent = `${phaseEmoji} ${timeStr}`;

    // Cambia colore in base al tempo
    if (timeRemaining <= 10) {
        timer.className = 'timer-display danger';
    } else if (timeRemaining <= 30) {
        timer.className = 'timer-display warning';
    } else {
        timer.className = 'timer-display';
    }
}

function updatePhaseButtons(currentPhase) {
    // Reset tutti i bottoni
    document.querySelectorAll('.phase-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Attiva bottone fase corrente
    const currentBtn = document.getElementById(`btn-${currentPhase}`);
    if (currentBtn) {
        currentBtn.classList.add('active');
    }
}

function updatePlayersList(players) {
    const list = document.getElementById('players-list');
    list.innerHTML = '';

    if (players.length === 0) {
        list.innerHTML = `
            <div style="text-align: center; opacity: 0.7; padding: 40px;">
                <h4>🎭 Nessuna partita attiva</h4>
                <p>I giocatori appariranno qui una volta avviata la partita</p>
            </div>
        `;
        return;
    }

    players.forEach(player => {
        const card = document.createElement('div');
        card.className = `player-card team-${player.team}`;

        if (player.stato !== 'vivo') {
            card.classList.add('dead');
        }

        const photoHtml = player.foto_profilo ?
            `<img src="/static/uploads/${player.foto_profilo}" alt="${player.nome}">` :
            `<span>${player.nome.charAt(0)}</span>`;

        const statusClass = {
            'vivo': 'status-alive',
            'morto': 'status-dead',
            'eliminato': 'status-eliminated'
        }[player.stato] || 'status-alive';

        const statusText = {
            'vivo': 'Vivo',
            'morto': 'Morto',
            'eliminato': 'Eliminato'
        }[player.stato] || 'Sconosciuto';

        card.innerHTML = `
            <div class="player-status ${statusClass}">${statusText}</div>
            <div class="player-header">
                <div class="player-photo">${photoHtml}</div>
                <div class="player-info">
                    <div class="player-name">${player.emoji} ${player.nome}</div>
                    <div class="player-role">${player.ruolo} | Team: ${player.team}</div>
                    ${player.morte_turno ? `<div style="font-size: 0.8em; opacity: 0.7;">Morto al turno ${player.morte_turno}</div>` : ''}
                </div>
            </div>
            <div class="player-actions">
                <button class="action-btn btn-info" onclick="showPlayerDetails(${player.id}, '${player.nome}')">
                    ℹ️ Dettagli
                </button>
                ${player.stato === 'vivo' ?
                    `<button class="action-btn btn-kill" onclick="killPlayer(${player.id}, '${player.nome}')">
                        💀 Elimina
                    </button>` :
                    `<button class="action-btn btn-revive" onclick="revivePlayer(${player.id}, '${player.nome}')">
                        💚 Rivivi
                    </button>`
                }
            </div>
        `;

        list.appendChild(card);
    });
}

function updateWinConditions(wolvesAlive, citizensAlive) {
    const wolfCondition = document.getElementById('wolf-condition');
    const citizenCondition = document.getElementById('citizen-condition');

    // Condizione vittoria lupi: lupi >= cittadini
    if (wolvesAlive >= citizensAlive && wolvesAlive > 0) {
        wolfCondition.textContent = '✅';
        wolfCondition.style.color = '#e74c3c';
    } else {
        wolfCondition.textContent = '❌';
        wolfCondition.style.color = '#95a5a6';
    }

    // Condizione vittoria cittadini: nessun lupo vivo
    if (wolvesAlive === 0) {
        citizenCondition.textContent = '✅';
        citizenCondition.style.color = '#3498db';
    } else {
        citizenCondition.textContent = '❌';
        citizenCondition.style.color = '#95a5a6';
    }
}

// Gestione fasi
function changePhase(newPhase) {
    if (!gameData || !gameData.game_active) {
        showNotification('Nessuna partita attiva', 'error');
        return;
    }

    const phaseNames = {
        'night': 'Notte',
        'day': 'Giorno',
        'voting': 'Votazione'
    };

    showConfirmModal(
        `Passare alla fase: ${phaseNames[newPhase]}?`,
        () => executePhaseChange(newPhase)
    );
}

function executePhaseChange(newPhase) {
    showLoading('Cambio fase...');

    fetch('/api/gamemaster/lupus-phase', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ phase: newPhase })
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        if (data.success) {
            showNotification(`✅ Fase cambiata: ${data.new_phase}`);
            loadGameStatus();
        } else {
            showNotification(data.error || 'Errore cambio fase', 'error');
        }
    })
    .catch(error => {
        hideLoading();
        showNotification('Errore di connessione', 'error');
    });
}

// Azioni rapide
function skipToVoting() {
    changePhase('voting');
}

function extendTime() {
    if (!gameData || !gameData.game_active) {
        showNotification('Nessuna partita attiva', 'error');
        return;
    }

    fetch('/api/gamemaster/lupus-advanced-action', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            type: 'extend_time',
            partita_id: gameData.partita_id
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('⏰ Tempo esteso di 30 secondi');
            loadGameStatus();
        } else {
            showNotification(data.error || 'Errore estensione tempo', 'error');
        }
    })
    .catch(error => {
        showNotification('Errore di connessione', 'error');
    });
}

function showActions() {
    if (!gameData || !gameData.game_active) {
        showNotification('Nessuna partita attiva', 'error');
        return;
    }

    // Carica e mostra azioni del turno corrente
    fetch(`/api/gamemaster/lupus-actions/${gameData.partita_id}/${gameData.turno}`)
        .then(response => response.json())
        .then(data => {
            displayActionsModal(data);
        })
        .catch(error => {
            showNotification('Errore caricamento azioni', 'error');
        });
}

function showVotes() {
    if (!gameData || !gameData.game_active) {
        showNotification('Nessuna partita attiva', 'error');
        return;
    }

    // Carica e mostra voti del turno corrente
    fetch(`/api/gamemaster/lupus-votes/${gameData.partita_id}/${gameData.turno}`)
        .then(response => response.json())
        .then(data => {
            displayVotesModal(data);
        })
        .catch(error => {
            showNotification('Errore caricamento voti', 'error');
        });
}

function endGame() {
    showConfirmModal(
        'Terminare la partita corrente? Questa azione non può essere annullata.',
        () => executeEndGame()
    );
}

function executeEndGame() {
    showLoading('Terminazione partita...');

    fetch('/api/gamemaster/lupus-phase', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ phase: 'ended' })
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        if (data.success) {
            showNotification('🏁 Partita terminata');
            loadGameStatus();
        } else {
            showNotification(data.error || 'Errore terminazione', 'error');
        }
    })
    .catch(error => {
        hideLoading();
        showNotification('Errore di connessione', 'error');
    });
}

// Azioni sui giocatori
function showPlayerDetails(playerId, playerName) {
    // Mostra dettagli giocatore in modal
    const player = gameData.partecipanti.find(p => p.id === playerId);
    if (!player) {
        showNotification('Giocatore non trovato', 'error');
        return;
    }

    const modal = document.getElementById('actions-modal');
    const title = document.getElementById('modal-title');
    const content = document.getElementById('modal-content');

    title.textContent = `Dettagli - ${playerName}`;

    content.innerHTML = `
        <div style="display: grid; gap: 15px;">
            <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 10px;">
                <h4>Informazioni Base</h4>
                <p><strong>Nome:</strong> ${player.nome}</p>
                <p><strong>Ruolo:</strong> ${player.ruolo}</p>
                <p><strong>Team:</strong> ${player.team}</p>
                <p><strong>Stato:</strong> ${player.stato}</p>
                ${player.morte_turno ? `<p><strong>Morto al turno:</strong> ${player.morte_turno}</p>` : ''}
            </div>
            ${player.abilita_speciali ? `
                <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 10px;">
                    <h4>Abilità Speciali</h4>
                    <p>${JSON.stringify(player.abilita_speciali, null, 2)}</p>
                </div>
            ` : ''}
        </div>
    `;

    modal.style.display = 'block';
}

function killPlayer(playerId, playerName) {
    showConfirmModal(
        `Eliminare ${playerName} dalla partita?`,
        () => executePlayerAction(playerId, 'kill')
    );
}

function revivePlayer(playerId, playerName) {
    showConfirmModal(
        `Riportare in vita ${playerName}?`,
        () => executePlayerAction(playerId, 'revive')
    );
}

function executePlayerAction(playerId, action) {
    showLoading('Elaborazione...');

    fetch('/api/gamemaster/lupus-player-action', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            player_id: playerId,
            action: action
        })
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        if (data.success) {
            showNotification(`✅ ${data.message}`);
            loadGameStatus();
        } else {
            showNotification(data.error || 'Errore azione', 'error');
        }
    })
    .catch(error => {
        hideLoading();
        showNotification('Errore di connessione', 'error');
    });
}

// Log eventi
function loadGameEvents() {
    if (!gameData || !gameData.game_active) {
        updateEventsList([]);
        return;
    }

    fetch(`/api/gamemaster/lupus-events/${gameData.partita_id}`)
        .then(response => response.json())
        .then(data => {
            updateEventsList(data);
        })
        .catch(error => {
            console.error('Errore caricamento eventi:', error);
        });
}

function updateEventsList(events) {
    const list = document.getElementById('events-list');
    list.innerHTML = '';

    if (events.length === 0) {
        list.innerHTML = `
            <div class="event-item">
                <span class="event-time">--:--</span>
                <span class="event-description">Nessun evento da mostrare</span>
            </div>
        `;
        return;
    }

    events.slice(-10).reverse().forEach(event => {
        const item = document.createElement('div');
        item.className = 'event-item';

        const time = new Date(event.timestamp).toLocaleTimeString('it-IT', {
            hour: '2-digit',
            minute: '2-digit'
        });

        item.innerHTML = `
            <span class="event-time">${time}</span>
            <span class="event-description">${event.descrizione}</span>
        `;

        list.appendChild(item);
    });
}

// Modals
function displayActionsModal(actions) {
    const modal = document.getElementById('actions-modal');
    const title = document.getElementById('modal-title');
    const content = document.getElementById('modal-content');

    title.textContent = `Azioni Turno ${gameData.turno}`;

    if (actions.length === 0) {
        content.innerHTML = '<p>Nessuna azione registrata per questo turno.</p>';
    } else {
        let html = '<div style="display: grid; gap: 10px;">';
        actions.forEach(action => {
            html += `
                <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 10px;">
                    <strong>${action.giocatore_nome}</strong> (${action.ruolo})
                    <br>Azione: ${action.tipo_azione}
                    ${action.target_nome ? `<br>Target: ${action.target_nome}` : ''}
                    ${action.risultato ? `<br>Risultato: ${action.risultato}` : ''}
                    <br><span style="color: ${action.successo ? '#27ae60' : '#e74c3c'};">
                        ${action.successo ? '✅ Successo' : '❌ Fallito'}
                    </span>
                </div>
            `;
        });
        html += '</div>';
        content.innerHTML = html;
    }

    modal.style.display = 'block';
}

function displayVotesModal(votes) {
    const modal = document.getElementById('actions-modal');
    const title = document.getElementById('modal-title');
    const content = document.getElementById('modal-content');

    title.textContent = `Voti Turno ${gameData.turno}`;

    if (votes.length === 0) {
        content.innerHTML = '<p>Nessun voto registrato per questo turno.</p>';
    } else {
        let html = '<div style="display: grid; gap: 10px;">';
        const voteCount = {};

        votes.forEach(vote => {
            if (!voteCount[vote.votato_nome]) {
                voteCount[vote.votato_nome] = 0;
            }
            voteCount[vote.votato_nome] += vote.peso_voto;

            html += `
                <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 10px;">
                    <strong>${vote.votante_nome}</strong> vota <strong>${vote.votato_nome}</strong>
                    ${vote.peso_voto > 1 ? ` (peso: ${vote.peso_voto})` : ''}
                </div>
            `;
        });

        html += '<hr style="margin: 20px 0; border-color: rgba(255,255,255,0.3);"><h4>Risultati:</h4>';
        Object.entries(voteCount).sort((a, b) => b[1] - a[1]).forEach(([nome, voti]) => {
            html += `
                <div style="background: rgba(243,156,18,0.2); padding: 10px; border-radius: 8px;">
                    <strong>${nome}</strong>: ${voti} voti
                </div>
            `;
        });

        html += '</div>';
        content.innerHTML = html;
    }

    modal.style.display = 'block';
}

function showConfirmModal(message, onConfirm) {
    document.getElementById('confirm-message').textContent = message;
    pendingAction = onConfirm;
    document.getElementById('confirm-modal').style.display = 'block';
}

function confirmAction() {
    if (pendingAction) {
        pendingAction();
        pendingAction = null;
    }
    closeModal('confirm-modal');
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

// Utility functions
function resetGame() {
    showConfirmModal(
        'Reset completo della partita? Tutti i dati verranno persi.',
        () => {
            fetch('/api/gamemaster/lupus-advanced-action', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    type: 'reset_game',
                    partita_id: gameData?.partita_id
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showNotification('🔄 Partita resettata');
                    loadGameStatus();
                } else {
                    showNotification('Funzione reset in sviluppo', 'info');
                }
            })
            .catch(error => {
                showNotification('Funzione reset in sviluppo', 'info');
            });
        }
    );
}

function exportGameLog() {
    if (!gameData || !gameData.game_active) {
        showNotification('Nessuna partita attiva da esportare', 'error');
        return;
    }

    // Genera log completo della partita
    const logData = {
        partita_id: gameData.partita_id,
        data_esportazione: new Date().toISOString(),
        stato_partita: gameData,
        giocatori: gameData.partecipanti
    };

    const dataStr = JSON.stringify(logData, null, 2);
    const dataBlob = new Blob([dataStr], {type: 'application/json'});

    const link = document.createElement('a');
    link.href = URL.createObjectURL(dataBlob);
    link.download = `lupus_log_${gameData.partita_id}_${new Date().toISOString().split('T')[0]}.json`;
    link.click();

    showNotification('📋 Log esportato!');
}

let loadingElement = null;

function showLoading(message = 'Caricamento...') {
    hideLoading(); // Rimuovi eventuali loading precedenti

    loadingElement = document.createElement('div');
    loadingElement.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.8);
        color: white;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        z-index: 2000;
        font-size: 1.2em;
    `;

    loadingElement.innerHTML = `
        <div style="text-align: center;">
            <div style="border: 4px solid rgba(255,255,255,0.3); border-top: 4px solid #ffd700; border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; margin-bottom: 20px;"></div>
            <div>${message}</div>
        </div>
        <style>
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        </style>
    `;

    document.body.appendChild(loadingElement);
}

function hideLoading() {
    if (loadingElement && document.body.contains(loadingElement)) {
        document.body.removeChild(loadingElement);
        loadingElement = null;
    }
}

function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        padding: 15px 25px;
        border-radius: 10px;
        color: white;
        font-weight: bold;
        z-index: 1001;
        background: ${type === 'error' ? '#e74c3c' : type === 'info' ? '#3498db' : '#27ae60'};
        box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        max-width: 90%;
        text-align: center;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        if (document.body.contains(notification)) {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(-50%) translateY(-20px)';
            setTimeout(() => {
                if (document.body.contains(notification)) {
                    document.body.removeChild(notification);
                }
            }, 300);
        }
    }, 4000);
}

// Aggiornamenti periodici
function startPeriodicUpdates() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
    refreshInterval = setInterval(() => {
        loadGameStatus();
    }, 3000); // Ogni 3 secondi
}

// Gestione visibilità pagina
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        if (refreshInterval) {
            clearInterval(refreshInterval);
        }
    } else {
        startPeriodicUpdates();
        loadGameStatus();
    }
});

// Cleanup
window.addEventListener('beforeunload', function() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
});

// Chiudi modal cliccando fuori
window.onclick = function(event) {
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    });
}

// Gestione tastiera per modal
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => {
            if (modal.style.display === 'block') {
                modal.style.display = 'none';
            }
        });
    }
});

// Funzioni aggiuntive per gestione avanzata
function pauseGame() {
    if (!gameData || !gameData.game_active) {
        showNotification('Nessuna partita attiva', 'error');
        return;
    }

    fetch('/api/gamemaster/lupus-advanced-action', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            type: 'pause_game',
            partita_id: gameData.partita_id
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('⏸️ Partita messa in pausa');
            loadGameStatus();
        } else {
            showNotification(data.error || 'Errore pausa', 'error');
        }
    })
    .catch(error => {
        showNotification('Errore di connessione', 'error');
    });
}

function resumeGame() {
    if (!gameData) {
        showNotification('Nessuna partita da riprendere', 'error');
        return;
    }

    fetch('/api/gamemaster/lupus-advanced-action', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            type: 'resume_game',
            partita_id: gameData.partita_id
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('▶️ Partita ripresa');
            loadGameStatus();
        } else {
            showNotification(data.error || 'Errore ripresa', 'error');
        }
    })
    .catch(error => {
        showNotification('Errore di connessione', 'error');
    });
}

// Debug functions per sviluppo
function debugGameState() {
    console.log('Game Data:', gameData);
    console.log('Configurations:', configurations);
}

// Inizializza tooltips e altri elementi UI se necessario
function initializeUI() {
    // Aggiungi eventuali inizializzazioni UI aggiuntive
    console.log('Lupus Gamemaster UI inizializzato');
}