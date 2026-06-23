import { createPlaceholderPage } from './_placeholderPage.js';

export default function createPage(routeInfo) {
  return createPlaceholderPage({
    title: 'Vsee',
    subtitle: 'Visual scene editor',
    icon: 'eye',
    description: 'The Vsee route now resolves cleanly. This page is a placeholder for the visual workspace until the rendering and state APIs are hooked up.',
    items: [
      { title: 'Expected API', detail: '/api/v1/vsee/*' },
      { title: 'Current state', detail: 'Placeholder page' },
    ],
    actions: [
      { label: 'Open Config', action: 'open-config', icon: 'gear' },
    ],
  });
}
