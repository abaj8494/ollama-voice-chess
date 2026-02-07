<script>
  import { createEventDispatcher } from 'svelte';

  export let title = '';
  export let showClose = true;

  const dispatch = createEventDispatcher();

  function handleClose() {
    dispatch('close');
  }

  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) {
      handleClose();
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') {
      handleClose();
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

<div class="modal-backdrop" on:click={handleBackdropClick}>
  <div class="modal">
    <div class="modal-header">
      <h2>{title}</h2>
      {#if showClose}
        <button class="close-btn" on:click={handleClose}>✕</button>
      {/if}
    </div>
    <div class="modal-content">
      <slot />
    </div>
  </div>
</div>

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 20px;
  }

  .modal {
    background: var(--bg-secondary);
    border-radius: 16px;
    max-width: 500px;
    width: 100%;
    max-height: 90vh;
    overflow-y: auto;
    border: 1px solid var(--border-color);
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 20px 24px;
    border-bottom: 1px solid var(--border-color);
  }

  .modal-header h2 {
    font-size: 1.25rem;
    font-weight: 600;
    margin: 0;
  }

  .close-btn {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    border: none;
    background: var(--bg-tertiary);
    color: var(--text-secondary);
    font-size: 1rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .close-btn:hover {
    background: var(--accent-red);
    color: white;
  }

  .modal-content {
    padding: 24px;
  }
</style>
