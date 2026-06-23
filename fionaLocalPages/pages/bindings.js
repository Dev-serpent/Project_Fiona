import { createPlaceholderPage } from './_placeholderPage.js';

export default function createPage(routeInfo) {
  return createPlaceholderPage({
    title: 'Key Bindings',
    subtitle: 'QuikTieper bindings',
    icon: 'keyboard',
    description: 'This route is present again, but the dedicated bindings UI is not yet implemented in this bundle. The config API still exposes the saved bindings file.',
    items: [
      { title: 'Config file', detail: 'bindings.json' },
      { title: 'Related settings', detail: 'Settings > Keyboard' },
      { title: 'Backend status', detail: 'No dedicated bindings REST handler yet' },
    ],
    actions: [
      { label: 'Open Settings', action: 'open-settings', icon: 'gear' },
    ],
  });
}
