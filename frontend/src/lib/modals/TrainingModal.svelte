<script>
  import Modal from '../components/Modal.svelte';
  import { closeModal, navigateTo } from '../stores/app.js';

  function handleClose() {
    closeModal();
  }

  function handleStartTraining() {
    closeModal();
    navigateTo('training');
  }
</script>

<Modal title="Train Openings" on:close={handleClose}>
  <div class="modal-body">
    <p class="description">
      Practice your opening repertoire with guided hints. Master 5 key openings through progressive practice.
    </p>

    <div class="opening-preview">
      <div class="opening-item white">
        <span class="name">London System</span>
        <span class="color">White</span>
      </div>
      <div class="opening-item white">
        <span class="name">Queen's Gambit</span>
        <span class="color">White</span>
      </div>
      <div class="opening-item black">
        <span class="name">Caro-Kann Defense</span>
        <span class="color">Black</span>
      </div>
      <div class="opening-item black">
        <span class="name">Scandinavian Defense</span>
        <span class="color">Black</span>
      </div>
      <div class="opening-item black">
        <span class="name">King's Indian Defense</span>
        <span class="color">Black</span>
      </div>
    </div>

    <button class="btn-primary" on:click={handleStartTraining}>
      Start Training
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

  .opening-preview {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 24px;
  }

  .opening-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 14px;
    background: var(--bg-tertiary);
    border-radius: 8px;
    font-size: 0.9rem;
  }

  .opening-item.white {
    border-left: 3px solid #f8fafc;
  }

  .opening-item.black {
    border-left: 3px solid #1e293b;
  }

  .name {
    font-weight: 500;
  }

  .color {
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: uppercase;
  }

  .btn-primary {
    width: 100%;
    padding: 14px;
    background: var(--accent-green);
    border: none;
    border-radius: 10px;
    color: white;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
  }

  .btn-primary:hover {
    background: #16a34a;
  }
</style>
