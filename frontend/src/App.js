import React, { useCallback, useEffect, useMemo, useState } from 'react';
import AdminConsole from './AdminConsole';
import BottomNav from './components/user/BottomNav';
import { UserProvider, useUser } from './components/user/UserContext';
import HomeScreen from './screens/HomeScreen';
import PayScreen from './screens/PayScreen';
import SecurityCheckScreen from './screens/SecurityCheckScreen';
import PaymentSuccessScreen from './screens/PaymentSuccessScreen';
import PaymentVerifyScreen from './screens/PaymentVerifyScreen';
import PaymentBlockedScreen from './screens/PaymentBlockedScreen';
import HistoryScreen from './screens/HistoryScreen';
import SecurityProfileScreen from './screens/SecurityProfileScreen';
import {
  fetchMySecurityScore,
  fetchMyTransactions,
  payTransaction,
  reportFraud,
  verifyBiometricWithMethod,
} from './api/fraudApi';

const IMMERSIVE_SCREENS = new Set(['checking', 'success', 'verify', 'blocked']);

function upsertByTransaction(prev, nextItem) {
  return [nextItem, ...prev.filter((row) => row.transaction_id !== nextItem.transaction_id)];
}

function transactionFromResult(result) {
  return {
    transaction_id: result.transaction_id,
    sender_upi: result.sender_upi,
    receiver_upi: result.receiver_upi,
    receiver_name: result.receiver_name,
    amount: Number(result.amount || 0),
    status: result.status,
    decision: result.decision,
    user_message: result.user_message,
    user_reason: result.user_reason,
    security_note: result.security_note,
    fraud_pattern: result.fraud_pattern,
    timestamp: result.timestamp,
    receipt_id: result.receipt_id,
    transaction_type: result.transaction_type || 'transfer',
  };
}

