import { useState } from 'react';

type TelegramWebAppUser = {
  id?: number;
  username?: string;
};

type TelegramWebApp = {
  initDataUnsafe?: { user?: TelegramWebAppUser };
  openTelegramLink?: (url: string) => void;
};

type TelegramWindow = Window & {
  Telegram?: { WebApp?: TelegramWebApp };
};

export interface TelegramUser {
  id: number;
  username: string | null;
}

function getWebApp(): TelegramWebApp | undefined {
  if (typeof window === 'undefined') return undefined;
  return (window as TelegramWindow).Telegram?.WebApp;
}

function readUser(): TelegramUser | null {
  const user = getWebApp()?.initDataUnsafe?.user;
  if (user && typeof user.id === 'number') {
    return { id: user.id, username: user.username ?? null };
  }
  try {
    if (typeof window === 'undefined') return null;
    const initData = window.sessionStorage.getItem('sh_init_data');
    if (!initData) return null;
    const rawUser = new URLSearchParams(initData).get('user');
    if (!rawUser) return null;
    const parsed = JSON.parse(rawUser) as TelegramWebAppUser | null;
    if (!parsed || typeof parsed.id !== 'number') return null;
    return { id: parsed.id, username: parsed.username ?? null };
  } catch {
    return null;
  }
}

export function useTelegramUserId(): number | null {
  const [userId] = useState<number | null>(() => readUser()?.id ?? null);
  return userId;
}

export function useTelegramUser(): TelegramUser | null {
  const [user] = useState<TelegramUser | null>(readUser);
  return user;
}
