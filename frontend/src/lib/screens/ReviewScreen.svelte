<script>
  import { onMount, onDestroy } from 'svelte';
  import { Chess } from 'chess.js';
  import ChessBoard from '../components/ChessBoard.svelte';
  import { navigateTo } from '../stores/app.js';
  import {
    reviewSession,
    currentCard,
    reviewFeedback,
    reviewStats,
    reviewProgress,
    isReviewing,
    reviewVoiceEnabled,
    addReviewFeedback,
    resetReview,
  } from '../stores/review.js';
  import {
    getReviewStats,
    getDueCards,
    startReview,
    submitReviewAnswer,
    skipReviewCard,
    completeReview,
  } from '../api.js';

  let loading = true;
  let error = null;
  let chess = new Chess();
  let selectedSquare = null;
  let legalMoves = [];
  let lastMove = null;
  let currentAudio = null;
  let showAnswer = false;
  let lastResult = null;

  $: fen = $currentCard?.fen || 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
  $: orientation = $currentCard?.color || 'white';
  $: cardType = $currentCard?.card_type || 'opening';

  $: {
    try {
      chess.load(fen);
    } catch (e) {
      console.error('Invalid FEN:', e);
    }
  }

  onMount(async () => {
    await loadStats();
  });

  onDestroy(() => {
    stopSpeaking();
  });

  async function loadStats() {
    loading = true;
    error = null;

    try {
      const stats = await getReviewStats();
      reviewStats.set(stats);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function handleStartReview() {
    try {
      loading = true;
      const result = await startReview();

      reviewSession.set(result);
      if (result.current_card) {
        currentCard.set(result.current_card);
      }

      showAnswer = false;
      lastResult = null;
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function handleSquareClick(e) {
    const { square } = e.detail;

    if (showAnswer) return; // Don't allow moves after showing answer

    if (selectedSquare) {
      if (legalMoves.includes(square)) {
        makeMove(selectedSquare, square);
      }
      selectedSquare = null;
      legalMoves = [];
    } else {
      const piece = chess.get(square);
      if (piece) {
        // For review, player can be either color depending on the card
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
    if (showAnswer) return;

    const { square } = e.detail;
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

    if (legalMoves.includes(to) && !showAnswer) {
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
      const result = await submitReviewAnswer($reviewSession.session_id, move.san);

      lastResult = result;
      showAnswer = true;

      addReviewFeedback(result.correct, result.expected_move, result.explanation);

      if (result.correct) {
        if ($reviewVoiceEnabled) {
          speak('Correct!');
        }
      } else {
        if ($reviewVoiceEnabled) {
          speak(`The correct move was ${result.expected_move}`);
        }
      }

      // Update session stats
      if (result.session_stats) {
        reviewSession.update(s => ({ ...s, ...result.session_stats }));
      }
    } catch (e) {
      error = e.message;
    }
  }

  async function handleNextCard() {
    showAnswer = false;
    lastResult = null;
    lastMove = null;
    selectedSquare = null;
    legalMoves = [];

    if ($reviewSession?.next_card) {
      currentCard.set($reviewSession.next_card);
    } else if ($reviewSession?.completed) {
      await handleCompleteReview();
    } else {
      // Session might have ended
      resetReview();
      await loadStats();
    }
  }

  async function handleSkipCard() {
    try {
      const result = await skipReviewCard($reviewSession.session_id);

      showAnswer = false;
      lastResult = null;
      lastMove = null;

      if (result.next_card) {
        currentCard.set(result.next_card);
      } else if (result.completed) {
        await handleCompleteReview();
      }
    } catch (e) {
      error = e.message;
    }
  }

  async function handleCompleteReview() {
    try {
      await completeReview($reviewSession.session_id);
      resetReview();
      await loadStats();
    } catch (e) {
      console.error('Error completing review:', e);
    }
  }

  function handleExit() {
    resetReview();
    navigateTo('setup');
  }

  async function speak(text) {
    if (!$reviewVoiceEnabled) return;

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
    reviewVoiceEnabled.update(v => !v);
  }

  function getLeitnerBoxColor(box) {
    const colors = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#3b82f6', '#8b5cf6'];
    return colors[Math.min(box - 1, 5)] || colors[0];
  }
</script>

<div class="review-screen">
  {#if !$isReviewing}
    <!-- Review Start -->
    <div class="start-view">
      <div class="start-header">
        <h2>Spaced Repetition Review</h2>
        <button class="btn-back" on:click={handleExit}>Back</button>
      </div>

      {#if loading}
        <div class="loading">Loading review stats...</div>
      {:else if error}
        <div class="error">{error}</div>
      {:else}
        <div class="stats-card">
          <div class="stats-grid">
            <div class="stat-item">
              <span class="stat-value due">{$reviewStats.dueCount || 0}</span>
              <span class="stat-label">Cards Due</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{$reviewStats.totalCards || 0}</span>
              <span class="stat-label">Total Cards</span>
            </div>
            <div class="stat-item">
              <span class="stat-value mastered">{$reviewStats.masteredCount || 0}</span>
              <span class="stat-label">Mastered</span>
            </div>
          </div>

          {#if ($reviewStats.dueCount || 0) > 0}
            <button class="btn-start" on:click={handleStartReview}>
              Start Review ({$reviewStats.dueCount} cards)
            </button>
          {:else}
            <div class="no-cards">
              <p>No cards due for review!</p>
              <p class="hint">Play some games or train openings to add new cards.</p>
            </div>
          {/if}
        </div>

        <div class="leitner-info">
          <h3>Leitner System</h3>
          <p>Cards move between boxes based on your answers:</p>
          <div class="leitner-boxes">
            <div class="leitner-box" style="--box-color: {getLeitnerBoxColor(1)}">
              <span class="box-num">1</span>
              <span class="box-interval">Daily</span>
            </div>
            <div class="leitner-box" style="--box-color: {getLeitnerBoxColor(2)}">
              <span class="box-num">2</span>
              <span class="box-interval">2 days</span>
            </div>
            <div class="leitner-box" style="--box-color: {getLeitnerBoxColor(3)}">
              <span class="box-num">3</span>
              <span class="box-interval">4 days</span>
            </div>
            <div class="leitner-box" style="--box-color: {getLeitnerBoxColor(4)}">
              <span class="box-num">4</span>
              <span class="box-interval">1 week</span>
            </div>
            <div class="leitner-box" style="--box-color: {getLeitnerBoxColor(5)}">
              <span class="box-num">5</span>
              <span class="box-interval">2 weeks</span>
            </div>
            <div class="leitner-box" style="--box-color: {getLeitnerBoxColor(6)}">
              <span class="box-num">6</span>
              <span class="box-interval">Mastered</span>
            </div>
          </div>
        </div>
      {/if}
    </div>
  {:else}
    <!-- Review Session -->
    <div class="session-view">
      <div class="board-area">
        <div class="session-header">
          <div class="card-info">
            <span class="card-type">{cardType}</span>
            {#if $currentCard?.box}
              <span class="card-box" style="background: {getLeitnerBoxColor($currentCard.box)}">
                Box {$currentCard.box}
              </span>
            {/if}
          </div>
          <div class="progress-bar">
            <div class="progress-fill" style="width: {$reviewProgress.percent}%"></div>
          </div>
          <span class="progress-text">
            {$reviewProgress.current} / {$reviewProgress.total}
          </span>
        </div>

        <ChessBoard
          position={fen}
          {orientation}
          interactive={!showAnswer}
          {selectedSquare}
          legalMoves={legalMoves}
          {lastMove}
          on:squareClick={handleSquareClick}
          on:dragStart={handleDragStart}
          on:move={handleMove}
        />

        <div class="board-footer">
          <button class="btn-secondary" on:click={handleExit}>Exit</button>
          <button class="btn-secondary" on:click={handleSkipCard}>Skip</button>
          <button class="btn-icon" class:active={$reviewVoiceEnabled} on:click={toggleVoice}>
            {$reviewVoiceEnabled ? '🔊' : '🔇'}
          </button>
        </div>
      </div>

      <div class="answer-panel">
        {#if showAnswer && lastResult}
          <div class="result-card" class:correct={lastResult.correct} class:incorrect={!lastResult.correct}>
            <div class="result-header">
              {#if lastResult.correct}
                <span class="result-icon">✓</span>
                <span class="result-text">Correct!</span>
              {:else}
                <span class="result-icon">✗</span>
                <span class="result-text">Incorrect</span>
              {/if}
            </div>

            {#if !lastResult.correct && lastResult.expected_move}
              <div class="expected-move">
                <span class="label">Expected:</span>
                <span class="move">{lastResult.expected_move}</span>
              </div>
            {/if}

            {#if lastResult.explanation}
              <p class="explanation">{lastResult.explanation}</p>
            {/if}

            <button class="btn-next" on:click={handleNextCard}>
              Next Card →
            </button>
          </div>
        {:else}
          <div class="prompt-card">
            <h4>Find the best move</h4>
            {#if $currentCard?.prompt}
              <p>{$currentCard.prompt}</p>
            {:else}
              <p>What's the correct move in this position?</p>
            {/if}
          </div>
        {/if}

        <div class="recent-feedback">
          <h4>Recent</h4>
          {#each $reviewFeedback as fb (fb.timestamp)}
            <div class="feedback-item" class:correct={fb.correct} class:incorrect={!fb.correct}>
              <span class="fb-icon">{fb.correct ? '✓' : '✗'}</span>
              <span class="fb-move">{fb.expectedMove}</span>
            </div>
          {/each}
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .review-screen {
    flex: 1;
    display: flex;
    flex-direction: column;
    background: var(--bg-primary);
  }

  /* Start View */
  .start-view {
    flex: 1;
    padding: 24px;
    max-width: 600px;
    margin: 0 auto;
    width: 100%;
  }

  .start-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 24px;
  }

  .start-header h2 {
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

  .stats-card {
    background: var(--bg-secondary);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 24px;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 24px;
  }

  .stat-item {
    text-align: center;
  }

  .stat-value {
    display: block;
    font-size: 2rem;
    font-weight: 700;
    margin-bottom: 4px;
  }

  .stat-value.due {
    color: var(--accent-yellow);
  }

  .stat-value.mastered {
    color: var(--accent-green);
  }

  .stat-label {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .btn-start {
    width: 100%;
    padding: 16px;
    background: var(--accent-blue);
    border: none;
    border-radius: 10px;
    color: white;
    font-size: 1.1rem;
    font-weight: 600;
    cursor: pointer;
  }

  .btn-start:hover {
    background: #2563eb;
  }

  .no-cards {
    text-align: center;
    padding: 24px;
    color: var(--text-secondary);
  }

  .no-cards .hint {
    font-size: 0.875rem;
    color: var(--text-muted);
    margin-top: 8px;
  }

  .leitner-info {
    background: var(--bg-secondary);
    border-radius: 12px;
    padding: 20px;
  }

  .leitner-info h3 {
    font-size: 1rem;
    margin: 0 0 8px;
  }

  .leitner-info > p {
    font-size: 0.875rem;
    color: var(--text-secondary);
    margin: 0 0 16px;
  }

  .leitner-boxes {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 8px;
  }

  .leitner-box {
    background: var(--bg-tertiary);
    border-radius: 8px;
    padding: 12px 8px;
    text-align: center;
    border-top: 3px solid var(--box-color);
  }

  .box-num {
    display: block;
    font-weight: 700;
    font-size: 1.25rem;
    color: var(--box-color);
  }

  .box-interval {
    display: block;
    font-size: 0.65rem;
    color: var(--text-muted);
    margin-top: 4px;
  }

  /* Session View */
  .session-view {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr 320px;
    gap: 0;
    height: calc(100vh - 60px);
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

  .card-info {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }

  .card-type {
    font-size: 0.75rem;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .card-box {
    font-size: 0.7rem;
    padding: 2px 8px;
    border-radius: 10px;
    color: white;
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
    background: var(--accent-blue);
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

  .answer-panel {
    background: var(--bg-secondary);
    border-left: 1px solid var(--border-color);
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .prompt-card,
  .result-card {
    padding: 20px;
    background: var(--bg-tertiary);
    border-radius: 12px;
  }

  .prompt-card h4 {
    margin: 0 0 8px;
    font-size: 1rem;
  }

  .prompt-card p {
    margin: 0;
    color: var(--text-secondary);
  }

  .result-card.correct {
    border: 2px solid var(--accent-green);
    background: rgba(34, 197, 94, 0.1);
  }

  .result-card.incorrect {
    border: 2px solid var(--accent-red);
    background: rgba(239, 68, 68, 0.1);
  }

  .result-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
  }

  .result-icon {
    font-size: 1.5rem;
  }

  .result-card.correct .result-icon {
    color: var(--accent-green);
  }

  .result-card.incorrect .result-icon {
    color: var(--accent-red);
  }

  .result-text {
    font-weight: 600;
    font-size: 1.1rem;
  }

  .expected-move {
    margin-bottom: 12px;
  }

  .expected-move .label {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .expected-move .move {
    font-family: monospace;
    font-size: 1.1rem;
    font-weight: 600;
    margin-left: 8px;
  }

  .explanation {
    font-size: 0.9rem;
    color: var(--text-secondary);
    margin: 0 0 16px;
    line-height: 1.5;
  }

  .btn-next {
    width: 100%;
    padding: 12px;
    background: var(--accent-blue);
    border: none;
    border-radius: 8px;
    color: white;
    font-weight: 600;
    cursor: pointer;
  }

  .recent-feedback {
    flex: 1;
    overflow-y: auto;
  }

  .recent-feedback h4 {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin: 0 0 8px;
  }

  .feedback-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px;
    border-radius: 6px;
    margin-bottom: 4px;
    font-size: 0.85rem;
  }

  .feedback-item.correct {
    background: rgba(34, 197, 94, 0.1);
  }

  .feedback-item.incorrect {
    background: rgba(239, 68, 68, 0.1);
  }

  .fb-icon {
    font-weight: bold;
  }

  .feedback-item.correct .fb-icon {
    color: var(--accent-green);
  }

  .feedback-item.incorrect .fb-icon {
    color: var(--accent-red);
  }

  .fb-move {
    font-family: monospace;
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

  @media (max-width: 900px) {
    .session-view {
      grid-template-columns: 1fr;
      grid-template-rows: 1fr auto;
    }

    .answer-panel {
      border-left: none;
      border-top: 1px solid var(--border-color);
      max-height: 250px;
    }

    .leitner-boxes {
      grid-template-columns: repeat(3, 1fr);
    }
  }
</style>
