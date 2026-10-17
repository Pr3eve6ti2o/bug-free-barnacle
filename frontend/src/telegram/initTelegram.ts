type HapticKind = 'tap' | 'success' | 'error';

// Loose, module-scoped cast of the Telegram WebApp bridge. Deliberately kept
// local instead of augmenting the global `Window` interface, so it can never
// clash with whatever ambient typings the app already ships.
type TelegramWebApp = {
  ready?: () => void;
  expand?: () => void;
  disableVerticalSwipes?: () => void;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
  initDataUnsafe?: { start_param?: string | number };
  HapticFeedback?: {
    impactOccurred?: (style: string) => void;
    notificationOccurred?: (type: string) => void;
  };
};

const BG_COLOR = '#06070c';

const webApp: TelegramWebApp | undefined =
  typeof window !== 'undefined' ? (window as any).Telegram?.WebApp : undefined;

if (webApp) {
  webApp.ready?.();
  webApp.expand?.();
  webApp.disableVerticalSwipes?.();
  webApp.setHeaderColor?.(BG_COLOR);
  webApp.setBackgroundColor?.(BG_COLOR);

  const startParam = webApp.initDataUnsafe?.start_param;
  if (startParam != null && /^\d+$/.test(String(startParam))) {
    try {
      sessionStorage.setItem('sh_start_param', String(startParam));
    } catch {
      // private mode / blocked storage — nothing to do
    }
  }
}

export function haptic(kind: HapticKind): void {
  try {
    const feedback =
      typeof window !== 'undefined'
        ? (window as any).Telegram?.WebApp?.HapticFeedback
        : undefined;
    if (!feedback) return;

    if (kind === 'tap') {
      feedback.impactOccurred?.('light');
    } else {
      feedback.notificationOccurred?.(kind);
    }
  } catch {
    // haptics are best-effort only
  }
}
