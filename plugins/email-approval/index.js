/**
 * email-approval plugin
 * Intercepts outbound email tool calls and requires Yoni's approval before sending.
 */

const { definePluginEntry } = await import(
  "/home/jonia/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/index.js"
);

export default definePluginEntry({
  id: "email-approval",
  name: "Email Approval Gate",
  description: "Requires explicit approval before sending any outbound email.",

  register(api) {
    api.on("before_tool_call", async (event, _ctx) => {
      const emailToolNames = [
        "send_email",
        "sendEmail",
        "send_mail",
        "sendMail",
        "compose_email",
        "reply_email",
        "forward_email",
      ];

      if (!emailToolNames.includes(event.toolName)) return;

      const p = event.params ?? {};
      const to = p.to ?? p.recipient ?? p.address ?? "?";
      const subject = p.subject ?? p.title ?? "(ללא נושא)";
      const body = p.body ?? p.content ?? p.text ?? "";
      const preview = typeof body === "string" ? body.slice(0, 300) : JSON.stringify(body).slice(0, 300);

      return {
        requireApproval: {
          title: `שליחת מייל — אישור נדרש`,
          description: `**אל:** ${to}\n**נושא:** ${subject}\n\n**תצוגה מקדימה:**\n${preview}${body.length > 300 ? "…" : ""}`,
          severity: "warning",
          timeoutMs: 120_000,
          timeoutBehavior: "deny",
        },
      };
    });
  },
});
