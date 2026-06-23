import { createPlaceholderPage } from './_placeholderPage.js';

export default function createPage(routeInfo) {
  return createPlaceholderPage({
    title: 'PhiConnect',
    subtitle: 'Secure local messaging',
    icon: 'lock',
    description: 'The PhiConnect route is restored so navigation works, but the dedicated UI for contacts and messages still needs the backend module to be wired in.',
    items: [
      { title: 'Expected API', detail: '/api/v1/phiconnect/*' },
      { title: 'Current state', detail: 'Placeholder page until the handler lands' },
    ],
    actions: [
      { label: 'Open Dashboard', action: 'open-dashboard', icon: 'dashboard' },
    ],
  });
}
