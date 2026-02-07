import { writable, derived } from 'svelte/store';

// Review session state
export const reviewSession = writable(null);

// Current review card
export const currentCard = writable(null);

// Review feedback messages
export const reviewFeedback = writable([]);

// Voice enabled for review
export const reviewVoiceEnabled = writable(true);

// Review statistics
export const reviewStats = writable({
  dueCount: 0,
  totalCards: 0,
  masteredCount: 0,
});

// Derived: review in progress
export const isReviewing = derived(
  reviewSession,
  $session => $session !== null
);

// Derived: review progress
export const reviewProgress = derived(
  reviewSession,
  $session => {
    if (!$session) return { current: 0, total: 0, percent: 0 };
    const current = $session.current_index || 0;
    const total = $session.total_cards || 1;
    return {
      current,
      total,
      percent: Math.round((current / total) * 100),
    };
  }
);

// Feedback ID counter for unique keys
let feedbackIdCounter = 0;

// Add review feedback
export function addReviewFeedback(correct, expectedMove, explanation) {
  reviewFeedback.update(items => [
    { id: ++feedbackIdCounter, correct, expectedMove, explanation, timestamp: Date.now() },
    ...items.slice(0, 4), // Keep last 5
  ]);
}

// Clear review feedback
export function clearReviewFeedback() {
  reviewFeedback.set([]);
}

// Reset review state
export function resetReview() {
  reviewSession.set(null);
  currentCard.set(null);
  clearReviewFeedback();
}
