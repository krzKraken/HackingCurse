import { createContext, useContext, useEffect, useRef, useState, ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { api, LearningSession } from "../../lib/api";
import { useAuth } from "../auth/useAuth";

const PING_INTERVAL_MS = 30000;

type FocusState = {
  session: LearningSession | null;
  activeSeconds: number;
  resumePath: string | null;
  dismissResume: () => void;
  breakReminderVisible: boolean;
  dismissBreakReminder: (skipToday: boolean) => void;
  hyperfocusReminderVisible: boolean;
  dismissHyperfocusReminder: () => void;
  focusModeEnabled: boolean;
  toggleFocusMode: () => void;
  setTimerMode: (mode: string) => void;
};

const FocusContext = createContext<FocusState | null>(null);

function todayKey(): string {
  return `focus-break-dismissed-${new Date().toDateString()}`;
}

export function FocusSessionProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  const [session, setSession] = useState<LearningSession | null>(null);
  const [activeSeconds, setActiveSeconds] = useState(0);
  const [resumePath, setResumePath] = useState<string | null>(null);
  const [breakReminderVisible, setBreakReminderVisible] = useState(false);
  const [hyperfocusReminderVisible, setHyperfocusReminderVisible] = useState(false);
  const [focusModeEnabled, setFocusModeEnabled] = useState(
    () => localStorage.getItem("focus-mode") === "true"
  );
  const sessionRef = useRef<LearningSession | null>(null);
  const activeSecondsRef = useRef(0);
  const initialized = useRef(false);

  useEffect(() => {
    sessionRef.current = session;
  }, [session]);
  useEffect(() => {
    activeSecondsRef.current = activeSeconds;
  }, [activeSeconds]);

  useEffect(() => {
    if (!user || initialized.current) return;
    initialized.current = true;

    api
      .getCurrentFocusSession()
      .then((s) => {
        setSession(s);
        setActiveSeconds(s.active_time_sec);
        if (s.last_position) setResumePath(s.last_position);
      })
      .catch(() => {
        api.startFocusSession().then(setSession);
      });
  }, [user]);

  useEffect(() => {
    if (!session) return;
    const id = setInterval(() => setActiveSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [session]);

  useEffect(() => {
    if (!session) return;
    const id = setInterval(() => {
      if (sessionRef.current) {
        api.updateFocusSession(sessionRef.current.id, {
          active_time_sec: activeSecondsRef.current,
          last_position: location.pathname,
        });
      }
    }, PING_INTERVAL_MS);
    return () => clearInterval(id);
  }, [session, location.pathname]);

  useEffect(() => {
    if (!session) return;
    const minutes = activeSeconds / 60;
    if (minutes >= session.break_reminder_threshold_min && localStorage.getItem(todayKey()) !== "true") {
      setBreakReminderVisible(true);
    }
    if (minutes >= session.hyperfocus_reminder_min) {
      setHyperfocusReminderVisible(true);
    }
  }, [activeSeconds, session]);

  const dismissResume = () => setResumePath(null);

  const dismissBreakReminder = (skipToday: boolean) => {
    setBreakReminderVisible(false);
    if (skipToday) localStorage.setItem(todayKey(), "true");
  };

  const dismissHyperfocusReminder = () => setHyperfocusReminderVisible(false);

  const toggleFocusMode = () => {
    setFocusModeEnabled((prev) => {
      const next = !prev;
      localStorage.setItem("focus-mode", String(next));
      return next;
    });
  };

  const setTimerMode = (mode: string) => {
    if (!session) return;
    api.updateFocusSession(session.id, { timer_mode: mode }).then(setSession);
  };

  return (
    <FocusContext.Provider
      value={{
        session,
        activeSeconds,
        resumePath,
        dismissResume,
        breakReminderVisible,
        dismissBreakReminder,
        hyperfocusReminderVisible,
        dismissHyperfocusReminder,
        focusModeEnabled,
        toggleFocusMode,
        setTimerMode,
      }}
    >
      {children}
    </FocusContext.Provider>
  );
}

export function useFocusSession(): FocusState {
  const ctx = useContext(FocusContext);
  if (!ctx) throw new Error("useFocusSession must be used inside FocusSessionProvider");
  return ctx;
}
