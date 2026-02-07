<script>
  import { onMount, onDestroy } from 'svelte';
  import { Chess } from 'chess.js';
  import ChessBoard from '../components/ChessBoard.svelte';
  import AnnotationPanel from '../components/AnnotationPanel.svelte';
  import { navigateTo } from '../stores/app.js';
  import {
    trainingSession,
    currentOpening,
    currentHint,
    trainingMessages,
    trainingStats,
    trainingProgress,
    isTraining,
    trainingVoiceEnabled,
    addTrainingMessage,
    resetTraining,
  } from '../stores/training.js';
  import {
    arrows,
    highlights,
    annotationsEnabled,
    annotationColor,
    toggleArrow,
    toggleHighlight,
    clearAnnotations,
  } from '../stores/annotations.js';
  import {
    getOpenings,
    getTrainingStats,
    startTraining,
    submitTrainingMove,
    completeTraining,
  } from '../api.js';

  let openings = [];
  let loading = true;
  let error = null;
  let chess = new Chess();
  let selectedSquare = null;
  let legalMoves = [];
  let lastMove = null;
  let currentAudio = null;

  // Extract state from training session - API returns state.fen, not fen directly
  $: sessionState = $trainingSession?.state || {};
  $: fen = sessionState?.fen || 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
  $: orientation = $trainingSession?.player_color || $currentOpening?.color || 'white';

  // Calculate whose turn based on FEN and player color
  $: fenTurn = fen.split(' ')[1] === 'w' ? 'white' : 'black';
  $: isMyTurn = fenTurn === orientation;

  // Hint from current_hint field
  $: hint = $trainingSession?.current_hint || null;
  $: hintLevel = $trainingSession?.hint_level || 'full';

  $: {
    try {
      chess.load(fen);
    } catch (e) {
      console.error('Invalid FEN:', e);
    }
  }

  onMount(async () => {
    await loadData();

    // Auto-start if opening was pre-selected from modal
    if ($currentOpening && !$isTraining) {
      await handleSelectOpening($currentOpening);
    }
  });

  onDestroy(() => {
    stopSpeaking();
  });

  async function loadData() {
    loading = true;
    error = null;

    try {
      const [openingsData, statsData] = await Promise.all([
        getOpenings().catch(() => ({ openings: [] })),
        getTrainingStats().catch(() => ({})),
      ]);

      openings = openingsData.openings || [];
      trainingStats.set(statsData);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function handleSelectOpening(opening) {
    try {
      loading = true;
      const result = await startTraining(opening.id);

      currentOpening.set(opening);
      trainingSession.set(result);

      addTrainingMessage('info', `Starting ${opening.name} training...`);

      // Set hint from current_hint field
      if (result.current_hint) {
        currentHint.set(result.current_hint);
        const hintSpeech = buildHintSpeech(result.current_hint);
        addTrainingMessage('hint', hintSpeech);
        if ($trainingVoiceEnabled) {
          speak(hintSpeech);
        }
      }
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function handleSquareClick(e) {
    const { square } = e.detail;

    if (selectedSquare) {
      if (legalMoves.includes(square)) {
        makeMove(selectedSquare, square);
      }
      selectedSquare = null;
      legalMoves = [];
    } else {
      const piece = chess.get(square);
      if (piece && isMyTurn) {
        const playerColor = orientation === 'white' ? 'w' : 'b';
        if (piece.color === playerColor) {
          selectedSquare = square;
          const moves = chess.moves({ square, verbose: true });
          legalMoves = moves.map(m => m.to);
        }
      }
    }
  }

  function handleDragStart(e) {
    const { square } = e.detail;
    if (!isMyTurn) return;

    const piece = chess.get(square);
    if (piece) {
      const playerColor = orientation === 'white' ? 'w' : 'b';
      if (piece.color === playerColor) {
        selectedSquare = square;
        const moves = chess.moves({ square, verbose: true });
        legalMoves = moves.map(m => m.to);
      }
    }
  }

  function handleMove(e) {
    const { from, to } = e.detail;

    if (legalMoves.includes(to)) {
      makeMove(from, to);
    }

    selectedSquare = null;
    legalMoves = [];
  }

  async function makeMove(from, to) {
    const move = chess.move({ from, to, promotion: 'q' });
    if (!move) return;

    lastMove = { from, to };

    try {
      const result = await submitTrainingMove($trainingSession.session_id, move.san);

      if (result.correct) {
        addTrainingMessage('success', result.message || 'Correct!');

        // Update opponent's move in lastMove if they responded
        if (result.opponent_move) {
          addTrainingMessage('info', `Opponent plays: ${result.opponent_move}`);
        }
      } else {
        addTrainingMessage('error', result.message || 'Not quite...');
        if (result.expected_move) {
          addTrainingMessage('hint', `Expected: ${result.expected_move}`);
        }
        // Undo the incorrect move locally
        chess.undo();
      }

      // Update session state with new position
      if (result.state) {
        trainingSession.update(s => ({
          ...s,
          state: result.state,
          current_move_index: result.current_move_index,
        }));
      }

      // Set next hint
      if (result.next_hint) {
        currentHint.set(result.next_hint);
        const hintSpeech = buildHintSpeech(result.next_hint);
        addTrainingMessage('hint', hintSpeech);
        if ($trainingVoiceEnabled) {
          speak(hintSpeech);
        }
      } else {
        currentHint.set(null);
      }

      // Check if training is complete
      if (result.is_complete) {
        await handleSessionComplete();
      }
    } catch (e) {
      addTrainingMessage('error', e.message);
      chess.undo();
    }
  }

  async function handleSessionComplete() {
    try {
      await completeTraining($trainingSession.session_id);
      addTrainingMessage('info', 'Training session complete! Great work!');

      // Reload stats
      const stats = await getTrainingStats();
      trainingStats.set(stats);
    } catch (e) {
      console.error('Error completing training:', e);
    }
  }

  function handleExit() {
    resetTraining();
    navigateTo('setup');
  }

  async function speak(text) {
    if (!$trainingVoiceEnabled) return;

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

  function toggleVoice() {
    trainingVoiceEnabled.update(v => !v);
  }

  function getMasteryClass(mastery) {
    if (mastery >= 0.9) return 'mastered';
    if (mastery >= 0.7) return 'proficient';
    if (mastery >= 0.4) return 'learning';
    return 'beginner';
  }

  function getMasteryLabel(mastery) {
    if (mastery >= 0.9) return 'Mastered';
    if (mastery >= 0.7) return 'Proficient';
    if (mastery >= 0.4) return 'Learning';
    return 'Beginner';
  }

  function buildHintSpeech(hint) {
    if (!hint) return 'Your move';

    const parts = [];
    if (hint.move) {
      parts.push(`Play ${hint.move}`);
    } else if (hint.piece_hint) {
      parts.push(`Move your ${hint.piece_hint}`);
    }
    if (hint.explanation) {
      parts.push(hint.explanation);
    }
    return parts.length > 0 ? parts.join('. ') : 'Your move';
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

<div class="training-screen">
  {#if !$isTraining}
    <!-- Opening Selection -->
    <div class="selection-view">
      <div class="selection-header">
        <h2>Train Openings</h2>
        <button class="btn-back" on:click={handleExit}>Back</button>
      </div>

      {#if loading}
        <div class="loading">Loading openings...</div>
      {:else if error}
        <div class="error">{error}</div>
      {:else}
        <div class="stats-bar">
          <div class="stat">
            <span class="stat-label">Today</span>
            <span class="stat-value">{$trainingStats.sessionsToday || 0} / {$trainingStats.dailyGoal || 5}</span>
          </div>
          <div class="stat">
            <span class="stat-label">Total Sessions</span>
            <span class="stat-value">{$trainingStats.totalSessions || 0}</span>
          </div>
        </div>

        <div class="openings-grid">
          {#each openings as opening}
            <button
              class="opening-card"
              class:white={opening.color === 'white'}
              class:black={opening.color === 'black'}
              on:click={() => handleSelectOpening(opening)}
            >
              <div class="opening-header">
                <span class="opening-name">{opening.name}</span>
                <span class="mastery-badge {getMasteryClass(opening.mastery || 0)}">
                  {getMasteryLabel(opening.mastery || 0)}
                </span>
              </div>
              <div class="opening-info">
                <span class="color-badge">{opening.color}</span>
                {#if opening.response_to}
                  <span class="response-to">vs {opening.response_to}</span>
                {/if}
              </div>
              <div class="opening-moves">{opening.preview || ''}</div>
            </button>
          {/each}
        </div>
      {/if}
    </div>
  {:else}
    <!-- Training Session -->
    <div class="session-view">
      <div class="annotation-area">
        <AnnotationPanel />
      </div>

      <div class="board-area">
        <div class="session-header">
          <h3>{$currentOpening?.name || 'Training'}</h3>
          <div class="progress-bar">
            <div class="progress-fill" style="width: {$trainingProgress.percent}%"></div>
          </div>
          <span class="progress-text">
            Move {$trainingProgress.current} / {$trainingProgress.total}
          </span>
        </div>

        <ChessBoard
          position={fen}
          {orientation}
          interactive={isMyTurn}
          {selectedSquare}
          legalMoves={legalMoves}
          {lastMove}
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
          <button class="btn-secondary" on:click={handleExit}>Exit Training</button>
          <button class="btn-icon" class:active={$trainingVoiceEnabled} on:click={toggleVoice}>
            {$trainingVoiceEnabled ? '🔊' : '🔇'}
          </button>
        </div>
      </div>

      <div class="hint-panel">
        <h4>Hint</h4>
        {#if hint}
          <div class="hint-content hint-{hint.level || hintLevel}">
            {#if hint.move}
              <div class="hint-move">Play: <strong>{hint.move}</strong></div>
            {:else if hint.piece_hint}
              <div class="hint-piece">Move your <strong>{hint.piece_hint}</strong></div>
            {/if}
            {#if hint.explanation}
              <div class="hint-explanation">{hint.explanation}</div>
            {/if}
          </div>
        {:else}
          <div class="hint-content hint-none">
            Your move...
          </div>
        {/if}

        <div class="feedback-section">
          <h4>Feedback</h4>
          <div class="feedback-list">
            {#if $trainingMessages.length === 0}
              <div class="feedback-empty">Make a move to see feedback</div>
            {:else}
              {#each [...$trainingMessages].slice(-5).reverse() as msg (msg.id)}
                <div class="feedback-item {msg.type}">
                  {msg.message}
                </div>
              {/each}
            {/if}
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .training-screen {
    flex: 1;
    display: flex;
    flex-direction: column;
    background: var(--bg-primary);
  }

  /* Selection View */
  .selection-view {
    flex: 1;
    padding: 24px;
    max-width: 800px;
    margin: 0 auto;
    width: 100%;
  }

  .selection-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 24px;
  }

  .selection-header h2 {
    font-size: 1.5rem;
    font-weight: 600;
    margin: 0;
  }

  .btn-back {
    padding: 8px 16px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    color: var(--text-primary);
    cursor: pointer;
  }

  .stats-bar {
    display: flex;
    gap: 24px;
    padding: 16px;
    background: var(--bg-secondary);
    border-radius: 12px;
    margin-bottom: 24px;
  }

  .stat {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .stat-label {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .stat-value {
    font-size: 1.25rem;
    font-weight: 600;
  }

  .openings-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }

  .opening-card {
    padding: 16px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    text-align: left;
    cursor: pointer;
    transition: all 0.2s;
  }

  .opening-card:hover {
    transform: translateY(-2px);
    border-color: var(--accent-blue);
  }

  .opening-card.white {
    border-left: 4px solid #f8fafc;
  }

  .opening-card.black {
    border-left: 4px solid #1e293b;
  }

  .opening-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }

  .opening-name {
    font-weight: 600;
    font-size: 1rem;
  }

  .mastery-badge {
    font-size: 0.7rem;
    padding: 2px 8px;
    border-radius: 12px;
    font-weight: 500;
  }

  .mastery-badge.beginner {
    background: rgba(239, 68, 68, 0.2);
    color: #fca5a5;
  }

  .mastery-badge.learning {
    background: rgba(234, 179, 8, 0.2);
    color: #fde047;
  }

  .mastery-badge.proficient {
    background: rgba(59, 130, 246, 0.2);
    color: #93c5fd;
  }

  .mastery-badge.mastered {
    background: rgba(34, 197, 94, 0.2);
    color: #86efac;
  }

  .opening-info {
    display: flex;
    gap: 8px;
    margin-bottom: 8px;
    font-size: 0.8rem;
    color: var(--text-secondary);
  }

  .color-badge {
    text-transform: capitalize;
  }

  .opening-moves {
    font-family: monospace;
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  /* Session View */
  .session-view {
    flex: 1;
    display: grid;
    grid-template-columns: 260px 1fr 320px;
    gap: 0;
    height: calc(100vh - 60px);
  }

  .annotation-area {
    background: var(--bg-secondary);
    border-right: 1px solid var(--border-color);
    padding: 20px;
    overflow-y: auto;
  }

  .board-area {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }

  .session-header {
    width: 100%;
    max-width: 520px;
    margin-bottom: 16px;
  }

  .session-header h3 {
    margin: 0 0 8px;
    font-size: 1.1rem;
  }

  .progress-bar {
    height: 6px;
    background: var(--bg-tertiary);
    border-radius: 3px;
    overflow: hidden;
    margin-bottom: 4px;
  }

  .progress-fill {
    height: 100%;
    background: var(--accent-green);
    transition: width 0.3s;
  }

  .progress-text {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .board-footer {
    display: flex;
    gap: 12px;
    margin-top: 16px;
  }

  .btn-secondary {
    padding: 10px 20px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    color: var(--text-primary);
    cursor: pointer;
  }

  .btn-icon {
    width: 40px;
    height: 40px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    background: var(--bg-secondary);
    font-size: 1.2rem;
    cursor: pointer;
  }

  .btn-icon.active {
    background: var(--accent-blue);
    border-color: var(--accent-blue);
  }

  .hint-panel {
    background: var(--bg-secondary);
    border-left: 1px solid var(--border-color);
    padding: 20px;
    display: flex;
    flex-direction: column;
  }

  .hint-panel h4 {
    margin: 0 0 12px;
    font-size: 0.875rem;
    color: var(--text-secondary);
  }

  .hint-content {
    padding: 16px;
    background: var(--bg-tertiary);
    border-radius: 8px;
    margin-bottom: 16px;
    font-size: 1rem;
    line-height: 1.5;
  }

  .hint-content.hint-full {
    border-left: 3px solid var(--accent-green);
  }

  .hint-content.hint-partial {
    border-left: 3px solid var(--accent-blue);
  }

  .hint-content.hint-minimal {
    border-left: 3px solid var(--accent-yellow);
  }

  .hint-content.hint-none {
    border-left: 3px solid var(--text-muted);
    color: var(--text-muted);
  }

  .hint-move,
  .hint-piece {
    font-size: 1.1rem;
    margin-bottom: 8px;
  }

  .hint-move strong,
  .hint-piece strong {
    color: var(--accent-green);
  }

  .hint-explanation {
    font-size: 0.9rem;
    color: var(--text-secondary);
    line-height: 1.5;
  }

  .feedback-section {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 120px;
  }

  .feedback-section h4 {
    margin: 0 0 8px;
    font-size: 0.8rem;
    color: var(--text-muted);
    text-transform: uppercase;
  }

  .feedback-list {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 8px;
    background: var(--bg-primary);
    border-radius: 8px;
    padding: 12px;
  }

  .feedback-empty {
    color: var(--text-muted);
    font-size: 0.85rem;
    text-align: center;
    padding: 20px;
  }

  .feedback-item {
    padding: 10px 12px;
    border-radius: 8px;
    font-size: 0.875rem;
  }

  .feedback-item.success {
    background: rgba(34, 197, 94, 0.2);
    color: #86efac;
  }

  .feedback-item.error {
    background: rgba(239, 68, 68, 0.2);
    color: #fca5a5;
  }

  .feedback-item.hint {
    background: rgba(59, 130, 246, 0.2);
    color: #93c5fd;
  }

  .feedback-item.info {
    background: rgba(148, 163, 184, 0.2);
    color: var(--text-secondary);
  }

  .loading,
  .error {
    text-align: center;
    padding: 40px;
    color: var(--text-secondary);
  }

  .error {
    color: var(--accent-red);
  }

  @media (max-width: 1100px) {
    .session-view {
      grid-template-columns: 1fr 280px;
    }

    .annotation-area {
      display: none;
    }
  }

  @media (max-width: 900px) {
    .session-view {
      grid-template-columns: 1fr;
      grid-template-rows: 1fr auto;
    }

    .annotation-area {
      display: none;
    }

    .hint-panel {
      border-left: none;
      border-top: 1px solid var(--border-color);
      max-height: 200px;
    }
  }
</style>
