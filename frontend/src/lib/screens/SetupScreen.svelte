<script>
  import { onMount } from 'svelte';
  import { navigateTo, openModal } from '../stores/app.js';
  import { settings, gameState, gameId, connectionStatus } from '../stores/game.js';
  import { getModels, getVoices, getPlayerStats, startGame } from '../api.js';

  let models = [];
  let voices = [];
  let stats = { wins: 0, losses: 0, draws: 0 };
  let loading = false;
  let error = null;

  // Form values bound to settings
  let selectedColor = 'white';
  let selectedDifficulty = 'intermediate';
  let selectedModel = '';
  let selectedVoice = '';

  const difficulties = [
    { value: 'beginner', label: 'Beginner (800)' },
    { value: 'easy', label: 'Easy (1000)' },
    { value: 'intermediate', label: 'Intermediate (1200)' },
    { value: 'advanced', label: 'Advanced (1400)' },
    { value: 'expert', label: 'Expert (1600)' },
    { value: 'master', label: 'Master (1800)' },
  ];

  onMount(async () => {
    try {
      // Load models, voices, and stats in parallel
      const [modelsData, voicesData, statsData] = await Promise.all([
        getModels().catch(() => ({ models: [] })),
        getVoices().catch(() => ({ voices: [] })),
        getPlayerStats().catch(() => ({ wins: 0, losses: 0, draws: 0 })),
      ]);

      models = modelsData.models || [];
      voices = voicesData.voices || [];
      stats = statsData;

      // Set defaults
      if (models.length > 0) selectedModel = models[0];
      if (voices.length > 0) selectedVoice = voices[0].key;
    } catch (e) {
      error = e.message;
    }
  });

  async function handleStartGame() {
    loading = true;
    error = null;

    try {
      const result = await startGame(selectedColor, selectedDifficulty, selectedModel, selectedVoice);

      gameId.set(result.game_id);
      gameState.update(state => ({
        ...state,
        playerColor: selectedColor,
        fen: result.state.fen,
        turn: result.state.turn,
        legalMoves: result.state.legal_moves || [],
        legalMovesSan: result.state.legal_moves_san || [],
      }));

      settings.update(s => ({
        ...s,
        difficulty: selectedDifficulty,
        model: selectedModel,
        voice: selectedVoice,
      }));

      navigateTo('game');
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function handleTrainClick() {
    openModal('training');
  }

  function handleReviewClick() {
    openModal('review');
  }
</script>

<div class="setup-screen">
  <div class="setup-card">
    <h2>Voice Chess</h2>

    {#if error}
      <div class="error-msg">{error}</div>
    {/if}

    <div class="form-group">
      <label for="difficulty">Difficulty</label>
      <select id="difficulty" bind:value={selectedDifficulty}>
        {#each difficulties as diff}
          <option value={diff.value}>{diff.label}</option>
        {/each}
      </select>
    </div>

    <div class="form-group">
      <label for="model">AI Model</label>
      <select id="model" bind:value={selectedModel}>
        {#if models.length === 0}
          <option value="">Loading models...</option>
        {:else}
          {#each models as model}
            <option value={model}>{model}</option>
          {/each}
        {/if}
      </select>
    </div>

    <div class="form-group">
      <label for="voice">Voice</label>
      <select id="voice" bind:value={selectedVoice}>
        {#if voices.length === 0}
          <option value="">Loading voices...</option>
        {:else}
          {#each voices as voice}
            <option value={voice.key}>{voice.name}</option>
          {/each}
        {/if}
      </select>
    </div>

    <div class="form-group">
      <label>Play as</label>
      <div class="color-picker">
        <button
          class="color-btn white"
          class:selected={selectedColor === 'white'}
          on:click={() => selectedColor = 'white'}
        >
          <span class="piece">♔</span>
          <span>White</span>
        </button>
        <button
          class="color-btn black"
          class:selected={selectedColor === 'black'}
          on:click={() => selectedColor = 'black'}
        >
          <span class="piece">♚</span>
          <span>Black</span>
        </button>
      </div>
    </div>

    <div class="stats-display">
      <div class="stats-row">
        <span class="label">Record (W/L/D)</span>
        <span class="value">{stats.wins}/{stats.losses}/{stats.draws}</span>
      </div>
    </div>

    <button
      class="btn btn-primary start-btn"
      on:click={handleStartGame}
      disabled={loading || !selectedModel}
    >
      {loading ? 'Starting...' : 'Start New Game'}
    </button>

    <div class="action-buttons">
      <button class="btn btn-success" on:click={handleTrainClick}>
        Train Openings
      </button>
      <button class="btn btn-purple" on:click={handleReviewClick}>
        Review
      </button>
    </div>
  </div>
</div>

<style>
  .setup-screen {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }

  .setup-card {
    background: var(--bg-secondary);
    border-radius: 16px;
    padding: 32px;
    max-width: 480px;
    width: 100%;
    border: 1px solid var(--border-color);
  }

  .setup-card h2 {
    text-align: center;
    margin-bottom: 24px;
    font-size: 1.5rem;
  }

  .error-msg {
    background: rgba(239, 68, 68, 0.2);
    color: #fca5a5;
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 16px;
    font-size: 0.875rem;
    text-align: center;
  }

  .form-group {
    margin-bottom: 20px;
  }

  .form-group label {
    display: block;
    margin-bottom: 8px;
    font-weight: 500;
    color: var(--text-secondary);
    font-size: 0.875rem;
  }

  .color-picker {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .color-btn {
    padding: 16px;
    border-radius: 12px;
    border: 2px solid transparent;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
  }

  .color-btn.white {
    background: #f8fafc;
    color: #1e293b;
  }

  .color-btn.black {
    background: #1e293b;
    color: #f8fafc;
    border-color: var(--border-color);
  }

  .color-btn:hover {
    transform: scale(1.02);
  }

  .color-btn.selected {
    border-color: var(--accent-blue);
    box-shadow: 0 0 20px rgba(59, 130, 246, 0.3);
  }

  .color-btn .piece {
    font-size: 2rem;
  }

  .stats-display {
    background: var(--bg-primary);
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 16px;
  }

  .stats-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .stats-row .label {
    color: var(--text-secondary);
    font-size: 0.875rem;
  }

  .stats-row .value {
    font-weight: 600;
    font-size: 1.1rem;
  }

  .start-btn {
    width: 100%;
    padding: 14px;
    font-size: 1rem;
  }

  .action-buttons {
    display: flex;
    gap: 8px;
    margin-top: 16px;
  }

  .action-buttons button {
    flex: 1;
    padding: 12px;
  }
</style>
