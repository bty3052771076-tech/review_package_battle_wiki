(() => {
  const input = document.querySelector('[data-search-input]');
  const results = document.querySelector('[data-search-results]');
  if (!input || !results) return;

  let index = [];
  fetch('search/index.json')
    .then((res) => res.json())
    .then((data) => {
      index = data.items || [];
    })
    .catch(() => {
      results.innerHTML = '<p>索引加载失败。</p>';
    });

  const render = (items) => {
    if (!items.length) {
      results.innerHTML = '<p>没有匹配结果。</p>';
      return;
    }
    const html = items
      .slice(0, 50)
      .map((item) => {
        const tags = item.tags ? item.tags.join('、') : '';
        return `
          <article style="padding:12px 0; border-bottom:1px solid var(--line);">
            <h3 style="margin:0 0 4px;"><a href="${item.url}">${item.title}</a></h3>
            <p style="margin:0 0 6px; color: var(--muted);">${item.summary || ''}</p>
            <div style="font-size:12px; color: var(--muted);">类型：${item.type || 'page'}${tags ? `｜标签：${tags}` : ''}</div>
          </article>
        `;
      })
      .join('');
    results.innerHTML = html;
  };

  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();
    if (!q) {
      results.innerHTML = '<p>输入关键词开始搜索。</p>';
      return;
    }
    const matched = index.filter((item) => {
      const hay = `${item.title} ${item.summary || ''} ${(item.tags || []).join(' ')} ${item.type || ''}`.toLowerCase();
      return hay.includes(q);
    });
    render(matched);
  });
})();
