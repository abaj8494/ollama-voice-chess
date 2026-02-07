// API base URL - in dev, Vite proxy handles this
const API_BASE = '';

// Generic fetch wrapper
async function fetchApi(endpoint, options = {}) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// Health check
export async function checkHealth() {
  return fetchApi('/api/health');
}

// Get available models
export async function getModels() {
  return fetchApi('/api/models');
}

// Get available voices
export async function getVoices() {
  return fetchApi('/api/voices');
}

// Get player stats
export async function getPlayerStats() {
  return fetchApi('/api/stats');
}

// Start a new game
export async function startGame(playerColor, difficulty, model, voice) {
  return fetchApi('/api/game/new', {
    method: 'POST',
    body: JSON.stringify({
      player_color: playerColor,
      difficulty,
      model,
      voice,
    }),
  });
}

// Get game state
export async function getGameState(gameId) {
  return fetchApi(`/api/game/${gameId}/state`);
}

// Text-to-speech
export async function speak(text) {
  const response = await fetch(`${API_BASE}/api/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });

  if (response.ok) {
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    await audio.play();
    return audio;
  }
  return null;
}

// === Training API ===

export async function getOpenings() {
  return fetchApi('/api/openings');
}

export async function getTrainingStats() {
  return fetchApi('/api/training/stats');
}

export async function startTraining(openingId) {
  return fetchApi('/api/training/start', {
    method: 'POST',
    body: JSON.stringify({ opening_id: openingId }),
  });
}

export async function submitTrainingMove(sessionId, move) {
  return fetchApi(`/api/training/${sessionId}/move`, {
    method: 'POST',
    body: JSON.stringify({ move }),
  });
}

export async function completeTraining(sessionId) {
  return fetchApi(`/api/training/${sessionId}/complete`, {
    method: 'POST',
  });
}

// === Review API ===

export async function getReviewStats() {
  return fetchApi('/api/review/stats');
}

export async function getDueCards(limit = 20) {
  return fetchApi(`/api/review/due?limit=${limit}`);
}

export async function startReview(cardLimit = 20) {
  return fetchApi('/api/review/start', {
    method: 'POST',
    body: JSON.stringify({ card_limit: cardLimit }),
  });
}

export async function submitReviewAnswer(sessionId, move) {
  return fetchApi(`/api/review/${sessionId}/answer`, {
    method: 'POST',
    body: JSON.stringify({ move }),
  });
}

export async function skipReviewCard(sessionId) {
  return fetchApi(`/api/review/${sessionId}/skip`, {
    method: 'POST',
  });
}

export async function completeReview(sessionId) {
  return fetchApi(`/api/review/${sessionId}/complete`, {
    method: 'POST',
  });
}
