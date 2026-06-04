type LogLevel = "trace" | "debug" | "info" | "warn" | "error" | "silent";
type LogContext = Record<string, unknown>;

type Logger = {
  trace: (message: string, context?: LogContext) => void;
  debug: (message: string, context?: LogContext) => void;
  info: (message: string, context?: LogContext) => void;
  warn: (message: string, context?: LogContext) => void;
  error: (message: string, context?: LogContext) => void;
  child: (namespace: string) => Logger;
};

const LOG_LEVEL_KEY = "noveltl:log-level";

const LEVEL_VALUES: Record<LogLevel, number> = {
  trace: 0,
  debug: 1,
  info: 2,
  warn: 3,
  error: 4,
  silent: 5,
};

function isLogLevel(value: string | null | undefined): value is LogLevel {
  return (
    value === "trace" ||
    value === "debug" ||
    value === "info" ||
    value === "warn" ||
    value === "error" ||
    value === "silent"
  );
}

function readStoredLogLevel(): LogLevel | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const storedLevel = window.localStorage.getItem(LOG_LEVEL_KEY);
    return isLogLevel(storedLevel) ? storedLevel : null;
  } catch {
    return null;
  }
}

let currentLevel: LogLevel = readStoredLogLevel() ?? (import.meta.env.DEV ? "debug" : "warn");

function shouldLog(level: Exclude<LogLevel, "silent">): boolean {
  return LEVEL_VALUES[level] >= LEVEL_VALUES[currentLevel];
}

function write(
  level: Exclude<LogLevel, "silent">,
  namespace: string,
  message: string,
  context?: LogContext,
): void {
  if (!shouldLog(level)) {
    return;
  }

  const prefix = `[${namespace}] ${message}`;
  if (context === undefined) {
    console[level](prefix);
    return;
  }
  console[level](prefix, context);
}

export function setLogLevel(level: LogLevel): void {
  currentLevel = level;
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(LOG_LEVEL_KEY, level);
  } catch {
    return;
  }
}

export function getLogLevel(): LogLevel {
  return currentLevel;
}

export function createLogger(namespace: string): Logger {
  return {
    trace: (message, context) => write("trace", namespace, message, context),
    debug: (message, context) => write("debug", namespace, message, context),
    info: (message, context) => write("info", namespace, message, context),
    warn: (message, context) => write("warn", namespace, message, context),
    error: (message, context) => write("error", namespace, message, context),
    child: (childNamespace) => createLogger(`${namespace}.${childNamespace}`),
  };
}

export const logger = createLogger("noveltl");
