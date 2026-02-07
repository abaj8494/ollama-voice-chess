<script>
  import { onMount } from 'svelte';
  import { currentScreen, activeModal, navigateTo } from './lib/stores/app.js';
  import { connectionStatus, gameId, gameState, resetGame } from './lib/stores/game.js';
  import { resetTraining } from './lib/stores/training.js';
  import { resetReview } from './lib/stores/review.js';
  import { checkHealth } from './lib/api.js';

  // Screens
  import SetupScreen from './lib/screens/SetupScreen.svelte';
  import GameScreen from './lib/screens/GameScreen.svelte';
  import TrainingScreen from './lib/screens/TrainingScreen.svelte';
  import ReviewScreen from './lib/screens/ReviewScreen.svelte';

  // Modals
  import GameOverModal from './lib/modals/GameOverModal.svelte';
  import TrainingModal from './lib/modals/TrainingModal.svelte';
  import ReviewModal from './lib/modals/ReviewModal.svelte';
  import ConfirmModal from './lib/modals/ConfirmModal.svelte';

  let serverStatus = 'checking';

  // Confirmation dialog state
  let showLeaveGameConfirm = false;
  let showDeletePgnConfirm = false;

  onMount(async () => {
    try {
      await checkHealth();
      serverStatus = 'connected';
    } catch (e) {
      serverStatus = 'error';
    }
  });

  // Show WebSocket status only during game, otherwise show server status
  $: showWebSocket = $currentScreen === 'game';
  $: statusConnected = showWebSocket ? $connectionStatus === 'connected' : serverStatus === 'connected';
  $: statusText = showWebSocket
    ? ($connectionStatus === 'connected' ? 'Connected' : 'Disconnected')
    : (serverStatus === 'connected' ? 'Server Ready' : 'Server Offline');

  // Check if we're in a game that's not over
  $: isInActiveGame = $currentScreen === 'game' && $gameId && !$gameState.isGameOver;

  function handleHomeClick() {
    if ($currentScreen === 'setup') {
      return; // Already home
    }

    if (isInActiveGame) {
      showLeaveGameConfirm = true;
    } else {
      goHome();
    }
  }

  function handleLeaveGameConfirm() {
    showLeaveGameConfirm = false;
    showDeletePgnConfirm = true;
  }

  function handleLeaveGameCancel() {
    showLeaveGameConfirm = false;
  }

  async function handleDeletePgnConfirm() {
    showDeletePgnConfirm = false;

    // Delete the backup PGN
    if ($gameId) {
      try {
        await fetch(`/api/game/${$gameId}/delete`, { method: 'DELETE' });
      } catch (e) {
        console.error('Failed to delete PGN:', e);
      }
    }

    goHome();
  }

  function handleDeletePgnCancel() {
    showDeletePgnConfirm = false;
    goHome();
  }

  function goHome() {
    // Reset all state
    resetGame();
    resetTraining();
    resetReview();
    navigateTo('setup');
  }
</script>

<div class="app">
  <header class="header">
    <button class="home-link" on:click={handleHomeClick}>
      <span class="logo">♔</span>
      <span class="title">Voice Chess</span>
    </button>
    <div class="header-status">
      <div class="connection-status">
        <span class="connection-dot" class:connected={statusConnected}></span>
        <span class="connection-text">{statusText}</span>
      </div>
    </div>
  </header>

  <main class="main">
    {#if $currentScreen === 'setup'}
      <SetupScreen />
    {:else if $currentScreen === 'game'}
      <GameScreen />
    {:else if $currentScreen === 'training'}
      <TrainingScreen />
    {:else if $currentScreen === 'review'}
      <ReviewScreen />
    {/if}
  </main>

  <!-- Modals -->
  {#if $activeModal === 'gameOver'}
    <GameOverModal />
  {:else if $activeModal === 'training'}
    <TrainingModal />
  {:else if $activeModal === 'review'}
    <ReviewModal />
  {/if}

  <!-- Confirmation dialogs -->
  {#if showLeaveGameConfirm}
    <ConfirmModal
      title="Leave Game?"
      message="You have a game in progress. Are you sure you want to leave?"
      confirmText="Leave Game"
      cancelText="Continue Playing"
      confirmDanger={true}
      on:confirm={handleLeaveGameConfirm}
      on:cancel={handleLeaveGameCancel}
    />
  {/if}

  {#if showDeletePgnConfirm}
    <ConfirmModal
      title="Delete Game Backup?"
      message="Do you want to delete the saved PGN file for this game?"
      confirmText="Delete Backup"
      cancelText="Keep Backup"
      confirmDanger={true}
      on:confirm={handleDeletePgnConfirm}
      on:cancel={handleDeletePgnCancel}
    />
  {/if}
</div>

<style>
  .app {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 20px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
  }

  .home-link {
    display: flex;
    align-items: center;
    gap: 8px;
    background: none;
    border: none;
    color: var(--text-primary);
    font-size: 1.25rem;
    font-weight: 600;
    cursor: pointer;
    padding: 4px 8px;
    margin: -4px -8px;
    border-radius: 8px;
    transition: background 0.2s;
  }

  .home-link:hover {
    background: var(--bg-tertiary);
  }

  .logo {
    font-size: 1.5rem;
  }

  .header-status {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .connection-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .connection-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent-red);
    transition: background 0.2s;
  }

  .connection-dot.connected {
    background: var(--accent-green);
  }

  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
</style>
