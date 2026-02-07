<script>
  import { createEventDispatcher } from 'svelte';
  import { ANNOTATION_COLORS } from '../stores/annotations.js';

  export let square = '';
  export let light = true;
  export let selected = false;
  export let isLegalMove = false;
  export let isCapture = false;
  export let isLastMove = false;
  export let isCheck = false;
  export let highlightColor = null;

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

  function handleContextMenu(e) {
    e.preventDefault();
    dispatch('rightclick', { square });
  }

  function handleMouseUp(e) {
    if (e.button === 2) {
      dispatch('rightup', { square });
    }
  }

  function handleMouseEnter() {
    dispatch('mouseenter', { square });
  }

  $: bgColor = (() => {
    if (isCheck) return 'var(--accent-red)';
    if (selected) return 'var(--square-selected)';
    if (isLastMove) return light ? 'var(--square-last-move-light)' : 'var(--square-last-move-dark)';
    return light ? 'var(--square-light)' : 'var(--square-dark)';
  })();

  $: highlightStyle = highlightColor && ANNOTATION_COLORS[highlightColor]
    ? `background-color: ${ANNOTATION_COLORS[highlightColor].fill};`
    : '';
</script>

<div
  class="square"
  style="background-color: {bgColor}"
  on:click={handleClick}
  on:dragover={handleDragOver}
  on:drop={handleDrop}
  on:contextmenu={handleContextMenu}
  on:mouseup={handleMouseUp}
  on:mouseenter={handleMouseEnter}
  role="button"
  tabindex="0"
  on:keydown={(e) => e.key === 'Enter' && handleClick()}
>
  {#if highlightColor}
    <div class="highlight-overlay" style={highlightStyle}></div>
  {/if}

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

  .highlight-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 1;
  }

  .move-indicator {
    position: absolute;
    width: 30%;
    height: 30%;
    border-radius: 50%;
    background-color: var(--move-dot-empty);
    pointer-events: none;
    z-index: 2;
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
