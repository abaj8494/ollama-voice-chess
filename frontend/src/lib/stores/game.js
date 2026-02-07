import { writable, derived } from 'svelte/store';

// Game state
export const gameState = writable({
  fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
  turn: 'white',
  playerColor: 'white',
  legalMoves: [],
  legalMovesSan: [],
  moveHistory: [],
  isCheck: false,
  isCheckmate: false,
  isStalemate: false,
  isGameOver: false,
  result: null,
});

// Selected square for click-to-move
export const selectedSquare = writable(null);

// Legal moves for the selected piece
export const legalMovesForSelected = writable([]);

// Last move made
export const lastMove = writable(null);

// Connection status
export const connectionStatus = writable('disconnected');

// WebSocket instance
export const websocket = writable(null);

// Game session ID
export const gameId = writable(null);

// Settings
export const settings = writable({
  difficulty: 'intermediate',
  model: 'gemma3:4b',
  voice: 'en-AU-WilliamNeural',
  voiceEnabled: true,
  alwaysOnMic: false,
});

// Derived: is it player's turn?
export const isPlayerTurn = derived(
  gameState,
  $gameState => $gameState.turn === $gameState.playerColor
);

// Derived: check square (king position if in check)
export const checkSquare = derived(
  gameState,
  $gameState => {
    if (!$gameState.isCheck) return null;
    // Find the king that's in check
    // This would need to parse FEN - for now return null
    return null;
  }
);

// Reset game state
export function resetGame() {
  gameState.set({
    fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
    turn: 'white',
    playerColor: 'white',
    legalMoves: [],
    legalMovesSan: [],
    moveHistory: [],
    isCheck: false,
    isCheckmate: false,
    isStalemate: false,
    isGameOver: false,
    result: null,
  });
  selectedSquare.set(null);
  legalMovesForSelected.set([]);
  lastMove.set(null);
}

// Update game state from server response
export function updateGameState(data) {
  gameState.update(state => ({
    ...state,
    fen: data.fen || state.fen,
    turn: data.turn || state.turn,
    legalMoves: data.legal_moves || state.legalMoves,
    legalMovesSan: data.legal_moves_san || state.legalMovesSan,
    moveHistory: data.moves || state.moveHistory,
    isCheck: data.is_check || false,
    isCheckmate: data.is_checkmate || false,
    isStalemate: data.is_stalemate || false,
    isGameOver: data.is_game_over || false,
    result: data.result || state.result,
  }));
}
