import { useFocusSession } from "./useFocusSession";

function formatSeconds(total: number): string {
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function FocusWidgets() {
  const {
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
  } = useFocusSession();

  return (
    <div>
      {resumePath && (
        <div>
          <a href={resumePath}>Continuar donde estabas</a>
          <button onClick={dismissResume}>Cerrar</button>
        </div>
      )}

      {session && (
        <div>
          {session.timer_mode !== "no_timer" && <span>{formatSeconds(activeSeconds)}</span>}
          <select value={session.timer_mode} onChange={(e) => setTimerMode(e.target.value)}>
            <option value="count_up">Count Up</option>
            <option value="pomodoro">Pomodoro</option>
            <option value="countdown">Countdown</option>
            <option value="no_timer">Sin timer</option>
          </select>
          <button onClick={toggleFocusMode}>{focusModeEnabled ? "Salir de Focus Mode" : "Focus Mode"}</button>
        </div>
      )}

      {breakReminderVisible && (
        <div role="alert">
          <p>Llevas un buen rato concentrado. ¿Pausa de 5 minutos?</p>
          <button onClick={() => dismissBreakReminder(false)}>Pausa</button>
          <button onClick={() => dismissBreakReminder(false)}>Seguir</button>
          <button onClick={() => dismissBreakReminder(true)}>No volver a preguntar hoy</button>
        </div>
      )}

      {hyperfocusReminderVisible && (
        <div role="alert">
          <p>Has trabajado mucho tiempo seguido. Guarda tus notas y considera una pausa.</p>
          <button onClick={dismissHyperfocusReminder}>Entendido</button>
        </div>
      )}
    </div>
  );
}
