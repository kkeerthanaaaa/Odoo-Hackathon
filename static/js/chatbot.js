/* Dayflow Assistant — floating widget + full-page chat client. */
(function (global) {
  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function renderMessage(container, sender, message, time) {
    const row = document.createElement('div');
    row.className = 'chat-bubble-row ' + (sender === 'user' ? 'from-user' : 'from-bot');
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';
    bubble.innerHTML = escapeHtml(message).replace(/\n/g, '<br>');
    row.appendChild(bubble);
    if (time) {
      const t = document.createElement('div');
      t.className = 'chat-bubble-time';
      t.textContent = time;
      row.appendChild(t);
    }
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
    return row;
  }

  function renderTyping(container) {
    const row = document.createElement('div');
    row.className = 'chat-bubble-row from-bot chat-typing-row';
    row.innerHTML = '<div class="chat-bubble chat-typing"><span></span><span></span><span></span></div>';
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
    return row;
  }

  async function sendMessage(text) {
    const resp = await fetch('/api/chatbot/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    });
    if (!resp.ok) {
      throw new Error('Request failed');
    }
    return resp.json();
  }

  async function loadHistory() {
    const resp = await fetch('/api/chatbot/history');
    if (!resp.ok) return [];
    return resp.json();
  }

  function wireForm(form, input, container, onAfterSend) {
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      input.value = '';
      input.disabled = true;
      renderMessage(container, 'user', text, null);
      const typingRow = renderTyping(container);
      try {
        const data = await sendMessage(text);
        typingRow.remove();
        if (data.error) {
          renderMessage(container, 'bot', data.error, null);
        } else {
          renderMessage(container, 'bot', data.reply, data.created_on);
        }
      } catch (err) {
        typingRow.remove();
        renderMessage(container, 'bot', "Sorry, I couldn't reach the server. Please try again.", null);
      } finally {
        input.disabled = false;
        input.focus();
        if (onAfterSend) onAfterSend();
      }
    });
  }

  const DayflowChatbot = {
    initWidget: function () {
      const widget = document.getElementById('chatbotWidget');
      if (!widget) return;
      const fab = document.getElementById('chatbotFab');
      const panel = document.getElementById('chatbotPanel');
      const closeBtn = document.getElementById('chatbotCloseBtn');
      const messages = document.getElementById('chatbotWidgetMessages');
      const form = document.getElementById('chatbotWidgetForm');
      const input = document.getElementById('chatbotWidgetInput');
      let loaded = false;

      function openPanel() {
        panel.classList.add('open');
        fab.classList.add('active');
        if (!loaded) {
          loaded = true;
          loadHistory().then(function (history) {
            if (!history.length) {
              renderMessage(messages, 'bot',
                "Hi! I'm the Dayflow Assistant. Ask me about your leave balance, attendance, payslip, or profile — or type \"help\" to see everything I can do.",
                null);
            } else {
              history.forEach(function (m) {
                renderMessage(messages, m.sender, m.message, m.created_on);
              });
            }
            input.focus();
          }).catch(function () {
            renderMessage(messages, 'bot', "Hi! I'm the Dayflow Assistant. How can I help?", null);
          });
        } else {
          input.focus();
        }
      }

      function closePanel() {
        panel.classList.remove('open');
        fab.classList.remove('active');
      }

      fab.addEventListener('click', function () {
        if (panel.classList.contains('open')) {
          closePanel();
        } else {
          openPanel();
        }
      });
      closeBtn.addEventListener('click', closePanel);

      wireForm(form, input, messages);
    },

    initPage: function () {
      const messages = document.getElementById('chatbotMessages');
      const form = document.getElementById('chatbotPageForm');
      const input = document.getElementById('chatbotPageInput');
      const clearBtn = document.getElementById('chatbotClearBtn');
      if (!messages || !form) return;

      messages.scrollTop = messages.scrollHeight;
      wireForm(form, input, messages);

      if (clearBtn) {
        clearBtn.addEventListener('click', async function () {
          if (!confirm('Clear your chat history with the assistant?')) return;
          try {
            await fetch('/api/chatbot/clear', { method: 'POST' });
            messages.innerHTML = '';
            renderMessage(messages, 'bot',
              "Chat history cleared. Ask me anything about your leave, attendance, payroll, or profile.",
              null);
          } catch (err) { /* ignore */ }
        });
      }
    },
  };

  global.DayflowChatbot = DayflowChatbot;
})(window);
