<script>
  import Modal from '../components/Modal.svelte';
  import { closeModal, navigateTo } from '../stores/app.js';
  import { gameState, resetGame } from '../stores/game.js';

  $: result = $gameState.result;
  $: isWin = result === 'win';
  $: isLoss = result === 'loss';
  $: isDraw = result === 'draw';

  $: title = isWin ? 'Victory!' : isLoss ? 'Defeat' : 'Draw';
  $: emoji = isWin ? '🎉' : isLoss ? '😔' : '🤝';

  function handleNewGame() {
    resetGame();
    closeModal();
    navigateTo('setup');
  }

  function handleClose() {
    closeModal();
  }
</script>

<Modal title="Game Over" showClose={true} on:close={handleClose}>
  <div class="game-over-content">
    <div class="result-display">
      <span class="emoji">{emoji}</span>
      <h3 class="result-title" class:win={isWin} class:loss={isLoss} class:draw={isDraw}>
        {title}
      </h3>
    </div>

    {#if $gameState.isCheckmate}
      <p class="result-reason">Checkmate</p>
    {:else if $gameState.isStalemate}
      <p class="result-reason">Stalemate</p>
    {:else if isDraw}
      <p class="result-reason">Draw by agreement</p>
    {/if}

    <div class="actions">
      <button class="btn btn-primary" on:click={handleNewGame}>
        New Game
      </button>
      <button class="btn btn-secondary" on:click={handleClose}>
        Review Position
      </button>
    </div>
  </div>
</Modal>

<style>
  .game-over-content {
    text-align: center;
  }

  .result-display {
    margin-bottom: 16px;
  }

  .emoji {
    font-size: 4rem;
    display: block;
    margin-bottom: 8px;
  }

  .result-title {
    font-size: 2rem;
    font-weight: 700;
    margin: 0;
  }

  .result-title.win {
    color: var(--accent-green);
  }

  .result-title.loss {
    color: var(--accent-red);
  }

  .result-title.draw {
    color: var(--accent-yellow);
  }

  .result-reason {
    color: var(--text-secondary);
    margin-bottom: 24px;
  }

  .actions {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .btn {
    width: 100%;
    padding: 14px;
    border-radius: 10px;
    border: none;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
  }

  .btn-primary {
    background: var(--accent-blue);
    color: white;
  }

  .btn-primary:hover {
    background: #2563eb;
  }

  .btn-secondary {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }

  .btn-secondary:hover {
    background: var(--bg-primary);
  }
</style>
