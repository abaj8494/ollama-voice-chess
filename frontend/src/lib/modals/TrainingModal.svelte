<script>
  import { onMount } from 'svelte';
  import Modal from '../components/Modal.svelte';
  import { closeModal, navigateTo } from '../stores/app.js';
  import { currentOpening } from '../stores/training.js';
  import { getOpenings, startTraining } from '../api.js';

  let openings = [];
  let loading = true;
  let error = null;

  onMount(async () => {
    try {
      const data = await getOpenings();
      openings = data.openings || [];
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  });

  function handleClose() {
    closeModal();
  }

  async function handleSelectOpening(opening) {
    closeModal();
    currentOpening.set(opening);
    navigateTo('training');
  }

  function handleStartTraining() {
    closeModal();
    navigateTo('training');
  }
</script>

<Modal title="Train Openings" on:close={handleClose}>
  <div class="modal-body">
    <p class="description">
      Select an opening to practice. Click any opening below to start training.
    </p>

    {#if loading}
      <div class="loading">Loading openings...</div>
    {:else if error}
      <div class="error">{error}</div>
    {:else}
      <div class="opening-list">
        {#each openings as opening}
          <button
            class="opening-item"
            class:white={opening.color === 'white'}
            class:black={opening.color === 'black'}
            on:click={() => handleSelectOpening(opening)}
          >
            <span class="name">{opening.name}</span>
            <span class="color-tag">{opening.color}</span>
          </button>
        {/each}
      </div>
    {/if}

    <button class="btn-browse" on:click={handleStartTraining}>
      Browse All Openings
    </button>
  </div>
</Modal>

<style>
  .modal-body {
    text-align: center;
  }

  .description {
    color: var(--text-secondary);
    margin: 0 0 20px;
    line-height: 1.5;
  }

  .loading, .error {
    padding: 20px;
    color: var(--text-muted);
  }

  .error {
    color: var(--accent-red);
  }

  .opening-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 20px;
  }

  .opening-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 16px;
    background: var(--bg-tertiary);
    border: 1px solid transparent;
    border-radius: 8px;
    font-size: 0.95rem;
    color: var(--text-primary);
    cursor: pointer;
    transition: all 0.2s;
    width: 100%;
    text-align: left;
  }

  .opening-item:hover {
    background: var(--bg-primary);
    border-color: var(--accent-green);
  }

  .opening-item.white {
    border-left: 3px solid #f8fafc;
  }

  .opening-item.black {
    border-left: 3px solid #64748b;
  }

  .name {
    font-weight: 500;
  }

  .color-tag {
    font-size: 0.7rem;
    color: var(--text-muted);
    text-transform: uppercase;
    background: var(--bg-secondary);
    padding: 2px 8px;
    border-radius: 4px;
  }

  .btn-browse {
    width: 100%;
    padding: 12px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 0.9rem;
    cursor: pointer;
  }

  .btn-browse:hover {
    background: var(--bg-tertiary);
  }
</style>
