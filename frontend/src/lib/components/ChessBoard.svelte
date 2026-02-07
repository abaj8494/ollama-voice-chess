<script>
  import { createEventDispatcher } from 'svelte';
  import Square from './Square.svelte';
  import Piece from './Piece.svelte';
  import { ANNOTATION_COLORS } from '../stores/annotations.js';

  // Props
  export let position = {};          // { a1: 'wR', e1: 'wK', ... } or FEN string
  export let orientation = 'white';  // 'white' or 'black'
  export let interactive = true;     // Allow moves
  export let selectedSquare = null;  // Currently selected square
  export let legalMoves = [];        // Array of legal target squares ['e4', 'd4']
  export let lastMove = null;        // { from: 'e2', to: 'e4' }
  export let checkSquare = null;     // Square where king is in check

  // Annotation props
  export let arrows = [];            // Array of { from, to, color }
  export let highlights = [];        // Array of { square, color }
  export let annotationsEnabled = false;
  export let annotationColor = 'green';

  const dispatch = createEventDispatcher();

  // Convert FEN to position object if needed
  $: positionObj = typeof position === 'string' ? fenToPosition(position) : position;

  // Board files and ranks based on orientation
  $: files = orientation === 'white'
    ? ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
    : ['h', 'g', 'f', 'e', 'd', 'c', 'b', 'a'];

  $: ranks = orientation === 'white'
    ? [8, 7, 6, 5, 4, 3, 2, 1]
    : [1, 2, 3, 4, 5, 6, 7, 8];

  // Track dragging state
  let isDragging = false;
  let dragSource = null;

  // Annotation drawing state
  let isDrawingArrow = false;
  let arrowStart = null;
  let arrowEnd = null;

  // Board element reference for coordinate calculation
  let boardEl;

  function fenToPosition(fen) {
    const pos = {};
    const fenBoard = fen.split(' ')[0];
    const rows = fenBoard.split('/');

    const pieceMap = {
      'p': 'bP', 'n': 'bN', 'b': 'bB', 'r': 'bR', 'q': 'bQ', 'k': 'bK',
      'P': 'wP', 'N': 'wN', 'B': 'wB', 'R': 'wR', 'Q': 'wQ', 'K': 'wK'
    };

    rows.forEach((row, rowIndex) => {
      let colIndex = 0;
      for (const char of row) {
        if (/\d/.test(char)) {
          colIndex += parseInt(char);
        } else {
          const file = String.fromCharCode(97 + colIndex); // 'a' = 97
          const rank = 8 - rowIndex;
          const square = file + rank;
          pos[square] = pieceMap[char];
          colIndex++;
        }
      }
    });

    return pos;
  }

  function isLightSquare(file, rank) {
    const fileIndex = file.charCodeAt(0) - 97; // a=0, b=1, etc.
    return (fileIndex + rank) % 2 === 1;
  }

  function getHighlightColor(square) {
    const highlight = highlights.find(h => h.square === square);
    return highlight ? highlight.color : null;
  }

  function handleSquareClick(e) {
    if (!interactive) return;
    const { square } = e.detail;
    dispatch('squareClick', { square });
  }

  function handleDragStart(square, piece) {
    if (!interactive) return;
    isDragging = true;
    dragSource = square;
    dispatch('dragStart', { square, piece });
  }

  function handleDragEnd() {
    isDragging = false;
    dragSource = null;
  }

  function handleDrop(e) {
    if (!interactive || !dragSource) return;
    const { square: targetSquare } = e.detail;

    if (dragSource !== targetSquare) {
      dispatch('move', { from: dragSource, to: targetSquare });
    }

    isDragging = false;
    dragSource = null;
  }

  // Right-click handling for annotations
  function handleContextMenu(e) {
    if (!annotationsEnabled) return;
    e.preventDefault();
  }

  function handleSquareRightDown(e) {
    if (!annotationsEnabled) return;
    const { square } = e.detail;

    // Start drawing arrow or preparing for highlight
    isDrawingArrow = true;
    arrowStart = square;
    arrowEnd = square;
  }

  function handleSquareRightUp(e) {
    if (!annotationsEnabled || !isDrawingArrow) return;
    const { square } = e.detail;

    if (arrowStart === square) {
      // Same square - toggle highlight
      dispatch('toggleHighlight', { square, color: annotationColor });
    } else {
      // Different square - add arrow
      dispatch('toggleArrow', { from: arrowStart, to: square, color: annotationColor });
    }

    isDrawingArrow = false;
    arrowStart = null;
    arrowEnd = null;
  }

  function handleSquareMouseEnter(square) {
    if (isDrawingArrow) {
      arrowEnd = square;
    }
  }

  // Convert square to SVG coordinates
  function squareToCoords(square) {
    const file = square.charCodeAt(0) - 97; // a=0, h=7
    const rank = parseInt(square[1]) - 1;   // 1=0, 8=7

    let x, y;
    if (orientation === 'white') {
      x = file * 12.5 + 6.25;
      y = (7 - rank) * 12.5 + 6.25;
    } else {
      x = (7 - file) * 12.5 + 6.25;
      y = rank * 12.5 + 6.25;
    }
    return { x, y };
  }

  // Generate arrow path
  function getArrowPath(from, to) {
    const start = squareToCoords(from);
    const end = squareToCoords(to);

    // Shorten the arrow slightly so it doesn't overlap piece
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const len = Math.sqrt(dx * dx + dy * dy);
    const shortenBy = 3; // percentage units

    const endX = end.x - (dx / len) * shortenBy;
    const endY = end.y - (dy / len) * shortenBy;
    const startX = start.x + (dx / len) * 2;
    const startY = start.y + (dy / len) * 2;

    return { startX, startY, endX, endY };
  }
