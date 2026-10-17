interface TelegramWebApps {
  WebApp: {
    initData: string;
    initDataUnsafe: {
      user?: {
        id?: string;
        username?: string;
        first_name?: string;
        last_name?: string;
      };
    };
    openTelegramLink: (url: string) => void;
    openLink: (url: string) => void;
    HapticFeedback: {
      impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void;
      notificationOccurred: (type: 'error' | 'success' | 'warning') => void;
      selectionChanged: () => void;
    };
  };
}

interface Window {
  Telegram: TelegramWebApps;
}
