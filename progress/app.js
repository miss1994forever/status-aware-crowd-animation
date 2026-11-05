'use strict';
(() => {
  const data = window.PROJECT_DATA;
  const key = 'animation-project-progress-personal-v1';
  const $ = selector => document.querySelector(selector);
  const known = new Set(data.tasks.map(task => task.id));
  let records = {}, filter = 'all', query = '', expanded = new Set();
  const notify = (text, error = false) => { $('#notice').textContent = text; $('#notice').classList.toggle('error', error); };
  function normalize(input) {
    if (!input || input.project !== 'animation-status-course' || input.version !== 1 || !input.records || typeof input.records !== 'object' || Array.isArray(input.records)) throw new Error('文件不是此工作台的个人记录。');
    const clean = {};
    for (const [id, item] of Object.entries(input.records)) {
      if (!known.has(id)) continue;
      if (!item || typeof item !== 'object' || typeof item.note !== 'string' || item.note.length > 4000 || typeof item.seen !== 'boolean' || typeof item.focus !== 'boolean') throw new Error('记录格式不正确，或单条备注超过 4000 字。');
      clean[id] = {seen: item.seen, focus: item.focus, note: item.note};
    }
    return clean;
  }
  const packet = () => ({project: 'animation-status-course', version: 1, exportedAt: new Date().toISOString(), records});
  function save() {
    try { localStorage.setItem(key, JSON.stringify(packet())); notify('个人记录已保存在当前浏览器，正式进度未改变。'); }
    catch { notify('浏览器无法保存记录。当前编辑仍在本页，请立即导出备份，刷新后可能丢失。', true); }
  }
  try { const saved = localStorage.getItem(key); if (saved) records = normalize(JSON.parse(saved)); }
  catch { notify('无法读取本地记录。本次可继续使用，请导出备份；已有记录未被主动删除。', true); }
  function element(tag, className, text) { const el = document.createElement(tag); if (className) el.className = className; if (text !== undefined) el.textContent = text; return el; }
  function recordFor(id) { return records[id] || {seen: false, focus: false, note: ''}; }
  function update(id, field, value) { records[id] = {...recordFor(id), [field]: value}; save(); }
  function render() {
    const visible = data.tasks.filter(task => (filter === 'all' || (filter === 'focus' ? recordFor(task.id).focus : task.category === filter)) && [task.title, task.status, task.evidence, task.owner].join(' ').toLowerCase().includes(query));
    $('#task-count').textContent = `${visible.length} / ${data.tasks.length}`;
    $('#empty').hidden = visible.length !== 0;
    $('#task-list').replaceChildren();
    for (const task of visible) {
      const details = element('details', 'task'); details.dataset.id = task.id; details.open = expanded.has(task.id);
      details.addEventListener('toggle', () => { if (!details.isConnected) return; if (details.open) expanded.add(task.id); else expanded.delete(task.id); });
      const summary = element('summary');
      const title = element('div', 'task-title', task.title); title.append(element('div', 'owner', `下一责任方：${task.owner}`));
      summary.append(title, element('span', `badge ${task.category}`, task.status));
      const body = element('div', 'task-body'); body.append(element('p', '', task.evidence));
      const personal = element('div', 'personal');
      for (const [field, label] of [['seen', '我已查看'], ['focus', '关注这项']]) {
        const control = element('label'); const input = element('input'); input.type = 'checkbox'; input.checked = recordFor(task.id)[field];
        input.addEventListener('change', () => { update(task.id, field, input.checked); if (filter === 'focus' && field === 'focus') render(); });
        control.append(input, document.createTextNode(label)); personal.append(control);
      }
      body.append(personal);
      const label = element('label', 'note-label', '我的备注 · 仅保存在当前浏览器');
      const note = element('textarea'); note.maxLength = 4000; note.placeholder = '例如：先看 M03 的摆臂对照，再决定是否保留。'; note.value = recordFor(task.id).note;
      note.addEventListener('input', () => update(task.id, 'note', note.value)); label.append(note); body.append(label);
      details.append(summary, body); $('#task-list').append(details);
    }
  }
  $('#updated').textContent = `正式进度核对：${data.checked}`;
  document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => {
    filter = button.dataset.filter;
    document.querySelectorAll('[data-filter]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    render();
  }));
  $('#search').addEventListener('input', event => { query = event.target.value.trim().toLowerCase(); render(); });
  function showDocument(id) {
    const doc = data.documents[id]; if (!doc) return;
    $('#doc-title').textContent = doc.title; $('#doc-text').textContent = doc.text; $('#doc-dialog').showModal(); $('#doc-dialog').scrollTop = 0;
  }
  for (const [id, doc] of Object.entries(data.documents)) {
    const button = element('button', 'doc-link'); button.dataset.doc = id; button.append(element('span', '', doc.title), element('span', '', '↗')); $('#document-list').append(button);
  }
  document.addEventListener('click', event => { const button = event.target.closest('[data-doc]'); if (button) showDocument(button.dataset.doc); });
  $('#close-doc').addEventListener('click', () => $('#doc-dialog').close());
  $('#export').addEventListener('click', () => {
    const blob = new Blob([JSON.stringify(packet(), null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob), link = element('a'); link.href = url; link.download = `动画项目-个人记录-${new Date().toISOString().slice(0, 10)}.json`; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 2000);
    notify('已发起个人记录下载。可将文件交给主聊天整理；它不会自动更新正式状态。');
  });
  $('#import').addEventListener('click', () => $('#import-file').click());
  $('#import-file').addEventListener('change', async event => {
    const file = event.target.files[0]; if (!file) return;
    try {
      if (file.size > 100000) throw new Error('文件超过 100 KB，请选择工作台导出的个人记录 JSON。');
      const incoming = normalize(JSON.parse(await file.text()));
      if (Object.keys(incoming).length === 0) throw new Error('文件中没有与当前任务匹配的记录。');
      if (!window.confirm('导入将覆盖文件中同名任务的个人勾选和备注，其他记录保留。是否继续？')) return;
      records = {...records, ...incoming}; save(); render();
    } catch (error) { notify(`未导入：${error.message}`, true); }
    finally { event.target.value = ''; }
  });
  render();
})();
