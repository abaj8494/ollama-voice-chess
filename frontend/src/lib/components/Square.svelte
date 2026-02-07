<script>
  import { createEventDispatcher } from 'svelte';

  export let square = '';
  export let light = true;
  export let selected = false;
  export let isLegalMove = false;
  export let isCapture = false;
  export let isLastMove = false;
  export let isCheck = false;

  const dispatch = createEventDispatcher();

  function handleClick() {
    dispatch('click', { square });
  }

  function handleDragOver(e) {
    e.preventDefault();
  }

  function handleDrop(e) {
    e.preventDefault();
    dispatch('drop', { square });
  }

  $: bgColor = (() => {
    if (isCheck) return 'var(--accent-red)';
    if (selected) return 'var(--square-selected)';
    if (isLastMove) return light ? 'var(--square-last-move-light)' : 'var(--square-last-move-dark)';
    return light ? 'var(--square-light)' : 'var(--square-dark)';
  })();
</script>

<div
  class="square"
  style="background-color: {bgColor}"
  on:click={handleClick}
  on:dragover={handleDragOver}
  on:drop={handleDrop}
  role="button"
  tabindex="0"
  on:keydown={(e) => e.key === 'Enter' && handleClick()}
>
  <slot />

  {#if isLegalMove}
    <div class="move-indicator" class:capture={isCapture}></div>
  {/if}
</div>

<style>
  .square {
    aspect-ratio: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    cursor: pointer;
    user-select: none;
  }

  .move-indicator {
    position: absolute;
    width: 30%;
    height: 30%;
    border-radius: 50%;
    background-color: var(--move-dot-empty);
    pointer-events: none;
  }

  .move-indicator.capture {
    width: 100%;
    height: 100%;
    background: transparent;
    border: 5px solid var(--move-dot-capture);
    border-radius: 50%;
    box-sizing: border-box;
  }
</style>
