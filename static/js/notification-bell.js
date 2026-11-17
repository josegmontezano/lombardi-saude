/* Lombardi Saude notification bell: no external services, no notification landing page. */
(() => {
  'use strict';
  const bell = document.getElementById('lombardi-notification-bell');
  if (!bell) return;
  const list = document.getElementById('lombardi-notification-items');
  const moreButton = document.getElementById('lombardi-notification-more');
  const csrf = bell.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
  const returnTo = bell.dataset.currentUrl || '/';

  document.addEventListener('click', event => {
    if (bell.open && !bell.contains(event.target)) bell.open = false;
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && bell.open) {
      bell.open = false;
      bell.querySelector('summary')?.focus();
    }
  });
  if (new URLSearchParams(location.search).get('notificacoes') === '1') bell.open = true;

  function postAction(action, label, returnAfter) {
    const form = document.createElement('form');
    form.method = 'post';
    form.action = action;
    const token = document.createElement('input');
    token.type = 'hidden';
    token.name = 'csrfmiddlewaretoken';
    token.value = csrf || '';
    form.appendChild(token);
    if (returnAfter) {
      const field = document.createElement('input');
      field.type = 'hidden';
      field.name = 'return_to';
      field.value = returnTo;
      form.appendChild(field);
    }
    const button = document.createElement('button');
    button.type = 'submit';
    button.textContent = label;
    form.appendChild(button);
    return form;
  }
  function appendNotification(item) {
    const row = document.createElement('article');
    row.className = `lx-notification-item${item.unread ? ' is-unread' : ''}`;
    const dot = document.createElement('span');
    dot.className = 'lx-notification-dot';
    dot.setAttribute('aria-hidden', 'true');
    row.appendChild(dot);
    const copy = document.createElement('div');
    copy.className = 'lx-notification-copy';
    const title = document.createElement('strong');
    title.textContent = item.title;
    const msg = document.createElement('p');
    msg.textContent = item.message;
    const time = document.createElement('time');
    time.textContent = item.when;
    copy.append(title, msg, time);
    const actions = document.createElement('div');
    actions.className = 'lx-notification-actions';
    const id = encodeURIComponent(item.id);
    if (item.has_link) actions.appendChild(postAction(`/notificacoes/${id}/abrir/`, 'Abrir assunto', false));
    if (item.unread) actions.appendChild(postAction(`/notificacoes/${id}/ler/`, 'Marcar como lida', true));
    if (actions.children.length) copy.appendChild(actions);
    row.appendChild(copy);
    list.appendChild(row);
  }
  if (moreButton) {
    moreButton.addEventListener('click', async () => {
      if (moreButton.disabled) return;
      moreButton.disabled = true;
      moreButton.textContent = 'Carregando...';
      try {
        const offset = Number.parseInt(bell.dataset.offset || '0', 10);
        const response = await fetch(`${bell.dataset.api}?offset=${offset}`, {
          credentials: 'same-origin', headers: {'Accept': 'application/json'}
        });
        if (!response.ok) throw new Error('Falha na consulta');
        const data = await response.json();
        data.items.forEach(appendNotification);
        bell.dataset.offset = String(data.next_offset);
        if (!data.has_more) {
          moreButton.remove();
          return;
        }
        moreButton.textContent = 'Carregar notificações anteriores';
      } catch {
        moreButton.textContent = 'Não foi possível carregar. Tentar novamente';
      } finally {
        moreButton.disabled = false;
      }
    });
  }
})();
