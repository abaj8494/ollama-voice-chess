import { writable, derived } from 'svelte/store';

// Training session state
export const trainingSession = writable(null);

// Current opening being practiced
export const currentOpening = writable(null);

// Current hint for the player
export const currentHint = writable(null);

// Training messages/feedback
export const trainingMessages = writable([]);

// Voice enabled for training
export const trainingVoiceEnabled = writable(true);

// Available openings
export const openings = writable([]);

// Training statistics
export const trainingStats = writable({
  sessionsToday: 0,
  dailyGoal: 5,
  totalSessions: 0,
  totalMovesPracticed: 0,
});

// Derived: training in progress
export const isTraining = derived(
  trainingSession,
  $session => $session !== null
);

// Derived: training progress
export const trainingProgress = derived(
  trainingSession,
  $session => {
    if (!$session) return { current: 0, total: 0, percent: 0 };
    const current = $session.current_move_index || 0;
    const total = $session.total_moves || 1;
    return {
      current,
      total,
      percent: Math.round((current / total) * 100),
    };
  }
);

// Add a training message
export function addTrainingMessage(type, message) {
  trainingMessages.update(msgs => [
    ...msgs,
    { type, message, timestamp: Date.now() }
  ]);
}

// Clear training messages
export function clearTrainingMessages() {
  trainingMessages.set([]);
}

// Reset training state
export function resetTraining() {
  trainingSession.set(null);
  currentOpening.set(null);
  currentHint.set(null);
  clearTrainingMessages();
}
