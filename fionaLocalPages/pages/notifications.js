import { createPlaceholderPage } from './_placeholderPage.js';

export default function createPage(routeInfo) {
  return createPlaceholderPage({
    title: 'Notifications',
    subtitle: 'System event center',
    icon: 'bell',
    description: 'This navigation target is fixed, but the dedicated notifications page still needs a backend notifications feed to show live items.',
    items: [
      { title: 'Store slice', detail: 'notifications.items' },
      { title: 'Store slice', detail: 'notifications.unreadCount' },
      { title: 'Expected API', detail: '/api/v1/notifications/*' },
    ],
    actions: [
      { label: 'Open Dashboard', action: 'open-dashboard', icon: 'dashboard' },
    ],
  });
}
