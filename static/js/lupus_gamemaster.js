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


// Aggiungi queste funzioni al tuo static/js/lupus_gamemaster.js o gamemaster_panel.js

// Funzione per terminare la partita
function endLupusGame() {
    showConfirmModal(
        '🛑 Terminare la partita?',
        'Questo terminerà immediatamente la partita corrente e assegnerà i punti ai vincitori. Sei sicuro?',
        () => executeEndGame(false)
    );
}

// Funzione per forzare la fine con un vincitore specifico
function forceEndLupusGame(winnerTeam) {
    const teamNames = {
        'lupi': 'Lupi 🐺',
        'cittadini': 'Cittadini 👥',
        'pareggio': 'Pareggio ⚖️'
    };

    showConfirmModal(
        `🏆 Dichiarare vittoria ${teamNames[winnerTeam]}?`,
        `Questo terminerà la partita dichiarando vincitori i ${teamNames[winnerTeam]}. I punti verranno assegnati di conseguenza.`,
        () => executeEndGame(true, winnerTeam)
    );
}

function executeEndGame(forceEnd = false, winnerTeam = null) {
    showLoading('Terminando partita...');

    const requestData = {
        force_end: forceEnd
    };

    if (winnerTeam) {
        requestData.winner_team = winnerTeam;
    }

    fetch('/api/gamemaster/lupus-end-game', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        if (data.success) {
            showGameEndModal(data);
            loadGameStatus(); // Aggiorna display
        } else {
            showNotification(data.error || 'Errore terminazione partita', 'error');
        }
    })
    .catch(error => {
        hideLoading();
        showNotification('Errore di connessione', 'error');
    });
}

// Funzione per riavviare la partita
function restartLupusGame() {
    showConfirmModal(
        '🔄 Riavviare Lupus?',
        'Vuoi riavviare una nuova partita con la stessa configurazione e gli stessi giocatori?',
        () => executeRestartGame()
    );
}

function executeRestartGame() {
    showLoading('Riavvio partita...');

    fetch('/api/gamemaster/lupus-restart', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            same_players: true,
            same_config: true
        })
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        if (data.success) {
            showNotification('🐺 Nuova partita avviata!');
            loadGameStatus();
        } else {
            showNotification(data.error || 'Errore riavvio partita', 'error');
        }
    })
    .catch(error => {
        hideLoading();
        showNotification('Errore di connessione', 'error');
    });
}

