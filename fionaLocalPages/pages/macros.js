import { createPlaceholderPage } from './_placeholderPage.js';

export default function createPage(routeInfo) {
  return createPlaceholderPage({
    title: 'Macros',
    subtitle: 'Record and replay workflows',
    icon: 'play',
    description: 'Macros are routed again. The backend already exposes a macros API, so this page can be expanded into a full macro manager without changing navigation.',
    items: [
      { title: 'List endpoint', detail: '/api/v1/macros' },
      { title: 'Run endpoint', detail: '/api/v1/macros/run' },
    ],
    actions: [
      { label: 'Open Terminal', action: 'open-terminal', icon: 'terminal' },
    ],
  });
}
