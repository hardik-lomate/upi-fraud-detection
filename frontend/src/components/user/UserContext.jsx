import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

const DEMO_PROFILES = [
  {
    name: 'Priya Sharma',
    upi: 'priya.sharma@oksbi',
    avatarColor: '#6C47FF',
    initials: 'PS',
    balance: 45200,
  },
  {
    name: 'Rahul Mehta',
    upi: 'rahul.mehta@ybl',
    avatarColor: '#00B894',
    initials: 'RM',
    balance: 12800,
  },
  {
    name: 'Ananya Patel',
    upi: 'ananya.patel@okaxis',
    avatarColor: '#F39C12',
    initials: 'AP',
    balance: 89500,
  },
  {
    name: 'Demo Attacker',
    upi: 'sim_swap_victim_001@upi',
    avatarColor: '#E24B4A',
    initials: 'DA',
    balance: 5000,
    note: 'This profile will trigger fraud detections',
  },
];

const UserContext = createContext(null);

export function UserProvider({ children }) {
  const [profiles, setProfiles] = useState(DEMO_PROFILES);
  const [currentUpi, setCurrentUpi] = useState(DEMO_PROFILES[0].upi);

  const currentUser = useMemo(
    () => profiles.find((profile) => profile.upi === currentUpi) || profiles[0],
    [profiles, currentUpi]
  );

  const switchProfile = useCallback((upi) => {
    setCurrentUpi(upi);
  }, []);

  const debitBalance = useCallback(
    (amount) => {
      const safeAmount = Number(amount) || 0;
      if (safeAmount <= 0) return;
      setProfiles((prev) =>
        prev.map((profile) => {
          if (profile.upi !== currentUpi) return profile;
          return {
            ...profile,
            balance: Math.max(0, Number(profile.balance || 0) - safeAmount),
          };
        })
      );
    },
    [currentUpi]
  );

  const creditBalance = useCallback(
    (amount) => {
      const safeAmount = Number(amount) || 0;
      if (safeAmount <= 0) return;
      setProfiles((prev) =>
        prev.map((profile) => {
          if (profile.upi !== currentUpi) return profile;
          return {
            ...profile,
            balance: Number(profile.balance || 0) + safeAmount,
          };
        })
      );
    },
    [currentUpi]
  );

  const value = useMemo(
    () => ({
      profiles,
      currentUser,
      switchProfile,
      debitBalance,
      creditBalance,
    }),
    [profiles, currentUser, switchProfile, debitBalance, creditBalance]
  );

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}

export function useUser() {
  const ctx = useContext(UserContext);
  if (!ctx) {
    throw new Error('useUser must be used inside UserProvider');
  }
  return ctx;
}

export const userProfiles = DEMO_PROFILES;