// Modal per mostrare i risultati della partita
function showGameEndModal(gameData) {
    const modal = document.createElement('div');
    modal.className = 'game-end-modal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 2000;
    `;

    const winnerEmoji = {
        'lupi': '🐺',
        'cittadini': '👥',
        'pareggio': '⚖️'
    };

    const winnerColor = {
        'lupi': '#e74c3c',
        'cittadini': '#3498db',
        'pareggio': '#f39c12'
    };

    const winner = gameData.winner_team || 'pareggio';

    modal.innerHTML = `
        <div style="background: white; border-radius: 20px; padding: 30px; max-width: 600px; width: 90%; max-height: 80vh; overflow-y: auto;">
            <div style="text-align: center; margin-bottom: 30px;">
                <div style="font-size: 4em; margin-bottom: 10px;">${winnerEmoji[winner]}</div>
                <h2 style="color: ${winnerColor[winner]}; margin: 0;">
                    ${winner === 'pareggio' ? 'Partita Terminata' : `Vittoria ${winner.charAt(0).toUpperCase() + winner.slice(1)}!`}
                </h2>
                <p style="color: #666; margin: 10px 0;">${gameData.message}</p>
            </div>

            ${gameData.punteggi && gameData.punteggi.length > 0 ? `
                <div style="margin-bottom: 30px;">
                    <h3 style="color: #333; margin-bottom: 20px; text-align: center;">🏆 Punteggi Assegnati</h3>
                    <div style="max-height: 300px; overflow-y: auto;">
                        ${gameData.punteggi.map(p => `
                            <div style="display: flex; justify-content: space-between; align-items: center; padding: 15px; margin-bottom: 10px; background: ${p.team === winner ? '#e8f5e8' : '#f8f9fa'}; border-radius: 10px; border-left: 4px solid ${getTeamColor(p.team)};">
                                <div>
                                    <div style="font-weight: bold; color: #333;">${p.nome}</div>
                                    <div style="font-size: 0.9em; color: #666;">${p.ruolo} (${p.team})</div>
                                    ${p.dettaglio ? `<div style="font-size: 0.8em; color: #888; margin-top: 5px;">${p.dettaglio.join(', ')}</div>` : ''}
                                </div>
                                <div style="font-size: 1.5em; font-weight: bold; color: ${getTeamColor(p.team)};">
                                    +${p.punti}
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            ` : ''}

            <div style="display: flex; gap: 15px; justify-content: center;">
                <button onclick="restartLupusGame(); closeGameEndModal();" style="background: #27ae60; color: white; border: none; padding: 12px 24px; border-radius: 10px; font-weight: bold; cursor: pointer;">
                    🔄 Nuova Partita
                </button>
                <button onclick="closeGameEndModal();" style="background: #95a5a6; color: white; border: none; padding: 12px 24px; border-radius: 10px; font-weight: bold; cursor: pointer;">
                    ✅ Chiudi
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    // Chiudi cliccando fuori
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeGameEndModal();
        }
    });
}

function closeGameEndModal() {
    const modal = document.querySelector('.game-end-modal');
    if (modal) {
        modal.remove();
    }
}

// Funzione per mostrare controlli di fine partita avanzati
function showAdvancedEndControls() {
    const modal = document.createElement('div');
    modal.className = 'advanced-end-modal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 2000;
    `;

    modal.innerHTML = `
        <div style="background: white; border-radius: 20px; padding: 30px; max-width: 500px; width: 90%;">
            <h3 style="color: #333; margin-bottom: 20px; text-align: center;">🎮 Opzioni Fine Partita</h3>

            <div style="margin-bottom: 20px;">
                <p style="color: #666; text-align: center; margin-bottom: 20px;">
                    Scegli come terminare la partita:
                </p>

                <div style="display: flex; flex-direction: column; gap: 15px;">
                    <button onclick="executeEndGame(false); closeAdvancedEndModal();"
                            style="background: #3498db; color: white; border: none; padding: 15px; border-radius: 10px; font-weight: bold; cursor: pointer;">
                        🏁 Fine Naturale
                        <div style="font-size: 0.8em; font-weight: normal; margin-top: 5px;">
                            Termina seguendo le regole (controlla vincitore automaticamente)
                        </div>
                    </button>

                    <button onclick="forceEndLupusGame('lupi'); closeAdvancedEndModal();"
                            style="background: #e74c3c; color: white; border: none; padding: 15px; border-radius: 10px; font-weight: bold; cursor: pointer;">
                        🐺 Vittoria Lupi
                        <div style="font-size: 0.8em; font-weight: normal; margin-top: 5px;">
                            Dichiara vincitori i lupi
                        </div>
                    </button>

                    <button onclick="forceEndLupusGame('cittadini'); closeAdvancedEndModal();"
                            style="background: #3498db; color: white; border: none; padding: 15px; border-radius: 10px; font-weight: bold; cursor: pointer;">
                        👥 Vittoria Cittadini
                        <div style="font-size: 0.8em; font-weight: normal; margin-top: 5px;">
                            Dichiara vincitori i cittadini
                        </div>
                    </button>

                    <button onclick="forceEndLupusGame('pareggio'); closeAdvancedEndModal();"
                            style="background: #f39c12; color: white; border: none; padding: 15px; border-radius: 10px; font-weight: bold; cursor: pointer;">
                        ⚖️ Pareggio
                        <div style="font-size: 0.8em; font-weight: normal; margin-top: 5px;">
                            Termina senza vincitori (punti minimi)
                        </div>
                    </button>
                </div>
            </div>

            <div style="text-align: center;">
                <button onclick="closeAdvancedEndModal();"
                        style="background: #95a5a6; color: white; border: none; padding: 10px 20px; border-radius: 10px; cursor: pointer;">
                    Annulla
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
}

function closeAdvancedEndModal() {
    const modal = document.querySelector('.advanced-end-modal');
    if (modal) {
        modal.remove();
    }
}

// Aggiorna i controlli di fase per includere opzioni avanzate
function updatePhaseControls(gameData) {
    const phaseControlsSection = document.getElementById('phase-controls-section');

    if (!gameData.game_active) {
        phaseControlsSection.style.display = 'none';
        return;
    }

    phaseControlsSection.style.display = 'block';

    // Aggiungi pulsante per controlli avanzati se non esiste
    if (!document.getElementById('advanced-end-btn')) {
        const advancedBtn = document.createElement('button');
        advancedBtn.id = 'advanced-end-btn';
        advancedBtn.className = 'btn';
        advancedBtn.style.cssText = 'background: #9b59b6; color: white; margin-top: 10px; width: 100%;';
        advancedBtn.innerHTML = '⚙️ Opzioni Avanzate';
        advancedBtn.onclick = showAdvancedEndControls;

        // Inserisci prima del pulsante termina partita esistente
        const terminaBtn = phaseControlsSection.querySelector('button[onclick*="endLupusGame"]');
        if (terminaBtn) {
            terminaBtn.parentNode.insertBefore(advancedBtn, terminaBtn);
        }
    }
}

// Funzione per ottenere il colore del team
function getTeamColor(team) {
    const colors = {
        'lupi': '#e74c3c',
        'cittadini': '#3498db',
        'neutral': '#f39c12'
    };
    return colors[team] || '#95a5a6';
}

// Modifica la funzione di aggiornamento display esistente
function updateGameDisplay(data) {
    // ... codice esistente ...

    // Aggiungi controlli avanzati
    updatePhaseControls(data);

    // Se la partita è terminata, mostra pulsante per riavviare
    if (data.game_active && data.fase_corrente === 'ended') {
        showRestartButton();
    }
}

function showRestartButton() {
    const setupSection = document.getElementById('setup-section');
    if (setupSection && !document.getElementById('restart-section')) {
        const restartSection = document.createElement('div');
        restartSection.id = 'restart-section';
        restartSection.className = 'controls-section';
        restartSection.innerHTML = `
            <h3>🔄 Partita Terminata</h3>
            <button class="btn btn-success" onclick="restartLupusGame()" style="width: 100%; margin-bottom: 10px;">
                🚀 Riavvia Lupus
            </button>
            <button class="btn btn-secondary" onclick="location.reload()" style="width: 100%;">
                🏠 Torna al Menu
            </button>
        `;
        setupSection.parentNode.insertBefore(restartSection, setupSection);
        setupSection.style.display = 'none';
    }
}

// Funzione per mostrare statistiche dettagliate della partita
function showGameSummary(partitaId) {
    fetch(`/api/gamemaster/lupus-game-summary/${partitaId}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showNotification(data.error, 'error');
                return;
            }

            const modal = document.createElement('div');
            modal.className = 'game-summary-modal';
            modal.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.8);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 2000;
            `;

            modal.innerHTML = `
                <div style="background: white; border-radius: 20px; padding: 30px; max-width: 800px; width: 90%; max-height: 80vh; overflow-y: auto;">
                    <h2 style="color: #333; margin-bottom: 20px; text-align: center;">📊 Riassunto Partita #${data.partita.id}</h2>

                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px;">
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 10px; text-align: center;">
                            <div style="font-size: 1.5em; font-weight: bold; color: #333;">${data.partita.vincitore || 'Pareggio'}</div>
                            <div style="color: #666;">Vincitore</div>
                        </div>
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 10px; text-align: center;">
                            <div style="font-size: 1.5em; font-weight: bold; color: #333;">${data.partita.turni_totali}</div>
                            <div style="color: #666;">Turni</div>
                        </div>
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 10px; text-align: center;">
                            <div style="font-size: 1.5em; font-weight: bold; color: #333;">${data.partita.durata_minuti}m</div>
                            <div style="color: #666;">Durata</div>
                        </div>
                    </div>

                    <h3 style="color: #333; margin-bottom: 15px;">👥 Giocatori</h3>
                    <div style="margin-bottom: 30px; max-height: 300px; overflow-y: auto;">
                        ${data.giocatori.map(g => `
                            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px; margin-bottom: 5px; background: ${g.era_bot ? '#fff3cd' : '#f8f9fa'}; border-radius: 8px; border-left: 4px solid ${getTeamColor(g.team)};">
                                <div>
                                    <span style="font-weight: bold;">${g.era_bot ? '🤖 ' : ''}${g.nome}</span>
                                    <span style="color: #666; margin-left: 10px;">${g.ruolo}</span>
                                </div>
                                <div style="text-align: right;">
                                    <div style="font-weight: bold; color: ${g.punti_ottenuti > 0 ? '#27ae60' : '#95a5a6'};">
                                        ${g.punti_ottenuti > 0 ? '+' : ''}${g.punti_ottenuti} pt
                                    </div>
                                    <div style="font-size: 0.8em; color: #666;">
                                        ${g.stato_finale}${g.morte_turno ? ` (T${g.morte_turno})` : ''}
                                    </div>
                                </div>
                            </div>
                        `).join('')}
                    </div>

                    <div style="text-align: center;">
                        <button onclick="this.parentElement.parentElement.parentElement.remove();"
                                style="background: #3498db; color: white; border: none; padding: 12px 24px; border-radius: 10px; font-weight: bold; cursor: pointer;">
                            ✅ Chiudi
                        </button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);
        })
        .catch(error => {
            showNotification('Errore caricamento riassunto', 'error');
        });
}

// Aggiungi event listener per aggiornamenti automatici
document.addEventListener('DOMContentLoaded', function() {
    // Aggiorna ogni 5 secondi se siamo nella pagina gamemaster
    if (window.location.pathname.includes('gamemaster') || window.location.pathname.includes('lupus')) {
        setInterval(() => {
            if (document.querySelector('#lupus-tab, .lupus-controls')) {
                loadGameStatus();
            }
        }, 5000);
    }
});