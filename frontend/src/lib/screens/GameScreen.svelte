<script>
  import { onMount, onDestroy } from 'svelte';
  import { Chess } from 'chess.js';
  import ChessBoard from '../components/ChessBoard.svelte';
  import AnnotationPanel from '../components/AnnotationPanel.svelte';
  import { navigateTo, openModal } from '../stores/app.js';
  import {
    gameState,
    gameId,
    settings,
    connectionStatus,
    websocket,
    selectedSquare,
    legalMovesForSelected,
    lastMove,
    isPlayerTurn,
    resetGame,
    updateGameState,
  } from '../stores/game.js';
  import {
    arrows,
    highlights,
    annotationsEnabled,
    annotationColor,
    toggleArrow,
    toggleHighlight,
  } from '../stores/annotations.js';

  // Local state
  let messages = [];
  let chatInput = '';
  let isThinking = false;
  let chess = new Chess();
  let currentAudio = null;
  let ws = null;
  let reconnectTimer = null;

  // Get the current state values
  $: orientation = $gameState.playerColor;
  $: fen = $gameState.fen;
  $: turnText = $gameState.turn === 'white' ? 'White to move' : 'Black to move';
  $: isMyTurn = $isPlayerTurn;

  // Sync chess.js with FEN
  $: {
    try {
      chess.load(fen);
    } catch (e) {
      console.error('Invalid FEN:', e);
    }
  }

  onMount(() => {
    connectWebSocket();
  });

  onDestroy(() => {
    if (ws) {
      ws.close();
    }
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
    }
    stopSpeaking();
  });

  function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${$gameId}`;

    ws = new WebSocket(wsUrl);
    websocket.set(ws);

    ws.onopen = () => {
      console.log('WebSocket connected');
      connectionStatus.set('connected');
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      connectionStatus.set('disconnected');
      websocket.set(null);

      // Reconnect after delay
      reconnectTimer = setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (err) => {
      console.error('WebSocket error:', err);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleServerMessage(data);
    };
  }

  function handleServerMessage(data) {
    console.log('Server message:', data.type, data);

    switch (data.type) {
      case 'game_state':
        updateGameState(data.state);
        break;

      case 'move_result':
        if (data.result.success) {
          updateGameState(data.result.state);
          if (data.result.move_from && data.result.move_to) {
            lastMove.set({ from: data.result.move_from, to: data.result.move_to });
          }
        } else {
          addMessage('system', data.result.error);
        }
        break;

      case 'ai_thinking':
        isThinking = data.thinking;
        break;

      case 'ai_response':
        isThinking = false;
        if (data.state) {
          updateGameState(data.state);
        }
        if (data.move_from && data.move_to) {
          lastMove.set({ from: data.move_from, to: data.move_to });
        }
        addMessage('assistant', data.message, data.move);
        if (data.blunder_feedback) {
          addMessage('system', data.blunder_feedback);
        }
        speak(data.message);
        break;

      case 'undo_result':
        if (data.result.success) {
          updateGameState(data.result.state);
          lastMove.set(null);
        }
        break;

      case 'game_over':
        if (data.state) {
          updateGameState(data.state);
        }
        openModal('gameOver');
        break;

      case 'error':
        addMessage('system', data.message);
        break;
    }
  }

  function send(data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      console.log('[WS SEND]', data);
      ws.send(JSON.stringify(data));
    }
  }

  // Move handling
  function handleSquareClick(e) {
    const { square } = e.detail;

    if ($selectedSquare) {
      // Check if this is a legal move
      if ($legalMovesForSelected.includes(square)) {
        makeMove($selectedSquare, square);
      }
      // Clear selection
      selectedSquare.set(null);
      legalMovesForSelected.set([]);
    } else {
      // Select the square if it has a player's piece
      const piece = chess.get(square);
      if (piece && isMyTurn) {
        const pieceColor = piece.color === 'w' ? 'white' : 'black';
        if (pieceColor === $gameState.playerColor) {
          selectedSquare.set(square);
          // Get legal moves for this piece
          const moves = chess.moves({ square, verbose: true });
          legalMovesForSelected.set(moves.map(m => m.to));
        }
      }
    }
  }

  function handleDragStart(e) {
    const { square, piece } = e.detail;
    if (!isMyTurn) return;

    const pieceObj = chess.get(square);
    if (pieceObj) {
      const pieceColor = pieceObj.color === 'w' ? 'white' : 'black';
      if (pieceColor === $gameState.playerColor) {
        selectedSquare.set(square);
        const moves = chess.moves({ square, verbose: true });
        legalMovesForSelected.set(moves.map(m => m.to));
      }
    }
  }

  function handleMove(e) {
    const { from, to } = e.detail;

    // Validate move is legal
    if ($legalMovesForSelected.includes(to)) {
      makeMove(from, to);
    }

    // Clear selection
    selectedSquare.set(null);
    legalMovesForSelected.set([]);
  }

  function makeMove(from, to) {
    // Check for promotion
    const piece = chess.get(from);
    let promotion = null;

    if (piece && piece.type === 'p') {
      const targetRank = to[1];
      if ((piece.color === 'w' && targetRank === '8') || (piece.color === 'b' && targetRank === '1')) {
        promotion = 'q'; // Auto-promote to queen for now
      }
    }

    send({
      type: 'move',
      from,
      to,
      promotion,
    });

    lastMove.set({ from, to });
  }

  // Chat
  let messageIdCounter = 0;
  function addMessage(role, content, move = null) {
    messages = [...messages, { id: ++messageIdCounter, role, content, move, timestamp: Date.now() }];
  }

  function sendChat(text) {
    addMessage('user', text);
    send({ type: 'chat', message: text });
  }

  function handleChatSubmit() {
    if (chatInput.trim()) {
      sendChat(chatInput.trim());
      chatInput = '';
    }
  }

  function handleChatKeypress(e) {
    if (e.key === 'Enter') {
      handleChatSubmit();
    }
  }

  // TTS
  async function speak(text) {
    if (!$settings.voiceEnabled) return;

    stopSpeaking();

    try {
      const response = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        currentAudio = new Audio(url);
        await currentAudio.play();
      }
    } catch (e) {
      console.error('TTS error:', e);
    }
  }

  function stopSpeaking() {
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.currentTime = 0;
      currentAudio = null;
    }
  }

  // Actions
  function handleUndo() {
    send({ type: 'undo' });
  }

  function handleHint() {
    sendChat("Can you give me a hint?");
  }

  function handleAnalyze() {
    sendChat("Can you analyze the current position?");
  }

  function handleNewGame() {
    stopSpeaking();
    resetGame();
    navigateTo('setup');
  }

  function handleResign() {
    send({ type: 'resign' });
  }

  function toggleVoice() {
    settings.update(s => ({ ...s, voiceEnabled: !s.voiceEnabled }));
  }

  function handleToggleHighlight(e) {
    const { square, color } = e.detail;
    toggleHighlight(square, color);
  }

  function handleToggleArrow(e) {
    const { from, to, color } = e.detail;
    toggleArrow(from, to, color);
  }
</script>

<div class="game-screen">
  <div class="annotation-area">
    <AnnotationPanel />
  </div>

  <div class="board-section">
    <div class="board-header">
      <div class="turn-indicator" class:active={!isMyTurn}>
        <span class="player-label">AI</span>
        {#if isThinking}
          <span class="thinking-indicator">Thinking...</span>
        {/if}
      </div>
    </div>

    <ChessBoard
      position={fen}
      {orientation}
      interactive={isMyTurn && !$gameState.isGameOver}
      selectedSquare={$selectedSquare}
      legalMoves={$legalMovesForSelected}
      lastMove={$lastMove}
      arrows={$arrows}
      highlights={$highlights}
      annotationsEnabled={$annotationsEnabled}
      annotationColor={$annotationColor}
      on:squareClick={handleSquareClick}
      on:dragStart={handleDragStart}
      on:move={handleMove}
      on:toggleHighlight={handleToggleHighlight}
      on:toggleArrow={handleToggleArrow}
    />

    <div class="board-footer">
      <div class="turn-indicator" class:active={isMyTurn}>
        <span class="player-label">You ({$gameState.playerColor})</span>
      </div>
    </div>

    <div class="board-controls">
      <button class="control-btn" on:click={handleUndo} title="Undo">
        ↩️ Undo
      </button>
      <button class="control-btn" on:click={handleHint} title="Hint">
        💡 Hint
      </button>
      <button class="control-btn" on:click={handleAnalyze} title="Analyze">
        📊 Analyze
      </button>
      <button class="control-btn danger" on:click={handleResign} title="Resign">
        🏳️ Resign
      </button>
    </div>
  </div>

  <div class="chat-section">
    <div class="chat-header">
      <h3>Game Chat</h3>
      <div class="header-controls">
        <button
          class="icon-btn"
          class:active={$settings.voiceEnabled}
          on:click={toggleVoice}
          title={$settings.voiceEnabled ? 'Mute voice' : 'Enable voice'}
        >
          {$settings.voiceEnabled ? '🔊' : '🔇'}
        </button>
        <button class="icon-btn" on:click={handleNewGame} title="New Game">
          🆕
        </button>
      </div>
    </div>

    <div class="messages">
      {#each messages as msg (msg.id)}
        <div class="message {msg.role}">
          <span class="message-content">
            {#if msg.move}
              <strong class="move-badge">{msg.move}</strong>
            {/if}
            {msg.content}
          </span>
        </div>
      {/each}
      {#if isThinking}
        <div class="message assistant thinking">
          <span class="dots">
            <span></span><span></span><span></span>
          </span>
        </div>
      {/if}
    </div>

    <div class="chat-input-area">
      <input
        type="text"
        placeholder="Type a message or move..."
        bind:value={chatInput}
        on:keypress={handleChatKeypress}
      />
      <button class="send-btn" on:click={handleChatSubmit}>Send</button>
    </div>
  </div>
</div>

<style>
  .game-screen {
    flex: 1;
    display: grid;
    grid-template-columns: 260px 1fr 380px;
    gap: 0;
    height: calc(100vh - 60px);
    overflow: hidden;
  }

  .annotation-area {
    background: var(--bg-secondary);
    border-right: 1px solid var(--border-color);
    padding: 20px;
    overflow-y: auto;
  }

  .board-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 20px;
    background: var(--bg-primary);
  }

  .board-header,
  .board-footer {
    width: 100%;
    max-width: 520px;
    padding: 8px 0;
  }

  .turn-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--bg-secondary);
    border-radius: 8px;
    opacity: 0.5;
    transition: opacity 0.2s;
  }

  .turn-indicator.active {
    opacity: 1;
    background: var(--accent-blue);
  }

  .player-label {
    font-weight: 600;
    font-size: 0.875rem;
  }

  .thinking-indicator {
    font-size: 0.75rem;
    color: var(--text-secondary);
    animation: pulse 1.5s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }

  .board-controls {
    display: flex;
    gap: 8px;
    margin-top: 16px;
    flex-wrap: wrap;
    justify-content: center;
  }

  .control-btn {
    padding: 8px 16px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.2s;
  }

  .control-btn:hover {
    background: var(--bg-tertiary);
  }

  .control-btn.danger:hover {
    background: rgba(239, 68, 68, 0.2);
    border-color: var(--accent-red);
  }

  .chat-section {
    display: flex;
    flex-direction: column;
    background: var(--bg-secondary);
    border-left: 1px solid var(--border-color);
    height: 100%;
  }

  .chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px;
    border-bottom: 1px solid var(--border-color);
  }

  .chat-header h3 {
    font-size: 1rem;
    font-weight: 600;
  }

  .header-controls {
    display: flex;
    gap: 8px;
  }

  .icon-btn {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    background: var(--bg-tertiary);
    font-size: 1.1rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .icon-btn.active {
    background: var(--accent-blue);
    border-color: var(--accent-blue);
  }

  .messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .message {
    padding: 10px 14px;
    border-radius: 12px;
    max-width: 85%;
    font-size: 0.9rem;
    line-height: 1.4;
  }

  .message.user {
    align-self: flex-end;
    background: var(--accent-blue);
    color: white;
  }

  .message.assistant {
    align-self: flex-start;
    background: var(--bg-tertiary);
  }

  .message.system {
    align-self: center;
    background: rgba(234, 179, 8, 0.2);
    color: var(--accent-yellow);
    font-size: 0.8rem;
    text-align: center;
  }

  .move-badge {
    display: inline-block;
    background: rgba(255, 255, 255, 0.2);
    padding: 2px 6px;
    border-radius: 4px;
    margin-right: 6px;
    font-family: monospace;
  }

  .message.thinking .dots {
    display: flex;
    gap: 4px;
  }

  .message.thinking .dots span {
    width: 8px;
    height: 8px;
    background: var(--text-muted);
    border-radius: 50%;
    animation: bounce 1.4s infinite ease-in-out;
  }

  .message.thinking .dots span:nth-child(1) { animation-delay: -0.32s; }
  .message.thinking .dots span:nth-child(2) { animation-delay: -0.16s; }

  @keyframes bounce {
    0%, 80%, 100% { transform: scale(0); }
    40% { transform: scale(1); }
  }

  .chat-input-area {
    display: flex;
    gap: 8px;
    padding: 16px;
    border-top: 1px solid var(--border-color);
  }

  .chat-input-area input {
    flex: 1;
    padding: 12px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: 0.9rem;
  }

  .chat-input-area input::placeholder {
    color: var(--text-muted);
  }

  .send-btn {
    padding: 12px 20px;
    background: var(--accent-blue);
    border: none;
    border-radius: 8px;
    color: white;
    font-weight: 600;
    cursor: pointer;
  }

  .send-btn:hover {
    background: #2563eb;
  }

  /* Responsive */
  @media (max-width: 1100px) {
    .game-screen {
      grid-template-columns: 1fr 340px;
    }

    .annotation-area {
      display: none;
    }
  }

  @media (max-width: 900px) {
    .game-screen {
      grid-template-columns: 1fr;
      grid-template-rows: 1fr auto;
    }

    .annotation-area {
      display: none;
    }

    .chat-section {
      border-left: none;
      border-top: 1px solid var(--border-color);
      max-height: 300px;
    }
  }
</style>
