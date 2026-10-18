import axios, { AxiosResponse } from 'axios';

// Создаем инстанс axios с базовыми настройками
const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_URL}/api`, // Динамический базовый URL
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach the Telegram-signed initData (when really inside Telegram) so the
// backend can verify identity when SPACEHUNTER_AUTH=on. ONLY on requests to
// our own API (relative URLs): initData is a replayable session credential
// and must never leak to a third-party origin via an absolute URL.
api.interceptors.request.use((config) => {
  const initData = window.Telegram?.WebApp?.initData;
  const url = config.url ?? '';
  const isOwnApi = !/^https?:\/\//i.test(url);
  if (initData && isOwnApi) {
    config.headers['X-Telegram-Init-Data'] = initData;
  }
  return config;
});

// Интерцептор для обработки ответов и извлечения данных
api.interceptors.response.use(
  (response: AxiosResponse) => response.data,
  error => {
    console.error('API Error:', {
      status: error.response?.status,
      statusText: error.response?.statusText,
      data: error.response?.data,
      url: error.config?.url,
      method: error.config?.method,
    });
    return Promise.reject(error.response?.data || error);
  }
);

export interface GameClickResponse {
  message: string;
  reward: number;
  new_score: number;
  balance: number;
  new_balance: number;
  level: number;
  leveled_up: boolean;
  energy: number;
}

export interface GameStateResponse {
  balance: number;
  level: number;
  score: number;
  energy: number;
  boost_multiplier: number;
}

export interface Boost {
  boost_id: number;
  name: string;
  category: string;
  description: string;
  icon_name: string;
  passive_income: number;
  click_multiplier: number;
  level: number;
  max_level: number;
  current_cost: number;
}

export interface UpgradeBoostResponse {
  boost_id: number;
  name: string;
  level: number;
  max_level: number;
  new_balance: number;
  new_cost: number;
  new_passive_income: number;
  new_click_multiplier: number;
}

export interface NFT {
  id: number;
  name: string;
  description: string | null;
  image_path: string;
  category_id: number;
  coins_threshold: number;
}

export interface NFTCategory {
  id: number;
  name: string;
  description: string | null;
  nfts: NFT[];
}

export interface UserNFT {
  user_id: number;
  nft_id: number;
  nft: NFT;
  acquired_at: string;
}

export interface TaskResponse {
  id: number;
  title: string;
  description: string;
  type: 'daily' | 'permanent';
  reward: number;
  condition_value: number;
  condition_type: string;
  reward_type: 'token' | 'multiplier';
  multiplier_pct: number;
  link_url?: string | null;
}

export interface UserTaskResponse {
  id: number;
  task: TaskResponse;
  progress: number;
  is_completed: boolean;
  is_claimed: boolean;
}

export interface DailyBonusStatus {
  current_day: number;
  can_claim: boolean;
  last_claimed: string | null;
  days_streak: number;
  streak?: number;
  next_milestone?: number | null;
  next_milestone_in_days?: number | null;
  resets_in_seconds?: number;
}

export interface DailyBonusResult {
  success: boolean;
  message: string;
  reward_type: string;
  reward_amount: number;
  current_day: number;
  next_day: number;
  can_claim: boolean;
  last_claimed_date: string;
  new_balance: number | null;
}

export interface DailyBonusConfig {
  day: number;
  type: string;
  amount: number;
}

export interface WalletStatus {
  is_connected: boolean;
  address: string | null;
}

// API методы
export const gameApi = {
  click: (telegramId: number | string) => 
    api.post<any, GameClickResponse>(`/game/click?telegram_id=${telegramId}`),
  getGameState: (telegramId: number | string) => 
    api.get<any, GameStateResponse>(`/game/state/${telegramId}`),
  getPassiveIncome: (telegramId: number | string) => 
    api.get<any, { passive_income_rate: number, accumulated_income: number, max_accumulation_time: number, time_accumulated: number }>(`/game/passive_income/${telegramId}`),
  applyReturningIncome: (telegramId: number | string) => 
    api.post<any, { applied_income: number, new_balance: number }>(`/game/apply_returning_income/${telegramId}`),
  applyPassiveIncome: (telegramId: number | string) => 
    api.post<any, { applied_income: number, new_balance: number }>(`/game/apply_passive_income/${telegramId}`),
  getEnergyState: (telegramId: number | string) => 
    api.get<any, { current_energy: number, energy_to_restore: number, max_energy: number }>(`/game/energy/${telegramId}`),
  applyEnergyRestore: (telegramId: number | string) => 
    api.post<any, { new_energy: number, restored_amount: number, max_energy: number }>(`/game/energy/restore/${telegramId}`),
};

export const boostApi = {
  getUserBoosts: (telegramId: number | string) => 
    api.get<any, Boost[]>(`/boosts/user/${telegramId}`),
  upgradeBoost: (telegramId: number | string, boostId: number) => 
    api.post<any, UpgradeBoostResponse>('/boosts/upgrade', { telegram_id: telegramId, boost_id: boostId }),
};

export const taskApi = {
  getUserTasks: (telegramId: number | string) => 
    api.get<any, UserTaskResponse[]>(`/tasks/user/${telegramId}`),
  getTasks: () => 
    api.get<any, TaskResponse[]>('/tasks'),
  checkTask: (telegramId: number | string, taskId: number) =>
    api.post<any, UserTaskResponse>('/tasks/check', { telegram_id: telegramId, task_id: taskId }),
  claimTaskReward: (telegramId: number | string, taskId: number) =>
    api.post<any, { success: boolean; reward?: number; new_balance?: number; task_id?: number; error?: string; reward_type?: string; multiplier_pct?: number; task_boost_pct?: number }>(`/tasks/claim/${telegramId}/${taskId}`),
  checkTasksProgress: (telegramId: number | string) => 
    api.post<any, { success: boolean; completed_tasks: number[] }>(`/tasks/check_progress/${telegramId}`),
  checkDailyReset: (telegramId: number | string) => 
    api.post<any, { success: boolean; was_reset: boolean }>(`/tasks/daily_reset/${telegramId}`),
};

export const userApi = {
  getUser: (telegramId: number | string) => api.get(`/users/${telegramId}`),
  registerUser: (telegramId: number | string, username: string) => 
    api.post('/users/register', { telegram_id: telegramId, username }),
  getUserReferrals: (telegramId: number | string) => 
    api.get<any, any[]>(`/users/referrals/${telegramId}`),
  registerWithReferral: (telegramId: number | string, username: string, refId: number | string) => 
    api.post('/users/register_with_referral', { 
      telegram_id: telegramId, 
      username, 
      ref_id: refId 
    }),
};

export const nftApi = {
  getCategories: () => 
    api.get<any, NFTCategory[]>('/nft/categories'),
  getUserCollection: (telegramId: number | string) => 
    api.get<any, UserNFT[]>(`/nft/user/${telegramId}`),
  getAvailableNFTs: (telegramId: number | string) => 
    api.get<any, NFT[]>(`/nft/available/${telegramId}`),
  autoUnlockNFTs: (telegramId: number | string) => 
    api.post<any, UserNFT[]>(`/nft/auto-unlock/${telegramId}`),
};

export const bonusApi = {
  getDailyBonusStatus: (telegramId: number | string) =>
    api.get<any, DailyBonusStatus>(`/bonus/daily/status/${telegramId}`),
  claimDailyBonus: (telegramId: number | string) =>
    api.post<any, DailyBonusResult>(`/bonus/daily/claim/${telegramId}`),
  getDailyBonusConfig: () =>
    api.get<any, DailyBonusConfig[]>('/bonus/daily/config'),
};

export const walletApi = {
  connectWallet: async (telegramId: number, address: string) => {
    return api.post(`/wallet/${telegramId}/connect`, { address });
  },
  getWalletStatus: async (telegramId: number): Promise<WalletStatus> => {
    try {
      // Добавим проверки и обработку ошибок
      const response = await api.get<any, any>(`/wallet/${telegramId}/status`);
      console.log('Wallet API raw response:', response);
      
      // Если ответ пустой, вернем дефолтное значение
      if (!response) {
        console.warn('Empty response from wallet API, using default values');
        return {
          is_connected: false,
          address: null
        };
      }
      
      // Если ответ есть, но структура неправильная, попробуем исправить
      if (response && typeof response === 'object') {
        const result: WalletStatus = {
          is_connected: response.is_connected === true,
          address: response.address || null
        };
        console.log('Normalized wallet status:', result);
        return result;
      }
      
      // Если ничего не подошло, вернем дефолт
      return {
        is_connected: false,
        address: null
      };
    } catch (error) {
      console.error('Error in getWalletStatus:', error);
      // В случае ошибки возвращаем безопасное значение
      return {
        is_connected: false,
        address: null
      };
    }
  },
  disconnectWallet: async (telegramId: number) => {
    return api.delete(`/wallet/${telegramId}/disconnect`);
  },
};
export interface MiningBreakdown {
  base: number;
  referral_pct: number;
  qualified_referrals: number;
  holdings_mult: number;
  holdings_tier: number;
  og_active: boolean;
  verified: boolean;
  task_boost_pct: number;
}

export interface MiningPotential {
  hourly_rate: number;
  breakdown: MiningBreakdown;
}

export interface MiningStatus {
  state: 'none' | 'active' | 'claimable';
  session_id?: number;
  ends_at?: string;
  seconds_left?: number;
  accrued?: number;
  accrued_estimate?: number;
  hourly_rate?: number;
  potential?: MiningPotential;
}

export interface MiningChallenge {
  challenge_id: string;
  question: string;
}

export const miningApi = {
  getChallenge: (telegramId: number | string) =>
    api.post<any, MiningChallenge>(`/mining/challenge?telegram_id=${telegramId}`),
  start: (telegramId: number | string, challengeId?: string, answer?: number) =>
    api.post<any, { session_id: number; hourly_rate: number; ends_at: string }>(
      '/mining/start', challengeId
        ? { telegram_id: telegramId, challenge_id: challengeId, answer }
        : { telegram_id: telegramId }),
  getStatus: (telegramId: number | string) =>
    api.get<any, MiningStatus>(`/mining/status/${telegramId}`),
  claim: (telegramId: number | string) =>
    api.post<any, { claimed_amount: number; new_balance: number }>(
      `/mining/claim?telegram_id=${telegramId}`),
};

export const promoApi = {
  redeem: (telegramId: number | string, code: string) =>
    api.post<any, { reward: number; new_balance: number }>(
      '/promo/redeem', { telegram_id: telegramId, code }),
};

export interface OgPassStatus {
  active: boolean;
  expires_at: string | null;
  cost: number;
  days: number;
}

export const ogPassApi = {
  getStatus: (telegramId: number | string) =>
    api.get<any, OgPassStatus>(`/ogpass/status/${telegramId}`),
  purchase: (telegramId: number | string) =>
    api.post<any, { expires_at: string; new_balance: number }>(
      `/ogpass/purchase?telegram_id=${telegramId}`),
};

export interface WithdrawalRecord {
  id: number;
  amount: number;
  address: string;
  status: string;
  created_at: string | null;
}

export interface PayoutEvent {
  kind: 'withdrawal' | 'crew_payout';
  name: string;
  amount: number;
  status: string;
  detail: string;
  created_at: string | null;
}

export const withdrawApi = {
  request: (telegramId: number | string, amount: number, address: string) =>
    api.post<any, { id: number; amount: number; status: string; new_balance: number }>(
      '/withdraw/request', { telegram_id: telegramId, amount, address }),
  getHistory: (telegramId: number | string) =>
    api.get<any, WithdrawalRecord[]>(`/withdraw/history/${telegramId}`),
  getRecent: () =>
    api.get<any, PayoutEvent[]>('/withdraw/recent'),
};

export interface LeaderEntry {
  rank: number;
  telegram_id: number;
  username: string | null;
  balance: number;
  level: number;
  og_badge: boolean;
}

export const ratingApi = {
  getGlobal: (limit = 50) =>
    api.get<any, { leaders: LeaderEntry[] }>(`/rating/global?limit=${limit}`),
};

export interface ReferralMilestone {
  invites: number;
  reward: number;
  claimed: boolean;
  reached: boolean;
}

export interface ReferralFriendEarning {
  telegram_id: number;
  username: string | null;
  earned_for_you: number;
  qualified: boolean;
}

export interface ReferralStats {
  total_invites: number;
  qualified_invites: number;
  earnings_total: number;
  earnings_tier1: number;
  earnings_tier2: number;
  tier1_rate_pct: number;
  tier2_rate_pct: number;
  milestones: ReferralMilestone[];
  friends: ReferralFriendEarning[];
}

export const referralApi = {
  getStats: (telegramId: number | string) =>
    api.get<any, ReferralStats>(`/users/referral-stats/${telegramId}`),
};

export const consentApi = {
  getConsent: (telegramId: number | string) =>
    api.get<any, { accepted_version: number }>(`/users/consent/${telegramId}`),
  accept: (telegramId: number | string, termsVersion: number) =>
    api.post<any, { accepted_version: number }>(
      '/users/consent', { telegram_id: telegramId, terms_version: termsVersion }),
};

export const welcomeApi = {
  claim: (telegramId: number | string) =>
    api.post<any, { reward?: number; new_balance: number; already_claimed?: boolean }>(
      `/bonus/welcome/${telegramId}`),
};

// ---- Folded-in features: Arcade (StoryVibe), The Button (ButtonMania), Drops (Token-Giver) ----

export interface ArcadeState {
  balance: number;
  wheel: { segments: number[]; free_spins_left: number; free_spins_per_day: number; paid_spin_cost: number };
  flip: { min_stake: number; max_stake: number; payout_mult: number };
}

export interface WheelSpinResult extends ArcadeState {
  segment_index: number;
  payout: number;
  was_free: boolean;
}

export interface FlipResult {
  result: 'heads' | 'tails';
  won: boolean;
  payout: number;
  balance: number;
}

export const arcadeApi = {
  getState: (telegramId: number | string) =>
    api.get<any, ArcadeState>(`/arcade/state?telegram_id=${telegramId}`),
  spin: (telegramId: number | string) =>
    api.post<any, WheelSpinResult>('/arcade/wheel/spin', { telegram_id: Number(telegramId) }),
  flip: (telegramId: number | string, choice: 'heads' | 'tails', stake: number) =>
    api.post<any, FlipResult>('/arcade/flip/play', { telegram_id: Number(telegramId), choice, stake }),
};

export interface ButtonStateResponse {
  total_presses: number;
  milestone: number;
  presses_into_milestone: number;
  presses_to_next: number;
  milestone_size: number;
  chest_amount: number;
  my_presses: number;
  can_claim_chest: boolean;
  claim_min_presses: number;
  balance?: number;
  claimed?: number;
}

export const buttonApi = {
  getState: (telegramId: number | string) =>
    api.get<any, ButtonStateResponse>(`/button/state?telegram_id=${telegramId}`),
  press: (telegramId: number | string) =>
    api.post<any, ButtonStateResponse>('/button/press', { telegram_id: Number(telegramId) }),
  claim: (telegramId: number | string) =>
    api.post<any, ButtonStateResponse>('/button/claim', { telegram_id: Number(telegramId) }),
};

export interface DropState {
  drop_key: string;
  starts_at: string;
  ends_at: string;
  next_starts_at: string;
  live: boolean;
  pool_total: number;
  per_claim: number;
  claims: number;
  pool_remaining: number;
  claimed_by_me: boolean;
  claimable: boolean;
  balance: number;
  claimed_amount?: number;
}

export const dropsApi = {
  getCurrent: (telegramId: number | string) =>
    api.get<any, DropState>(`/drops/current?telegram_id=${telegramId}`),
  claim: (telegramId: number | string) =>
    api.post<any, DropState>('/drops/claim', { telegram_id: Number(telegramId) }),
};

// ---- Admin panel (GarageInc pattern: allowlist of admin Telegram IDs) ----

export interface AdminStats {
  users: number;
  balances_total: number;
  lifetime_earned_total: number;
  referral_payouts: number;
  referral_events: number;
  arcade_plays: number;
  arcade_staked: number;
  arcade_paid: number;
  button_presses: number;
  drop_claims: number;
  pending_withdrawals: number;
  paid_out_total: number;
  banned_users: number;
}

export interface AdminUser {
  telegram_id: number;
  username: string | null;
  balance: number;
  level: number;
  lifetime_earned: number;
  lifetime_mined: number;
  referral_earnings: number;
  task_boost_pct: number;
  admin_boost_pct: number;
  wallet: string | null;
  banned: boolean;
  ban_reason: string | null;
  invites: number;
  created_at: string | null;
  arcade_plays?: number;
  arcade_won?: number;
  arcade_staked?: number;
  referrer_telegram_id?: number | null;
  recent_withdrawals?: { id: number; amount: number; status: string; created_at: string | null }[];
}

export interface AdminSettings { referrals_enabled: boolean; arcade_enabled: boolean; announcement: string }
export interface AdminAction { action: string; target: string; detail: string; at: string | null }

export interface AdminWithdrawal {
  id: number; telegram_id: number | null; username: string | null; amount: number;
  address: string; status: string; created_at: string | null;
  reviewed_by: number | null; tx_hash: string | null; paid_at: string | null;
}
export interface AdminTaskFull {
  id: number; title: string; description: string; type: string; reward: number;
  reward_type: string; multiplier_pct: number; link_url: string | null;
  condition_type: string; condition_value: number; is_active: boolean;
}
export interface AdminEconomy { base_rate: number; session_hours: number; og_cost: number; welcome_reward: number }
export interface AdminComms {
  proofs_channel_id: string; proofs_realtime: boolean;
  digest_enabled: boolean; digest_hour_utc: number; bot_audience: number;
}

export const adminApi = {
  whoami: (telegramId: number | string) =>
    api.get<any, { is_admin: boolean }>(`/admin/whoami?telegram_id=${telegramId}`),
  getAnnouncement: () =>
    api.get<any, { text: string }>('/admin/announcement'),
  getStats: (adminId: number | string) =>
    api.get<any, AdminStats>(`/admin/stats?admin_id=${adminId}`),
  listUsers: (adminId: number | string, q = '') =>
    api.get<any, { users: AdminUser[] }>(`/admin/users?admin_id=${adminId}&q=${encodeURIComponent(q)}`),
  getUser: (adminId: number | string, tid: number) =>
    api.get<any, AdminUser>(`/admin/users/${tid}?admin_id=${adminId}`),
  adjust: (adminId: number | string, tid: number, amount: number) =>
    api.post<any, { telegram_id: number; balance: number }>(`/admin/users/${tid}/adjust`, { admin_id: Number(adminId), amount }),
  setLevel: (adminId: number | string, tid: number, level: number) =>
    api.post<any, { telegram_id: number; level: number }>(`/admin/users/${tid}/set-level`, { admin_id: Number(adminId), level }),
  grantBoost: (adminId: number | string, tid: number, pct: number) =>
    api.post<any, { telegram_id: number; admin_boost_pct: number }>(`/admin/users/${tid}/grant-boost`, { admin_id: Number(adminId), pct }),
  grantReferralBonus: (adminId: number | string, tid: number, amount: number) =>
    api.post<any, { telegram_id: number; balance: number }>(`/admin/users/${tid}/grant-referral-bonus`, { admin_id: Number(adminId), amount }),
  setReferrer: (adminId: number | string, tid: number, referrerTelegramId: number | null) =>
    api.post<any, { telegram_id: number; referrer_telegram_id: number | null }>(`/admin/users/${tid}/set-referrer`, { admin_id: Number(adminId), referrer_telegram_id: referrerTelegramId }),
  banUser: (adminId: number | string, tid: number, reason: string) =>
    api.post<any, { telegram_id: number; banned: boolean }>(`/admin/users/${tid}/ban`, { admin_id: Number(adminId), reason }),
  unbanUser: (adminId: number | string, tid: number) =>
    api.post<any, { telegram_id: number; banned: boolean }>(`/admin/users/${tid}/unban`, { admin_id: Number(adminId) }),
  getSettings: (adminId: number | string) =>
    api.get<any, AdminSettings>(`/admin/settings?admin_id=${adminId}`),
  updateSettings: (adminId: number | string, body: Partial<AdminSettings>) =>
    api.post<any, AdminSettings>('/admin/settings', { admin_id: Number(adminId), ...body }),
  forceStartDrop: (adminId: number | string) =>
    api.post<any, { drop_key: string; ends_at: string }>('/admin/drops/force-start', { admin_id: Number(adminId) }),
  getActions: (adminId: number | string) =>
    api.get<any, { actions: AdminAction[] }>(`/admin/actions?admin_id=${adminId}`),
  exportActions: (adminId: number | string) =>
    api.get<any, Blob>(`/admin/export.xlsx?admin_id=${adminId}`, { responseType: 'blob' }),
  listWithdrawals: (adminId: number | string, status = '') =>
    api.get<any, { withdrawals: AdminWithdrawal[]; counts: Record<string, number>; paid_total: number }>(
      `/admin/withdrawals?admin_id=${adminId}${status ? `&status=${status}` : ''}`),
  reviewWithdrawal: (adminId: number | string, wid: number, action: 'approve' | 'reject') =>
    api.post<any, { id: number; status: string }>(`/admin/withdrawals/${wid}/review`, { admin_id: Number(adminId), action }),
  markPaid: (adminId: number | string, wid: number, txHash: string) =>
    api.post<any, { id: number; status: string; proof_posted: boolean }>(`/admin/withdrawals/${wid}/mark-paid`, { admin_id: Number(adminId), tx_hash: txHash }),
  listAllTasks: (adminId: number | string) =>
    api.get<any, { tasks: AdminTaskFull[] }>(`/admin/tasks/all?admin_id=${adminId}`),
  createTask: (adminId: number | string, body: Omit<AdminTaskFull, 'id' | 'is_active'>) =>
    api.post<any, AdminTaskFull>('/admin/tasks/create', { admin_id: Number(adminId), ...body }),
  patchTask: (adminId: number | string, taskId: number, body: Record<string, unknown>) =>
    api.request<any, AdminTaskFull>({ method: 'PATCH', url: `/admin/tasks/${taskId}`, data: { admin_id: Number(adminId), ...body } }),
  deleteTask: (adminId: number | string, taskId: number) =>
    api.delete<any, { deleted: number }>(`/admin/tasks/${taskId}?admin_id=${adminId}`),
  getEconomy: (adminId: number | string) =>
    api.get<any, AdminEconomy>(`/admin/economy?admin_id=${adminId}`),
  setEconomy: (adminId: number | string, body: Partial<AdminEconomy>) =>
    api.post<any, AdminEconomy>('/admin/economy', { admin_id: Number(adminId), ...body }),
  getComms: (adminId: number | string) =>
    api.get<any, AdminComms>(`/admin/comms?admin_id=${adminId}`),
  setComms: (adminId: number | string, body: Partial<AdminComms>) =>
    api.post<any, AdminComms>('/admin/comms', { admin_id: Number(adminId), ...body }),
  broadcast: (adminId: number | string, text: string) =>
    api.post<any, { audience: number; sent: number; failed: number }>('/admin/broadcast', { admin_id: Number(adminId), text }),
};

export interface StreakStatus {
  streak: number;
  next_milestone: number | null;
  next_milestone_in_days: number | null;
  resets_in_seconds: number;
}
