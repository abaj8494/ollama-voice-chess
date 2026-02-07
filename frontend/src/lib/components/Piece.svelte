<script>
  import { createEventDispatcher } from 'svelte';

  // Piece format: 'wP', 'bK', etc. (color + piece type)
  export let piece = '';
  export let draggable = true;

  const dispatch = createEventDispatcher();

  // Map piece codes to asset paths
  $: pieceAsset = piece ? `/pieces/${piece.toLowerCase()}.png` : null;

  function handleDragStart(e) {
    if (!draggable) {
      e.preventDefault();
      return;
    }
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', piece);
    dispatch('dragstart', { piece });
  }

  function handleDragEnd(e) {
    dispatch('dragend', { piece });
  }
</script>

{#if pieceAsset}
  <img
    src={pieceAsset}
    alt={piece}
    class="piece"
    class:draggable
    draggable={draggable}
    on:dragstart={handleDragStart}
    on:dragend={handleDragEnd}
  />
{/if}

<style>
  .piece {
    width: 85%;
    height: 85%;
    object-fit: contain;
    pointer-events: auto;
    transition: transform 0.1s ease;
  }

  .piece.draggable {
    cursor: grab;
  }

  .piece.draggable:active {
    cursor: grabbing;
    transform: scale(1.1);
  }
</style>
