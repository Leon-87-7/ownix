import PostalMime from "postal-mime";
import type { Email } from "postal-mime";

export interface Env {
  OWNIX_EMAIL_SECRET: string;
  OWNIX_EMAIL_WEBHOOK_URL: string;
}

function normalizedSender(email: Email, message: ForwardableEmailMessage): string {
  const parsed = email.from?.address?.trim().toLowerCase();
  return parsed || message.from.trim().toLowerCase();
}

export default {
  async email(
    message: ForwardableEmailMessage,
    env: Env,
    _ctx: ExecutionContext,
  ): Promise<void> {
    const parsed = await PostalMime.parse(message.raw);
    const payload = {
      envelopeTo: message.to,
      from: normalizedSender(parsed, message),
      subject: parsed.subject ?? message.headers.get("subject") ?? "",
      html: parsed.html ?? "",
      text: parsed.text ?? "",
      messageId: parsed.messageId ?? message.headers.get("message-id") ?? "",
    };

    const response = await fetch(env.OWNIX_EMAIL_WEBHOOK_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Ownix-Email-Secret": env.OWNIX_EMAIL_SECRET,
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Ownix webhook returned ${response.status}`);
    }
  },
};
