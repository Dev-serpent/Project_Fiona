import { createPlaceholderPage } from './_placeholderPage.js';

export default function createPage(routeInfo) {
  return createPlaceholderPage({
    title: 'Actions',
    subtitle: 'Action runner',
    icon: 'bolt',
    description: 'This page is now wired into the router. Use it to browse and run Fiona actions once the backend action catalog is available.',
    items: [
      { title: 'API endpoint', detail: '/api/v1/actions' },
      { title: 'Run endpoint', detail: '/api/v1/actions/run' },
      { title: 'History endpoint', detail: '/api/v1/actions/history' },
    ],
  });
}
