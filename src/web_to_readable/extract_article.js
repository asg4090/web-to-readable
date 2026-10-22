({selector}) => {
    const visible = el => {
        const s = getComputedStyle(el);
        return s.display !== 'none' && s.visibility === 'visible' && Number(s.opacity) !== 0 &&
            (!el.checkVisibility || el.checkVisibility({checkOpacity:true, checkVisibilityCSS:true}));
    };
    let root, selected;
    if (selector) {
        root = document.querySelector(selector);
        if (!root) throw new Error('找不到指定的正文区域：' + selector);
        selected = selector;
    } else {
        for (const candidate of ['#js_content', 'article', 'main', '[role="main"]']) {
            const nodes = [...document.querySelectorAll(candidate)].filter(visible)
                .sort((a,b) => (b.innerText || '').length - (a.innerText || '').length);
            if (nodes.length && (nodes[0].innerText.trim() || nodes[0].querySelector('img,svg,canvas'))) {
                root = nodes[0]; selected = candidate; break;
            }
        }
        if (!root) {root = document.body; selected = 'body';}
    }
    if (!root || !visible(root)) throw new Error('正文区域不可见。');
    const clone = root.cloneNode(true);
    const originals = [root, ...root.querySelectorAll('*')];
    const copies = [clone, ...clone.querySelectorAll('*')];
    const images = [];
    const excluded = 'script,style,noscript,template,nav,footer,form,button,input,select,textarea,iframe,object,embed';
    // Remove inactive UI, scripts and hidden widgets while retaining visible article order.
    for (let i = 1; i < originals.length; i++) {
        const o = originals[i], c = copies[i];
        if (!clone.contains(c)) continue;
        if (o.matches(excluded) || !visible(o)) c.remove();
    }
    for (let i = 0; i < originals.length; i++) {
        const o = originals[i], c = copies[i];
        if (c !== clone && !clone.contains(c)) continue;
        // Make the saved HTML passive and independent of the original page's CSS/JS.
        for (const attr of [...c.attributes]) {
            if (attr.name.startsWith('on') || ['style','srcset','sizes','loading'].includes(attr.name)) c.removeAttribute(attr.name);
        }
        if (o.matches('a[href]')) {
            try {
                const href = new URL(o.getAttribute('href'), location.href);
                if (['http:','https:','mailto:','tel:'].includes(href.protocol)) c.setAttribute('href', href.href);
                else c.removeAttribute('href');
            } catch {c.removeAttribute('href');}
        }
        if (!o.matches('img,svg,canvas')) continue;
        const rect = o.getBoundingClientRect();
        let src = o.currentSrc || o.getAttribute('src') || o.getAttribute('data-src') || '';
        if (o.matches('img') && o.naturalWidth <= 1 && o.getAttribute('data-src')) src = o.getAttribute('data-src');
        if (rect.width <= 2 || rect.height <= 2 || (o.matches('img') && !src.trim())) {c.remove(); continue;}
        const id = 'image-' + String(images.length + 1).padStart(3, '0');
        o.setAttribute('data-web-export-id', id);
        if (src && !src.startsWith('data:') && !src.startsWith('blob:')) {
            try {src = new URL(src, location.href).href;} catch {src = '';}
        }
        const kind = o.tagName.toLowerCase();
        const alt = o.getAttribute('alt') || o.getAttribute('aria-label') || '';
        images.push({id, kind, source_url:src, alt, width:Math.round(rect.width), height:Math.round(rect.height),
            loaded:kind !== 'img' || (o.complete && o.naturalWidth > 0),
            svg:kind === 'svg' ? new XMLSerializer().serializeToString(o) : null});
        let target = c;
        if (kind !== 'img') {target = document.createElement('img'); c.replaceWith(target);}
        target.removeAttribute('src');
        target.setAttribute('alt', alt || '图片 ' + images.length);
        // Avoid a lazy loader fetching the remote source again in the local HTML.
        for (const attr of [...target.attributes]) if (attr.name.startsWith('data-')) target.removeAttribute(attr.name);
        target.setAttribute('data-export-image-id', id);
    }
    const meta = name => document.querySelector(`meta[property="${name}"],meta[name="${name}"]`)?.content?.trim() || '';
    const text = sel => document.querySelector(sel)?.innerText?.trim() || '';
    return {
        title:text('#activity-name') || meta('og:title') || text('h1') || document.title,
        author:meta('author') || text('#js_author_name') || text('[rel="author"]'),
        site_name:meta('og:site_name') || text('#js_name') || location.hostname,
        published_at:meta('article:published_time') || document.querySelector('time[datetime]')?.dateTime || text('#publish_time'),
        language:document.documentElement.lang || '', extraction_selector:selected,
        html:clone.outerHTML, text:root.innerText || '', images
    };
}
