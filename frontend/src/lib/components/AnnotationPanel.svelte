<script>
  import { ANNOTATION_COLORS, annotationColor, annotationsEnabled, clearAnnotations, clearArrows, clearHighlights, arrows, highlights } from '../stores/annotations.js';

  const colorNames = Object.keys(ANNOTATION_COLORS);

  function selectColor(color) {
    annotationColor.set(color);
  }

  function toggleAnnotations() {
    annotationsEnabled.update(v => !v);
  }
</script>

<div class="annotation-panel">
  <div class="panel-header">
    <span class="panel-title">Annotations</span>
    <button
      class="toggle-btn"
      class:active={$annotationsEnabled}
      on:click={toggleAnnotations}
      title={$annotationsEnabled ? 'Disable annotations' : 'Enable annotations'}
    >
      {$annotationsEnabled ? 'ON' : 'OFF'}
    </button>
  </div>

  <div class="color-section">
    <span class="section-label">Color</span>
    <div class="color-picker">
      {#each colorNames as color}
        <button
          class="color-btn"
          class:selected={$annotationColor === color}
          style="background-color: {ANNOTATION_COLORS[color].stroke};"
          on:click={() => selectColor(color)}
          title={color}
          disabled={!$annotationsEnabled}
        ></button>
      {/each}
    </div>
  </div>

  <div class="instructions">
    <span class="section-label">How to use</span>
    <ul>
      <li><strong>Right-click</strong> a square to highlight it</li>
      <li><strong>Right-drag</strong> between squares to draw an arrow</li>
      <li>Same action removes existing annotation</li>
    </ul>
  </div>

  <div class="clear-section">
    <button
      class="clear-btn"
      on:click={clearAnnotations}
      disabled={$arrows.length === 0 && $highlights.length === 0}
    >
      Clear All
    </button>
    <div class="clear-row">
      <button
        class="clear-btn small"
        on:click={clearArrows}
        disabled={$arrows.length === 0}
      >
        Clear Arrows ({$arrows.length})
      </button>
      <button
        class="clear-btn small"
        on:click={clearHighlights}
        disabled={$highlights.length === 0}
      >
        Clear Highlights ({$highlights.length})
      </button>
    </div>
  </div>
</div>

<style>
  .annotation-panel {
    background: var(--surface-secondary);
    border-radius: 8px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .panel-title {
    font-weight: 600;
    color: var(--text-primary);
    font-size: 1rem;
  }

  .toggle-btn {
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
    border: none;
    cursor: pointer;
    background: var(--surface-tertiary);
    color: var(--text-muted);
    transition: all 0.2s;
  }

  .toggle-btn.active {
    background: var(--accent-green);
    color: white;
  }

  .section-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    display: block;
    margin-bottom: 8px;
  }

  .color-picker {
    display: flex;
    gap: 8px;
  }

  .color-btn {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: 3px solid transparent;
    cursor: pointer;
    transition: all 0.2s;
  }

  .color-btn:hover:not(:disabled) {
    transform: scale(1.1);
  }

  .color-btn.selected {
    border-color: white;
    box-shadow: 0 0 0 2px var(--accent-green);
  }

  .color-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .instructions {
    border-top: 1px solid var(--border-color);
    padding-top: 12px;
  }

  .instructions ul {
    margin: 0;
    padding-left: 16px;
    font-size: 0.8rem;
    color: var(--text-secondary);
    line-height: 1.6;
  }

  .instructions li {
    margin-bottom: 4px;
  }

  .instructions strong {
    color: var(--text-primary);
  }

  .clear-section {
    border-top: 1px solid var(--border-color);
    padding-top: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .clear-row {
    display: flex;
    gap: 8px;
  }

  .clear-btn {
    flex: 1;
    padding: 8px 12px;
    border-radius: 4px;
    border: none;
    background: var(--surface-tertiary);
    color: var(--text-secondary);
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.2s;
  }

  .clear-btn:hover:not(:disabled) {
    background: var(--accent-red);
    color: white;
  }

  .clear-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .clear-btn.small {
    font-size: 0.75rem;
    padding: 6px 8px;
  }
</style>
