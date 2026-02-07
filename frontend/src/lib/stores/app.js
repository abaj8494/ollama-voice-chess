import { writable } from 'svelte/store';

// Current screen/view
export const currentScreen = writable('setup'); // 'setup', 'game', 'training', 'review'

// Modal state
export const activeModal = writable(null); // 'training', 'review', 'loadGame', 'gameOver', 'analysis'

// Navigate to a screen
export function navigateTo(screen) {
  currentScreen.set(screen);
  activeModal.set(null);
}

// Open a modal
export function openModal(modal) {
  activeModal.set(modal);
}

// Close modal
export function closeModal() {
  activeModal.set(null);
}
