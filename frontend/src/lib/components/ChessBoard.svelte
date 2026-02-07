<script>
  import { createEventDispatcher } from 'svelte';
  import Square from './Square.svelte';
  import Piece from './Piece.svelte';

  // Props
  export let position = {};          // { a1: 'wR', e1: 'wK', ... } or FEN string
  export let orientation = 'white';  // 'white' or 'black'
  export let interactive = true;     // Allow moves
  export let selectedSquare = null;  // Currently selected square
  export let legalMoves = [];        // Array of legal target squares ['e4', 'd4']
  export let lastMove = null;        // { from: 'e2', to: 'e4' }
  export let checkSquare = null;     // Square where king is in check

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
</script>

<div class="board-container">
  <div class="board" class:flipped={orientation === 'black'}>
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

        <Square
          {square}
          {light}
          selected={isSelected}
          isLegalMove={isLegal}
          isCapture={!!isCapture}
          isLastMove={isLastMoveSquare}
          {isCheck}
          on:click={handleSquareClick}
          on:drop={handleDrop}
        >
          {#if piece && !(isDragging && dragSource === square)}
            <Piece
              {piece}
              draggable={interactive}
              on:dragstart={() => handleDragStart(square, piece)}
              on:dragend={handleDragEnd}
            />
          {/if}
        </Square>
      {/each}
    {/each}
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
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    border: 4px solid var(--board-border);
    border-radius: 4px;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
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
