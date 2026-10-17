export const TERMS_VERSION = 1;

export interface TermsSection {
  title: string;
  body: string[];
}

export const TERMS_SUMMARY: string[] = [
  "Space Hunter is a game. CSM points are in-game only and have no monetary value.",
  "One account per person. Bots, scripts and exploits will get you banned and your earnings removed.",
  "Reward rates can change at any time. Nothing here is an investment or a promise of profit.",
  "Withdrawals need a minimum balance, are reviewed, and timing is never guaranteed.",
  "Invite real people only — farmed referrals do not count towards rewards.",
  "You must be 18 or older to play.",
];

export const TERMS_SECTIONS: TermsSection[] = [
  {
    title: "1. The game and eligibility",
    body: [
      "Space Hunter (\"the game\") is a Telegram Mini App game operated as a demonstration product.",
      "You must be at least 18 years old to play. By playing you confirm you meet the age requirement.",
      "You need a Telegram account to play. One account per person — creating or using multiple accounts to gain an advantage is prohibited.",
    ],
  },
  {
    title: "2. CSM points",
    body: [
      "CSM points are in-game units of account. They have no monetary value, are not a currency, not a security, and not an investment of any kind.",
      "CSM cannot be sold, transferred between players, or redeemed for cash, except through the in-app withdrawal flow where explicitly offered.",
      "Nothing in the game constitutes financial advice or a promise of future value.",
    ],
  },
  {
    title: "3. Earning and rates",
    body: [
      "CSM is earned by tapping, mining sessions, boosts, tasks, daily bonuses, streaks, promo codes and referrals.",
      "Reward rates, costs and limits are set server-side and may be changed, capped or reset at any time without notice.",
      "Rewards are not guaranteed: bugs, abuse prevention or balancing may reduce or remove earnings.",
    ],
  },
  {
    title: "4. Fair play",
    body: [
      "Bots, scripts, automation, emulators, clickers, modified clients and any exploitation of bugs are strictly forbidden.",
      "If you break this rule, your earnings may be removed and your account permanently banned, at our sole discretion.",
      "Attempting to manipulate challenges, referrals or leaderboards counts as a violation.",
    ],
  },
  {
    title: "5. Referrals",
    body: [
      "Invite real people with your personal link. Self-referrals and farmed or fake accounts do not count.",
      "Milestone rewards require referred users to have earned at least 100 CSM lifetime.",
      "We may withhold referral rewards suspected of fraud pending review.",
    ],
  },
  {
    title: "6. Mining sessions and streaks",
    body: [
      "Mining sessions run for a fixed duration and must be claimed before starting a new one.",
      "A short anti-bot check is required to start a session.",
      "Daily streaks count consecutive calendar days (UTC). Missing a day resets your streak. Milestone rewards are credited once each.",
    ],
  },
  {
    title: "7. OG Pass",
    body: [
      "The OG Pass is purchased with CSM for a fixed duration (30 days) and grants the listed benefits while active.",
      "OG Pass purchases are final and non-refundable. Repurchasing extends the pass from its current expiry date.",
      "Benefits apply from the moment of purchase and end when the pass expires.",
    ],
  },
  {
    title: "8. Withdrawals",
    body: [
      "Withdrawals require a minimum balance (shown in the app) and a valid TON wallet address.",
      "Requested amounts are debited immediately and held pending review. Requests are approved or rejected at our discretion.",
      "Processing time is not guaranteed. In this demo build, requests are recorded and settlement is manual.",
      "Network fees, where applicable, are deducted from the withdrawn amount or borne by you.",
    ],
  },
  {
    title: "9. Changes and termination",
    body: [
      "We may modify, suspend or discontinue the game or any feature at any time.",
      "We may terminate accounts that violate these terms, with forfeiture of in-game balances.",
      "These terms may be updated; material changes will ask you to accept the new version before continuing to play.",
    ],
  },
  {
    title: "10. Liability",
    body: [
      "The game is provided \"as is\" without warranties of any kind.",
      "To the maximum extent permitted by law, we are not liable for any loss of in-game progress, points or anticipated rewards.",
      "Nothing here is investment advice. Never spend money you cannot afford to lose on anything crypto-related.",
    ],
  },
  {
    title: "11. Privacy",
    body: [
      "We process your Telegram user ID, username, profile photo (if available) and your in-game activity to operate the game.",
      "We do not sell your data. Wallet addresses you provide are used only for withdrawals and verification.",
      "Data is stored for as long as your account exists; contact us to request deletion.",
    ],
  },
  {
    title: "12. Contact",
    body: [
      "For questions about these terms, fair-play decisions or your account, contact the game administrators through the official Telegram channel.",
      "These terms were last updated for version 1. Continued play after an update constitutes acceptance of the new version.",
    ],
  },
];