function UserMode({ onOpenConsole }) {
  const { currentUser, profiles, switchProfile, debitBalance } = useUser();

  const [screen, setScreen] = useState('home');
  const [payDraft, setPayDraft] = useState({ transaction_type: 'transfer' });
  const [paymentPayload, setPaymentPayload] = useState(null);
  const [paymentResult, setPaymentResult] = useState(null);

  const [transactions, setTransactions] = useState([]);
  const [securityScore, setSecurityScore] = useState(null);
  const [toast, setToast] = useState('');

  const refreshUserData = useCallback(async () => {
    try {
      const [txnData, scoreData] = await Promise.all([
        fetchMyTransactions(currentUser.upi, 50),
        fetchMySecurityScore(currentUser.upi),
      ]);
      setTransactions(Array.isArray(txnData?.transactions) ? txnData.transactions : []);
      setSecurityScore(scoreData || null);
    } catch {
      setToast('Could not refresh account data. Showing latest available info.');
    }
  }, [currentUser.upi]);

  useEffect(() => {
    refreshUserData();
  }, [refreshUserData]);

  useEffect(() => {
    setScreen('home');
    setPayDraft({ transaction_type: 'transfer' });
    setPaymentPayload(null);
    setPaymentResult(null);
  }, [currentUser.upi]);

  useEffect(() => {
    if (!toast) return undefined;
    const timer = setTimeout(() => setToast(''), 2800);
    return () => clearTimeout(timer);
  }, [toast]);

  const navScreen = useMemo(() => {
    if (screen === 'history') return 'history';
    if (screen === 'security') return 'security';
    if (screen === 'pay' || screen === 'checking' || screen === 'verify' || screen === 'success' || screen === 'blocked') {
      return 'pay';
    }
    return 'home';
  }, [screen]);

  const historySummary = useMemo(() => {
    const blockedCount = transactions.filter((txn) => txn.status === 'BLOCKED').length;
    return {
      protectedCount: transactions.length,
      protectedAmount: Number(securityScore?.protected_amount || 0),
      blockedCount,
    };
  }, [transactions, securityScore]);

  const runPayCheck = useCallback(async (payload) => {
    return payTransaction(payload);
  }, []);

  const handleCheckComplete = useCallback(
    (response) => {
      const result = {
        ...response,
        sender_upi: currentUser.upi,
      };
      setPaymentResult(result);
      setTransactions((prev) => upsertByTransaction(prev, transactionFromResult(result)));

      if (result.decision === 'ALLOW') {
        debitBalance(Number(result.amount || 0));
        setScreen('success');
      } else if (result.decision === 'VERIFY') {
        setScreen('verify');
      } else {
        setScreen('blocked');
      }

      refreshUserData();
    },
    [currentUser.upi, debitBalance, refreshUserData]
  );

  const handleVerifyRequest = useCallback(async (method) => {
    const mappedMethod = method === 'pin' ? 'fingerprint' : method;
    return verifyBiometricWithMethod(paymentResult?.transaction_id, mappedMethod);
  }, [paymentResult?.transaction_id]);

  const handleVerifyResolved = useCallback(
    ({ outcome, verification }) => {
      if (outcome === 'success') {
        const next = {
          ...paymentResult,
          status: 'COMPLETED',
          decision: 'ALLOW',
          user_message: verification?.message || paymentResult?.user_message,
          security_note: 'Verification completed successfully. Payment sent securely.',
        };
        setPaymentResult(next);
        setTransactions((prev) => upsertByTransaction(prev, transactionFromResult(next)));
        debitBalance(Number(next.amount || 0));
        setScreen('success');
      } else {
        const next = {
          ...paymentResult,
          status: 'BLOCKED',
          decision: 'BLOCK',
          user_reason: verification?.message || paymentResult?.user_reason,
          user_message: 'Your money is safe. Payment stopped for your protection.',
        };
        setPaymentResult(next);
        setTransactions((prev) => upsertByTransaction(prev, transactionFromResult(next)));
        setScreen('blocked');
      }
      refreshUserData();
    },
    [debitBalance, paymentResult, refreshUserData]
  );

  const openPay = useCallback((prefill = {}) => {
    setPayDraft((prev) => ({
      ...prev,
      ...prefill,
    }));
    setScreen('pay');
  }, []);

  const runDemoScenario = useCallback((scenario) => {
    setPayDraft({
      ...scenario.payload,
      note: `Demo: ${scenario.label}`,
    });
    setScreen('pay');
  }, []);

  const submitPayForm = useCallback(
    (payload) => {
      const outgoing = {
        sender_upi: currentUser.upi,
        receiver_upi: payload.receiver_upi,
        amount: Number(payload.amount || 0),
        transaction_type: payload.transaction_type || 'transfer',
        note: payload.note || '',
        sender_device_id: payload.sender_device_id || `WEB_${currentUser.initials}_001`,
      };
      setPaymentPayload(outgoing);
      setScreen('checking');
    },
    [currentUser.initials, currentUser.upi]
  );

  const submitAppeal = useCallback(async ({ reason, phone, transactionId }) => {
    setToast(`Appeal submitted for ${transactionId}. Support callback on ${phone}.`);
    if (!reason) return;
  }, []);

  const submitFraudReport = useCallback(
    async (txnOrResult) => {
      const transactionId = txnOrResult?.transaction_id || paymentResult?.transaction_id;
      if (!transactionId) return;
      try {
        await reportFraud(transactionId, currentUser.upi, 'User reported this transaction as unauthorized.');
        setToast('Report submitted. Support ticket created and account secured.');
      } catch {
        setToast('Could not submit report right now. Please call 1930.');
      }
      refreshUserData();
    },
    [currentUser.upi, paymentResult?.transaction_id, refreshUserData]
  );

  const shareReceipt = useCallback(async () => {
    if (!paymentResult) return;
    const text = `ShieldPay Receipt\nID: ${paymentResult.receipt_id}\nTo: ${paymentResult.receiver_upi}\nAmount: Rs.${paymentResult.amount}`;
    try {
      if (navigator.share) {
        await navigator.share({ title: 'ShieldPay Receipt', text });
      } else {
        await navigator.clipboard.writeText(text);
      }
      setToast('Receipt ready to share.');
    } catch {
      setToast('Could not share receipt now.');
    }
  }, [paymentResult]);

  const isImmersive = IMMERSIVE_SCREENS.has(screen);

  let content = null;
  if (screen === 'home') {
    content = (
      <HomeScreen
        profile={currentUser}
        profiles={profiles}
        transactions={transactions}
        securitySummary={securityScore}
        onOpenPay={openPay}
        onOpenHistory={() => setScreen('history')}
        onOpenSecurity={() => setScreen('security')}
        onRunDemo={runDemoScenario}
        onSelectProfile={switchProfile}
      />
    );
  } else if (screen === 'pay') {
    content = (
      <PayScreen
        draft={payDraft}
        onBack={() => setScreen('home')}
        onSubmit={submitPayForm}
      />
    );
  } else if (screen === 'checking') {
    content = (
      <SecurityCheckScreen
        paymentPayload={paymentPayload}
        onRunCheck={runPayCheck}
        onComplete={handleCheckComplete}
      />
    );
  } else if (screen === 'success') {
    content = (
      <PaymentSuccessScreen
        result={paymentResult}
        onDone={() => {
          setScreen('home');
          refreshUserData();
        }}
        onShare={shareReceipt}
        onPayAgain={() => openPay({ receiver_upi: paymentResult?.receiver_upi, transaction_type: paymentResult?.transaction_type })}
      />
    );
  } else if (screen === 'verify') {
    content = (
      <PaymentVerifyScreen
        result={paymentResult}
        onBack={() => setScreen('pay')}
        onVerify={handleVerifyRequest}
        onResolved={handleVerifyResolved}
      />
    );
  } else if (screen === 'blocked') {
    content = (
      <PaymentBlockedScreen
        result={paymentResult}
        onHome={() => setScreen('home')}
        onAppeal={submitAppeal}
        onReport={() => submitFraudReport(paymentResult)}
      />
    );
  } else if (screen === 'history') {
    content = (
      <HistoryScreen
        transactions={transactions}
        summary={historySummary}
        onReportFraud={submitFraudReport}
      />
    );
  } else if (screen === 'security') {
    content = <SecurityProfileScreen scoreData={securityScore} />;
  }

  return (
    <div className="user-mode-shell">
      <button type="button" className="console-toggle" onClick={onOpenConsole}>
        Security Console
      </button>

      <main className={`mobile-frame ${isImmersive ? 'immersive' : ''}`}>
        {content}
      </main>

      {!isImmersive ? (
        <BottomNav
          active={navScreen}
          onNavigate={(target) => setScreen(target)}
          onConsole={onOpenConsole}
        />
      ) : null}

      {toast ? <div className="toast-banner">{toast}</div> : null}
    </div>
  );
}

function AppRoot() {
  const [mode, setMode] = useState('user');

  if (mode === 'admin') {
    return (
      <div className="app-mode mode-admin">
        <button type="button" className="console-toggle in-admin" onClick={() => setMode('user')}>
          ShieldPay
        </button>
        <AdminConsole />
      </div>
    );
  }

  return (
    <div className="app-mode mode-user">
      <UserMode onOpenConsole={() => setMode('admin')} />
    </div>
  );
}

export default function App() {
  return (
    <UserProvider>
      <AppRoot />
    </UserProvider>
  );
}
