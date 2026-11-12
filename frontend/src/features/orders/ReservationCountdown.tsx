import { Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { toPersianDigits } from "../../shared/money";

type Props = {
  expiresAt: string | null | undefined;
};

function formatRemaining(ms: number): string {
  if (ms <= 0) {
    return "مهلت رزرو از دید مرورگر به پایان رسیده (تأیید فقط با پاسخ سرور).";
  }
  const totalSec = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSec / 60);
  const seconds = totalSec % 60;
  return `مانده تا مهلت رزرو (راهنما): ${toPersianDigits(String(minutes))}:${toPersianDigits(
    String(seconds).padStart(2, "0"),
  )}`;
}

/**
 * Visual countdown for reservation deadline.
 * Local clock is guidance only — it must never enable/disable confirm.
 */
export function ReservationCountdown({ expiresAt }: Props) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!expiresAt) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [expiresAt]);

  if (!expiresAt) {
    return null;
  }

  const remaining = new Date(expiresAt).getTime() - now;

  return (
    <Typography
      variant="body2"
      color="text.secondary"
      data-testid="reservation-countdown"
      data-remaining-ms={String(remaining)}
      data-expired-locally={remaining <= 0 ? "true" : "false"}
    >
      {formatRemaining(remaining)}
    </Typography>
  );
}