</script>

<div class="board-container" on:contextmenu={handleContextMenu}>
  <div class="board" class:flipped={orientation === 'black'} bind:this={boardEl}>
    {#each ranks as rank}
      {#each files as file}
        {@const square = file + rank}
        {@const piece = positionObj[square]}
        {@const light = isLightSquare(file, rank)}
        {@const isSelected = square === selectedSquare}
        {@const isLegal = legalMoves.includes(square)}
        {@const isLastMoveSquare = lastMove && (lastMove.from === square || lastMove.to === square)}
        {@const isCheck = square === checkSquare}
        {@const isCapture = isLegal && piece}
        {@const highlightColor = getHighlightColor(square)}

        <Square
          {square}
          {light}
          selected={isSelected}
          isLegalMove={isLegal}
          isCapture={!!isCapture}
          isLastMove={isLastMoveSquare}
          {isCheck}
          {highlightColor}
          on:click={handleSquareClick}
          on:drop={handleDrop}
          on:rightdown={handleSquareRightDown}
          on:rightup={handleSquareRightUp}
          on:mouseenter={() => handleSquareMouseEnter(square)}
        >
          {#if piece && !(isDragging && dragSource === square)}
            <Piece
              {piece}
              draggable={interactive}
              on:dragstart={() => handleDragStart(square, piece)}
              on:dragend={handleDragEnd}
              on:rightdown={() => handleSquareRightDown({ detail: { square }})}
              on:rightup={() => handleSquareRightUp({ detail: { square }})}
            />
          {/if}
        </Square>
      {/each}
    {/each}

    <!-- Arrow SVG overlay -->
    <svg class="arrow-layer" viewBox="0 0 100 100" preserveAspectRatio="none">
      <defs>
        {#each Object.entries(ANNOTATION_COLORS) as [colorName, colors]}
          <marker
            id="arrowhead-{colorName}"
            markerWidth="3"
            markerHeight="3"
            refX="1.5"
            refY="1.5"
            orient="auto"
          >
            <polygon points="0 0, 3 1.5, 0 3" fill={colors.fill} />
          </marker>
        {/each}
      </defs>

      <!-- Stored arrows -->
      {#each arrows as arrow}
        {@const path = getArrowPath(arrow.from, arrow.to)}
        {@const colors = ANNOTATION_COLORS[arrow.color] || ANNOTATION_COLORS.green}
        <line
          x1={path.startX}
          y1={path.startY}
          x2={path.endX}
          y2={path.endY}
          stroke={colors.fill}
          stroke-width="1.5"
          stroke-linecap="round"
          marker-end="url(#arrowhead-{arrow.color})"
          class="arrow"
        />
      {/each}

      <!-- Arrow being drawn -->
      {#if isDrawingArrow && arrowStart && arrowEnd && arrowStart !== arrowEnd}
        {@const path = getArrowPath(arrowStart, arrowEnd)}
        {@const colors = ANNOTATION_COLORS[annotationColor] || ANNOTATION_COLORS.green}
        <line
          x1={path.startX}
          y1={path.startY}
          x2={path.endX}
          y2={path.endY}
          stroke={colors.fill}
          stroke-width="1.5"
          stroke-linecap="round"
          marker-end="url(#arrowhead-{annotationColor})"
          class="arrow drawing"
          opacity="0.7"
        />
      {/if}
    </svg>
  </div>

  <!-- File labels -->
  <div class="file-labels">
    {#each files as file}
      <span>{file}</span>
    {/each}
  </div>

  <!-- Rank labels -->
  <div class="rank-labels">
    {#each ranks as rank}
      <span>{rank}</span>
    {/each}
  </div>
</div>

<style>
  .board-container {
    position: relative;
    width: 100%;
    max-width: 520px;
    margin: 0 auto;
  }

  .board {
    position: relative;
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    border: 4px solid var(--board-border);
    border-radius: 4px;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  }

  .arrow-layer {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 10;
  }

  .arrow {
    filter: drop-shadow(1px 1px 1px rgba(0, 0, 0, 0.3));
  }

  .file-labels {
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    padding: 4px 0;
  }

  .file-labels span {
    text-align: center;
    color: var(--text-muted);
    font-size: 0.75rem;
    font-weight: 500;
  }

  .rank-labels {
    position: absolute;
    left: -20px;
    top: 4px;
    bottom: 24px;
    display: flex;
    flex-direction: column;
    justify-content: space-around;
  }

  .rank-labels span {
    color: var(--text-muted);
    font-size: 0.75rem;
    font-weight: 500;
  }
</style>
