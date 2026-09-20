// Touch devices get 44px targets (WCAG 2.5.5) without changing the 32px
// pointer-device buttons the design system specifies.
export const touchTarget =
  '[@media(pointer:coarse)]:h-11 [@media(pointer:coarse)]:px-5';

export const btnSignal = `inline-flex h-8 items-center justify-center rounded-md bg-signal px-3.5 text-button font-medium leading-none text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep ${touchTarget}`;

export const linkClasses =
  'inline-block transition-ui hover:text-signal-bright focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-surface [@media(pointer:coarse)]:py-3';

export const chromeExtensionUrl =
  'https://chromewebstore.google.com/detail/nofmlngkebkapkpjjiieppamfoodkfid?utm_source=item-share-cb';
