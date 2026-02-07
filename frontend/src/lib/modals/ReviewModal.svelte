<script>
  import { onMount } from 'svelte';
  import Modal from '../components/Modal.svelte';
  import { closeModal, navigateTo } from '../stores/app.js';
  import { reviewStats } from '../stores/review.js';
  import { getReviewStats } from '../api.js';

  let loading = true;

  onMount(async () => {
    try {
      const stats = await getReviewStats();
      reviewStats.set(stats);
    } catch (e) {
      console.error('Failed to load review stats:', e);
    } finally {
      loading = false;
    }
  });

  function handleClose() {
    closeModal();
  }

  function handleStartReview() {
    closeModal();
    navigateTo('review');
  }
</script>

<Modal title="Spaced Repetition Review" on:close={handleClose}>
  <div class="modal-body">
    {#if loading}
      <p class="loading">Loading stats...</p>
    {:else}
      <div class="stats-grid">
        <div class="stat">
          <span class="stat-value due">{$reviewStats.dueCount || 0}</span>
          <span class="stat-label">Cards Due</span>
        </div>
        <div class="stat">
          <span class="stat-value">{$reviewStats.totalCards || 0}</span>
          <span class="stat-label">Total</span>
        </div>
        <div class="stat">
          <span class="stat-value mastered">{$reviewStats.masteredCount || 0}</span>
          <span class="stat-label">Mastered</span>
        </div>
      </div>

      <p class="description">
        Review positions using spaced repetition. Correct answers move cards to longer intervals,
        while mistakes return them to daily review.
      </p>

      {#if ($reviewStats.dueCount || 0) > 0}
        <button class="btn-primary" on:click={handleStartReview}>
          Review {$reviewStats.dueCount} Cards
        </button>
      {:else}
        <div class="no-cards">
          <p>No cards due for review today!</p>
          <button class="btn-secondary" on:click={handleClose}>
            Close
          </button>
        </div>
      {/if}
    {/if}
  </div>
</Modal>

<style>
  .modal-body {
    text-align: center;
  }

  .loading {
    color: var(--text-muted);
    padding: 20px;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 20px;
    padding: 16px;
    background: var(--bg-tertiary);
    border-radius: 12px;
  }

  .stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
  }

  .stat-value {
    font-size: 1.75rem;
    font-weight: 700;
  }

  .stat-value.due {
    color: var(--accent-yellow);
  }

  .stat-value.mastered {
    color: var(--accent-green);
  }

  .stat-label {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .description {
    color: var(--text-secondary);
    font-size: 0.9rem;
    line-height: 1.5;
    margin: 0 0 20px;
  }

  .btn-primary {
    width: 100%;
    padding: 14px;
    background: #8b5cf6;
    border: none;
    border-radius: 10px;
    color: white;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
  }

  .btn-primary:hover {
    background: #7c3aed;
  }

  .no-cards {
    padding: 16px;
    background: var(--bg-tertiary);
    border-radius: 12px;
  }

  .no-cards p {
    color: var(--text-secondary);
    margin: 0 0 16px;
  }

  .btn-secondary {
    padding: 12px 24px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    color: var(--text-primary);
    cursor: pointer;
  }
</style>
