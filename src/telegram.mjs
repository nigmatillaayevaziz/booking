export class TelegramError extends Error {
  constructor(message, response) { super(message); this.response = response; }
}

export class Telegram {
  constructor(token, logger = console) {
    this.baseUrl = `https://api.telegram.org/bot${token}`;
    this.logger = logger;
    this.controllers = new Set();
    this.closed = false;
  }

  async call(method, payload = {}, timeoutMs = 40_000, maximumAttempts = 3) {
    let lastError;
    for (let attempt = 1; attempt <= maximumAttempts; attempt += 1) {
      if (this.closed) throw new Error("Telegram klienti yopilgan");
      const controller = new AbortController();
      this.controllers.add(controller);
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetch(`${this.baseUrl}/${method}`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(payload),
          signal: controller.signal,
        });
        const data = await response.json().catch(() => null);
        if (!response.ok || !data?.ok) {
          const error = new TelegramError(data?.description ?? `Telegram HTTP ${response.status}`, data);
          error.retryAfter = Number(data?.parameters?.retry_after ?? 0);
          error.retryable = response.status === 429 || response.status >= 500;
          throw error;
        }
        return data.result;
      } catch (error) {
        lastError = error;
        if (this.closed || error?.name === "AbortError" && controller.signal.aborted && this.closed) throw error;
        const retryable = error?.retryable ?? (error?.name === "AbortError" || error instanceof TypeError);
        if (!retryable || attempt === maximumAttempts) throw error;
        const waitMs = error?.retryAfter ? error.retryAfter * 1000 : Math.min(5000, 500 * 2 ** (attempt - 1));
        this.logger.warn(`Telegram ${method} so‘rovi qayta uriniladi (${attempt}/${maximumAttempts})`);
        await new Promise((resolve) => setTimeout(resolve, waitMs));
      } finally {
        clearTimeout(timer);
        this.controllers.delete(controller);
      }
    }
    throw lastError;
  }

  close() {
    this.closed = true;
    for (const controller of this.controllers) controller.abort();
    this.controllers.clear();
  }

  send(chatId, text, replyMarkup) {
    return this.call("sendMessage", {
      chat_id: chatId, text, parse_mode: "HTML",
      disable_web_page_preview: true,
      ...(replyMarkup ? { reply_markup: replyMarkup } : {}),
    });
  }

  edit(chatId, messageId, text, replyMarkup) {
    return this.call("editMessageText", {
      chat_id: chatId, message_id: messageId, text, parse_mode: "HTML",
      disable_web_page_preview: true,
      ...(replyMarkup ? { reply_markup: replyMarkup } : {}),
    });
  }

  answer(callbackId, text = "", showAlert = false) {
    return this.call("answerCallbackQuery", { callback_query_id: callbackId, text, show_alert: showAlert });
  }

  async poll(offset, timeout = 30) {
    return this.call("getUpdates", { offset, timeout, allowed_updates: ["message", "callback_query"] }, (timeout + 10) * 1000, 1);
  }
}
