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

function assertHttpsWebhookUrl(value: string): string {
  const url = new URL(value);
  if (url.protocol !== "https:") {
    throw new Error(`OWNIX_EMAIL_WEBHOOK_URL must be an https:// URL, got ${url.protocol}`);
  }
  return url.toString();
}

export default {
  async email(
    message: ForwardableEmailMessage,
    env: Env,
    _ctx: ExecutionContext,
  ): Promise<void> {
    const webhookUrl = assertHttpsWebhookUrl(env.OWNIX_EMAIL_WEBHOOK_URL);
    const parsed = await PostalMime.parse(message.raw);
    const payload = {
      envelopeTo: message.to,
      from: normalizedSender(parsed, message),
      subject: parsed.subject ?? message.headers.get("subject") ?? "",
      html: parsed.html ?? "",
      text: parsed.text ?? "",
      messageId: parsed.messageId ?? message.headers.get("message-id") ?? "",
    };

    // redirect: "manual" — never follow a redirect on this request, so the secret
    // header can't end up forwarded to a host OWNIX_EMAIL_WEBHOOK_URL didn't name.
    const response = await fetch(webhookUrl, {
      method: "POST",
      redirect: "manual",
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
