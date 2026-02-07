<script>
  import { createEventDispatcher } from 'svelte';
  import Modal from '../components/Modal.svelte';

  export let title = 'Confirm';
  export let message = 'Are you sure?';
  export let confirmText = 'Yes';
  export let cancelText = 'Cancel';
  export let confirmDanger = false;

  const dispatch = createEventDispatcher();

  function handleConfirm() {
    dispatch('confirm');
  }

  function handleCancel() {
    dispatch('cancel');
  }
</script>

<Modal {title} showClose={false}>
  <div class="confirm-body">
    <p class="message">{message}</p>

    <div class="actions">
      <button class="btn-cancel" on:click={handleCancel}>
        {cancelText}
      </button>
      <button
        class="btn-confirm"
        class:danger={confirmDanger}
        on:click={handleConfirm}
      >
        {confirmText}
      </button>
    </div>
  </div>
</Modal>

<style>
  .confirm-body {
    text-align: center;
  }

  .message {
    color: var(--text-secondary);
    margin: 0 0 24px;
    line-height: 1.5;
  }

  .actions {
    display: flex;
    gap: 12px;
  }

  .btn-cancel,
  .btn-confirm {
    flex: 1;
    padding: 12px 20px;
    border-radius: 8px;
    font-size: 0.95rem;
    font-weight: 500;
    cursor: pointer;
    border: none;
  }

  .btn-cancel {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }

  .btn-cancel:hover {
    background: var(--bg-primary);
  }

  .btn-confirm {
    background: var(--accent-blue);
    color: white;
  }

  .btn-confirm:hover {
    background: #2563eb;
  }

  .btn-confirm.danger {
    background: var(--accent-red);
  }

  .btn-confirm.danger:hover {
    background: #dc2626;
  }
</style>
