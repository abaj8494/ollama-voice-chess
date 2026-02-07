<script>
  import { onMount } from 'svelte';
  import { currentScreen, activeModal } from './lib/stores/app.js';
  import { connectionStatus } from './lib/stores/game.js';
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

  let healthStatus = 'checking';

  onMount(async () => {
    try {
      await checkHealth();
      healthStatus = 'healthy';
    } catch (e) {
      healthStatus = 'error';
    }
  });
</script>

<div class="app">
  <header class="header">
    <h1>
      <span class="logo">♔</span>
      Voice Chess
    </h1>
    <div class="header-status">
      <div class="connection-status">
        <span class="connection-dot" class:connected={$connectionStatus === 'connected'}></span>
        <span class="connection-text">
          {$connectionStatus === 'connected' ? 'Connected' : 'Disconnected'}
        </span>
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

  .header h1 {
    font-size: 1.25rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0;
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
