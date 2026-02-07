<script>
  import { onMount, onDestroy } from 'svelte';
  import { Chess } from 'chess.js';
  import { marked } from 'marked';
  import ChessBoard from '../components/ChessBoard.svelte';
  import AnnotationPanel from '../components/AnnotationPanel.svelte';
  import { navigateTo, openModal } from '../stores/app.js';

  // Configure marked for safe inline rendering
  marked.setOptions({
    breaks: true,
    gfm: true,
  });

  // Strip markdown for TTS - convert to plain readable text
  function stripMarkdownForTTS(text) {
    return text
      // Remove code blocks
      .replace(/```[\s\S]*?```/g, '')
      .replace(/`([^`]+)`/g, '$1')
      // Remove headers but keep text
      .replace(/#{1,6}\s+/g, '')
      // Remove bold/italic markers
      .replace(/\*\*([^*]+)\*\*/g, '$1')
      .replace(/\*([^*]+)\*/g, '$1')
      .replace(/__([^_]+)__/g, '$1')
      .replace(/_([^_]+)_/g, '$1')
      // Remove links but keep text
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      // Remove bullet points
      .replace(/^[\s]*[-*+]\s+/gm, '')
      // Remove numbered lists prefix
      .replace(/^[\s]*\d+\.\s+/gm, '')
      // Clean up extra whitespace
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  }

  // Render markdown to HTML
  function renderMarkdown(text) {
    try {
      return marked.parse(text);
    } catch (e) {
      return text;
    }
  }
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
  let localFen = null; // For immediate player move display
  let isSpeaking = false;
  let moveHistory = []; // Array of { san, from, to, isPlayer }
  let lastAIMove = null; // { from, to, san } for replay
  let isReplaying = false;

  // Voice recognition state
  let recognition = null;
  let isListening = false;
  let alwaysOnMode = true; // Default to always-on
  let silenceTimer = null;
  let accumulatedTranscript = '';

  // Get the current state values
  $: orientation = $gameState.playerColor;
  $: serverFen = $gameState.fen;
  $: fen = localFen || serverFen; // Use localFen for immediate player move display
  $: turnText = $gameState.turn === 'white' ? 'White to move' : 'Black to move';
  $: isMyTurn = $isPlayerTurn;

  // Clear localFen when server updates (after move confirmed)
  $: if (serverFen && !isThinking) {
    localFen = null;
  }

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
    initSpeechRecognition();
    // Start listening if always-on mode is enabled by default
    if (alwaysOnMode) {
      setTimeout(() => startListening(), 500);
    }
  });

  onDestroy(() => {
    if (ws) {
      ws.close();
    }
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
    }
    stopSpeaking();
    stopListening();
  });

  // Voice recognition setup
  function initSpeechRecognition() {
    if (typeof window === 'undefined') return;

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onresult = (event) => {
      if (silenceTimer) {
        clearTimeout(silenceTimer);
        silenceTimer = null;
      }

      let finalTranscript = '';
      let interimTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        } else {
          interimTranscript = transcript;
        }
      }

      if (finalTranscript) {
        accumulatedTranscript += finalTranscript;
        // Set timer to submit after silence
        silenceTimer = setTimeout(() => {
          if (accumulatedTranscript.trim()) {
            sendChat(accumulatedTranscript.trim());
            accumulatedTranscript = '';
          }
        }, 1500);
      }

      // Update input with current transcript
      chatInput = accumulatedTranscript + interimTranscript;
    };

    recognition.onerror = (event) => {
      // 'aborted' is expected when we pause for TTS - don't log it
      if (event.error === 'aborted') return;

      if (event.error === 'no-speech' && alwaysOnMode && !isSpeaking && !isThinking) {
        restartListening();
        return;
      }
      if (event.error === 'not-allowed') {
        console.error('Speech error:', event.error);
        addMessage('system', 'Microphone access denied. Please allow and reload.');
        alwaysOnMode = false;
      }
      isListening = false;
    };

    recognition.onend = () => {
      if (alwaysOnMode && !isSpeaking && !isThinking) {
        setTimeout(() => {
          if (alwaysOnMode && !isSpeaking && !isThinking) {
            restartListening();
          }
        }, 100);
      } else {
        isListening = false;
      }
    };
  }

  function restartListening() {
    if (!recognition || isSpeaking || isThinking) return;
    try {
      recognition.start();
      isListening = true;
    } catch (e) {
      console.log('Recognition restart error:', e.message);
    }
  }

  function startListening() {
    if (!recognition || isThinking || isSpeaking) return;
    stopSpeaking();
    try {
      recognition.start();
      isListening = true;
      accumulatedTranscript = '';
    } catch (e) {
      console.log('Start listening error:', e.message);
    }
  }

  function stopListening() {
    alwaysOnMode = false;
    if (recognition) {
      try { recognition.stop(); } catch (e) {}
    }
    isListening = false;
    if (silenceTimer) {
      clearTimeout(silenceTimer);
      silenceTimer = null;
    }
    accumulatedTranscript = '';
  }

  function pauseListening() {
    if (recognition && isListening) {
      try { recognition.stop(); } catch (e) {}
      isListening = false;
    }
    if (silenceTimer) {
      clearTimeout(silenceTimer);
      silenceTimer = null;
    }
    accumulatedTranscript = '';
  }

  function toggleMic() {
    if (!recognition) {
      initSpeechRecognition();
      if (!recognition) {
        addMessage('system', 'Speech recognition not supported');
        return;
      }
    }

    alwaysOnMode = !alwaysOnMode;
    if (alwaysOnMode) {
      startListening();
    } else {
      stopListening();
    }
  }

  function resumeListeningIfAlwaysOn() {
    if (alwaysOnMode && !isSpeaking && !isThinking) {
      startListening();
    }
  }

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
            // Track player move in history
            moveHistory = [...moveHistory, {
              san: data.result.move,
              from: data.result.move_from,
              to: data.result.move_to,
              isPlayer: true
            }];
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
          // Track AI move for replay and history
          lastAIMove = { from: data.move_from, to: data.move_to, san: data.move };
          moveHistory = [...moveHistory, {
            san: data.move,
            from: data.move_from,
            to: data.move_to,
            isPlayer: false
          }];
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

    // Show move immediately on the board (optimistic update)
    const move = chess.move({ from, to, promotion: promotion || undefined });
    if (move) {
      localFen = chess.fen();
      lastMove.set({ from, to });
    }

    // Send to server
    send({
      type: 'move',
      from,
      to,
      promotion,
    });
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
    pauseListening(); // Stop listening while speaking
    isSpeaking = true;

    // Strip markdown for natural speech
    const cleanText = stripMarkdownForTTS(text);
    if (!cleanText) {
      isSpeaking = false;
      resumeListeningIfAlwaysOn();
      return;
    }

    try {
      const response = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: cleanText }),
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        currentAudio = new Audio(url);

        currentAudio.onended = () => {
          isSpeaking = false;
          currentAudio = null;
          resumeListeningIfAlwaysOn();
        };

        await currentAudio.play();
      } else {
        isSpeaking = false;
        resumeListeningIfAlwaysOn();
      }
    } catch (e) {
      console.error('TTS error:', e);
      isSpeaking = false;
      resumeListeningIfAlwaysOn();
    }
  }

  function stopSpeaking() {
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.currentTime = 0;
      currentAudio = null;
    }
    isSpeaking = false;
  }

  function skipSpeaking() {
    // Skip current speech but don't disable TTS permanently
    stopSpeaking();
    resumeListeningIfAlwaysOn();
  }

  function replayLastMove() {
    if (!lastAIMove || isReplaying) return;

    isReplaying = true;

    // Temporarily clear the last move highlight
    const currentLastMove = $lastMove;
    lastMove.set(null);

    // Flash the squares
    setTimeout(() => {
      lastMove.set({ from: lastAIMove.from, to: lastAIMove.to });
      isReplaying = false;
    }, 200);
  }

  // Actions
  function handleUndo() {
    send({ type: 'undo' });
    // Remove last 2 moves from history (player + AI)
    if (moveHistory.length >= 2) {
      moveHistory = moveHistory.slice(0, -2);
    } else {
      moveHistory = [];
    }
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

    <!-- Moves list strip -->
    <div class="moves-strip">
      {#if moveHistory.length === 0}
        <span class="moves-placeholder">Moves will appear here...</span>
      {:else}
        <div class="moves-scroll">
          {#each moveHistory as move, i}
            {#if i % 2 === 0}
              <span class="move-number">{Math.floor(i / 2) + 1}.</span>
            {/if}
            <span class="move-san" class:player={move.isPlayer} class:ai={!move.isPlayer}>
              {move.san}
            </span>
          {/each}
        </div>
      {/if}
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
          class:active={alwaysOnMode}
          class:listening={isListening}
          on:click={toggleMic}
          title={alwaysOnMode ? 'Disable voice input' : 'Enable voice input (always-on)'}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
          </svg>
        </button>
        <button
          class="icon-btn"
          class:active={$settings.voiceEnabled}
          on:click={toggleVoice}
          title={$settings.voiceEnabled ? 'Mute voice' : 'Enable voice'}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            {#if $settings.voiceEnabled}
              <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
            {:else}
              <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
            {/if}
          </svg>
        </button>
        <button
          class="icon-btn"
          on:click={skipSpeaking}
          disabled={!isSpeaking}
          title="Skip current speech"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/>
          </svg>
        </button>
        <button
          class="icon-btn"
          on:click={replayLastMove}
          disabled={!lastAIMove || isReplaying}
          title="Replay last AI move"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/>
          </svg>
        </button>
        <button class="icon-btn" on:click={handleNewGame} title="New Game">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
          </svg>
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
            {#if msg.role === 'assistant'}
              {@html renderMarkdown(msg.content)}
            {:else}
              {msg.content}
            {/if}
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

  .moves-strip {
    width: 100%;
    max-width: 520px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 8px 12px;
    margin-bottom: 8px;
    min-height: 36px;
    display: flex;
    align-items: center;
  }

  .moves-placeholder {
    color: var(--text-muted);
    font-size: 0.8rem;
    font-style: italic;
  }

  .moves-scroll {
    display: flex;
    flex-wrap: nowrap;
    gap: 4px;
    overflow-x: auto;
    white-space: nowrap;
    scrollbar-width: thin;
  }

  .moves-scroll::-webkit-scrollbar {
    height: 4px;
  }

  .moves-scroll::-webkit-scrollbar-thumb {
    background: var(--border-color);
    border-radius: 2px;
  }

  .move-number {
    color: var(--text-muted);
    font-size: 0.75rem;
    font-weight: 600;
    margin-right: 2px;
  }

  .move-san {
    font-family: monospace;
    font-size: 0.85rem;
    padding: 2px 6px;
    border-radius: 4px;
    cursor: default;
  }

  .move-san.player {
    background: rgba(59, 130, 246, 0.2);
    color: var(--accent-blue);
  }

  .move-san.ai {
    background: rgba(239, 68, 68, 0.2);
    color: #fca5a5;
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

  .icon-btn.listening {
    background: var(--accent-red);
    border-color: var(--accent-red);
    animation: pulse-mic 1s infinite;
  }

  @keyframes pulse-mic {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.1); }
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

  /* Markdown content styles */
  .message-content :global(p) {
    margin: 0 0 0.5em 0;
  }

  .message-content :global(p:last-child) {
    margin-bottom: 0;
  }

  .message-content :global(h1),
  .message-content :global(h2),
  .message-content :global(h3),
  .message-content :global(h4) {
    margin: 0.5em 0 0.3em 0;
    font-weight: 600;
  }

  .message-content :global(h1) { font-size: 1.1em; }
  .message-content :global(h2) { font-size: 1.05em; }
  .message-content :global(h3) { font-size: 1em; }

  .message-content :global(ul),
  .message-content :global(ol) {
    margin: 0.3em 0;
    padding-left: 1.5em;
  }

  .message-content :global(li) {
    margin: 0.2em 0;
  }

  .message-content :global(code) {
    background: rgba(0, 0, 0, 0.2);
    padding: 0.1em 0.3em;
    border-radius: 3px;
    font-family: monospace;
    font-size: 0.9em;
  }

  .message-content :global(pre) {
    background: rgba(0, 0, 0, 0.3);
    padding: 0.5em;
    border-radius: 4px;
    overflow-x: auto;
    margin: 0.5em 0;
  }

  .message-content :global(pre code) {
    background: none;
    padding: 0;
  }

  .message-content :global(strong) {
    font-weight: 600;
  }

  .message-content :global(em) {
    font-style: italic;
  }

  .message-content :global(a) {
    color: inherit;
    text-decoration: underline;
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
