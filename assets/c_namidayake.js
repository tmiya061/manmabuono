/* Checkout is enabled only by the Shopify-rendered data-commerce flag. */
(() => {
  const root = document.querySelector('[data-namidayake-preview]');
  if (!root) return;
  const state = { flavor: 'chicken', size: null };
  const flavorLabel = () => state.flavor === 'chicken' ? 'チキン' : 'フィッシュ';
  const catalog = {"fish-150": {"handle": "だし薫る犬のごはん-フィッシュ-150g", "id": 41086962794557, "plan": 1789984829, "price": 89100, "regular": 99000, "available": true}, "fish-800": {"handle": "だし薫る犬のごはん-フィッシュ-800g", "id": 41086962827325, "plan": 1789984829, "price": 356400, "regular": 396000, "available": true}, "chicken-150": {"handle": "だし薫る犬のごはん-チキン-150g", "id": 41086962860093, "plan": 1789984829, "price": 89100, "regular": 99000, "available": true}, "chicken-800": {"handle": "だし薫る犬のごはん-チキン", "id": 41086962892861, "plan": 1789984829, "price": 356400, "regular": 396000, "available": true}};
  const money = value => (value / 100).toLocaleString('ja-JP');
  const offers = [...root.querySelectorAll('[data-offer]')];
  const selectedRing = offers[0].querySelector('[data-size="800"] [data-name="選択丸"] img').src;
  const emptyRing = offers[0].querySelector('[data-size="150"] [data-name="選択丸"] img').src;
  function render() {
    const faqProduct = catalog['chicken-800'];
    root.querySelectorAll('[data-faq-price]').forEach(node => {
      node.textContent = node.dataset.faqPrice === 'regular' ? `通常価格${money(faqProduct.regular)}円（税込）` : node.dataset.faqPrice === 'repeat' ? `2回目以降も${money(faqProduct.price)}円（税込）です。` : `定期価格${money(faqProduct.price)}円（税込）`;
    });
    offers.forEach(offer => {
      offer.querySelectorAll('[data-flavor]').forEach(button => {
        const selected = button.dataset.flavor === state.flavor;
        button.setAttribute('aria-pressed', String(selected));
        button.querySelector('p').textContent = (selected ? '✓ ' : '') + (button.dataset.flavor === 'chicken' ? 'チキン' : 'フィッシュ');
      });
      offer.querySelectorAll('[data-size]').forEach(button => {
        const selected = button.dataset.size === state.size;
        const product = catalog[`${state.flavor}-${button.dataset.size}`];
        const prices = button.querySelectorAll(':scope > p');
        prices[2].textContent = money(product.regular) + '円';
        prices[4].textContent = money(product.price);
        button.setAttribute('aria-pressed', String(selected));
        button.querySelector('[data-name="選択丸"] img').src = selected ? selectedRing : emptyRing;
      });
      offer.querySelector('[data-selection-label]').textContent = state.flavor && state.size ? `${flavorLabel()}／${state.size}gを選択中` : `${flavorLabel()}／容量を選択してください`;
      // The Figma badge and selection point move with the selected capacity.
      const delta = state.size === '150' ? -112 / 3.9 : 0;
      ['[data-selected-badge]', '[data-selected-dot]'].forEach(selector => {
        offer.querySelector(selector).style.visibility = state.size ? 'visible' : 'hidden';
        offer.querySelector(selector).style.translate = `0 ${delta}cqw`;
      });
    });
  }
  const dialog = document.querySelector('[data-preview-dialog]');
  let pickerMode = false;
  function renderPicker() {
    dialog.querySelectorAll('[name="lp-modal-size"]').forEach(input => { const item = catalog[`${state.flavor}-${input.value}`]; const label = input.closest('label'); label.querySelector('[data-modal-regular]').textContent = '通常 ' + money(item.regular) + '円'; label.querySelector('[data-modal-price]').innerHTML = money(item.price) + '<small>円</small>';  });
    dialog.querySelectorAll('[name="lp-modal-flavor"]').forEach(input => { input.checked = input.value === state.flavor; });
    dialog.querySelectorAll('[name="lp-modal-size"]').forEach(input => { input.checked = input.value === state.size; });
    dialog.querySelector('[data-preview-summary]').textContent = state.flavor && state.size ? `だし薫る犬のごはん ${flavorLabel()} ${state.size}g` : '商品を選択してください';
  }
  dialog.querySelector('[data-modal-picker]').addEventListener('change', event => {
    if (event.target.name === 'lp-modal-flavor') state.flavor = event.target.value;
    if (event.target.name === 'lp-modal-size') state.size = event.target.value;
    dialog.querySelector('[data-preview-notice]').hidden = true;
    render(); renderPicker();
  });
  root.addEventListener('click' , event => {
    const flavor = event.target.closest('[data-flavor]');
    const size = event.target.closest('[data-size]');
    if (flavor) { state.flavor = flavor.dataset.flavor; render(); }
    if (size) { state.size = size.dataset.size; render(); }
    if (event.target.closest('[data-preview-checkout]')) {
      const button = event.target.closest('[data-preview-checkout]');
      proceedToCheckout(button, false);
    }
  });
  let closeTimer;
  function closeModal() {
    if (!dialog.open || dialog.classList.contains('is-closing')) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { dialog.close(); return; }
    dialog.classList.add('is-closing');
    closeTimer = window.setTimeout(() => { dialog.close(); dialog.classList.remove('is-closing'); }, 180);
  }
  dialog.querySelector('[data-preview-close]').addEventListener('click', closeModal);
  dialog.addEventListener('cancel', event => { event.preventDefault(); closeModal(); });
  dialog.addEventListener('close', () => { window.clearTimeout(closeTimer); dialog.classList.remove('is-closing'); });
  let checkoutBusy = false;
  const routeRoot = window.Shopify?.routes?.root || '/';
  async function refreshProduct(key) {
    const item = catalog[key];
    const response = await fetch(`${routeRoot}products/${encodeURIComponent(item.handle)}.js`, {credentials:'same-origin',cache:'no-store'});
    if (!response.ok) throw new Error('商品情報を取得できませんでした。時間をおいて再度お試しください。');
    const product = await response.json();
    const variant = product.variants.find(v => v.id === item.id);
    const allocation = variant?.selling_plan_allocations?.find(a => a.selling_plan_id === item.plan);
    if (!allocation) throw new Error('この商品の定期購入プランを確認できません。お問い合わせください。');
    Object.assign(item,{price:allocation.price,regular:variant.price,available:variant.available});
    return item;
  }
  async function proceedToCheckout(button, fromModal = true) {
    const offer = button.closest('[data-offer]');
    const notice = fromModal ? dialog.querySelector('[data-preview-notice]') : root.querySelector(`[data-checkout-notice="${offer.dataset.section}"]`);
    notice.hidden = true;
    if (checkoutBusy) return;
    if (!state.flavor || !state.size) {
      notice.textContent = '容量を選択してください'; notice.hidden = false;
      if (fromModal) dialog.querySelector('[name="lp-modal-size"]').focus();
      else { offer.querySelector('[data-selection-label]').textContent = '容量を選択してください'; offer.querySelector('[data-size]').focus(); }
      return;
    }
    if (root.dataset.commerce !== 'true') {
      notice.textContent = 'ローカルプレビューでは決済へ進めません。公開ページでご利用ください。';
      notice.hidden = false;
      return;
    }
    checkoutBusy = true;
    const originalHtml = button.innerHTML;
    button.disabled = true; button.setAttribute('aria-busy','true');
    if (fromModal) button.textContent = '購入手続きへ進んでいます';
    dialog.querySelectorAll('input').forEach(input => { input.disabled = true; });
    try {
      const key = `${state.flavor}-${state.size}`;
      const previousPrice = catalog[key].price;
      const item = await refreshProduct(key);
      render(); renderPicker();
      if (!item.available) throw new Error('選択した商品は現在売り切れです。別の商品をお選びください。');
      if (previousPrice !== item.price) throw new Error('価格が更新されました。表示価格をご確認のうえ、もう一度「決済に進む」を押してください。');
      const cartResponse = await fetch(`${routeRoot}cart.js`,{credentials:'same-origin',cache:'no-store'});
      if (!cartResponse.ok) throw new Error('カートを確認できませんでした。再度お試しください。');
      const cart = await cartResponse.json();
      const alreadyAdded = cart.items.some(line => line.variant_id === item.id && line.selling_plan_allocation?.selling_plan?.id === item.plan && line.properties?._lp_source === 'namidayake');
      if (!alreadyAdded) {
        const response = await fetch(`${routeRoot}cart/add.js`, {method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({items:[{id:item.id,quantity:1,selling_plan:item.plan,properties:{_lp_source:'namidayake'}}]})});
        const result = await response.json();
        if (!response.ok) throw new Error(result.description || 'カートに追加できませんでした。再度お試しください。');
        const added = result.items?.[0];
        if (added?.selling_plan_allocation?.selling_plan?.id !== item.plan) throw new Error('定期購入を確認できませんでした。カートをご確認ください。');
      }
      window.location.assign(`${routeRoot}checkout`);
    } catch (error) {
      notice.textContent = error.message || '処理に失敗しました。再度お試しください。';
      notice.hidden = false;
      if (!fromModal) notice.scrollIntoView?.({block:'nearest',behavior:'smooth'});
    } finally {
      checkoutBusy = false; button.disabled = false; button.removeAttribute('aria-busy'); button.innerHTML = originalHtml;
      dialog.querySelectorAll('input').forEach(input => { input.disabled = false; });
    }
  }
  dialog.querySelector('[data-preview-proceed]').addEventListener('click', event => proceedToCheckout(event.currentTarget));
  if (root.dataset.commerce === 'true') {
    Promise.allSettled(Object.keys(catalog).map(refreshProduct)).then(() => { render(); renderPicker(); });
  }
  const viewport = root.querySelector('.c_namidayake__reviews-viewport');
  const cards = [...root.querySelector('.c_namidayake__reviews-track').children];
  let review = 0;
  function fitReview() {
    if (cards[review].offsetHeight) viewport.style.setProperty('height', `${cards[review].offsetHeight + viewport.clientWidth * 16 / 390}px`, 'important');
  }
  root.querySelectorAll('[data-review-index]').forEach(button => button.addEventListener('click', () => {
    review = Number(button.dataset.reviewIndex);
    viewport.scrollTo({left:(cards[1].offsetLeft-cards[0].offsetLeft)*review, behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
  }));
  if (typeof ResizeObserver !== 'undefined') {
    const observer = new ResizeObserver(fitReview);
    cards.forEach(card => observer.observe(card));
  }
  function updateReview() {
    const step = cards[1].offsetLeft - cards[0].offsetLeft;
    review = Math.max(0, Math.min(2, Math.round(viewport.scrollLeft / step)));
    root.querySelector('[data-review-count]').textContent = `${review + 1} / 3`;
    root.querySelectorAll('[data-review-index]').forEach(button => button.setAttribute('aria-current', String(Number(button.dataset.reviewIndex) === review)));
    fitReview();
  }
  root.querySelectorAll('[data-review-step]').forEach(button => button.addEventListener('click', () => {
    review = (review + Number(button.dataset.reviewStep) + cards.length) % cards.length;
    const step = cards[1].offsetLeft - cards[0].offsetLeft;
    viewport.scrollTo({ left: step * review, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  }));
  viewport.addEventListener('scroll', updateReview, { passive: true });
  viewport.addEventListener('keydown', event => {
    if (!['ArrowLeft','ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    root.querySelector(`[data-review-step="${event.key === 'ArrowLeft' ? '-1' : '1'}"]`).click();
  });
  const faqs = [...root.querySelectorAll('.c_namidayake__faq')];
  let desiredFaq = null;
  let faqBusy = false;
  async function animateFaq(item, opening) {
    const start = item.getBoundingClientRect().height;
    if (opening) item.open = true;
    const end = opening ? item.getBoundingClientRect().height : (() => {
      const style = getComputedStyle(item);
      return item.querySelector('summary').getBoundingClientRect().height + parseFloat(style.paddingTop || 0) + parseFloat(style.paddingBottom || 0) + parseFloat(style.borderTopWidth || 0) + parseFloat(style.borderBottomWidth || 0);
    })();
    if (item.animate && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      item.style.overflow = 'hidden';
      const animation = item.animate([{height:`${start}px`},{height:`${end}px`}], {duration:240,easing:'cubic-bezier(.22,1,.36,1)'});
      await animation.finished.catch(() => {});
      item.style.overflow = '';
    }
    if (!opening) item.open = false;
  }
  async function reconcileFaq() {
    if (faqBusy) return;
    faqBusy = true;
    try {
      while (true) {
        const target = desiredFaq;
        const changing = faqs.filter(item => item.open !== (item === target));
        if (!changing.length) break;
        await Promise.all(changing.map(item => animateFaq(item, item === target)));
      }
    } finally { faqBusy = false; }
  }
  faqs.forEach(item => item.querySelector('summary').addEventListener('click', event => {
    event.preventDefault();
    desiredFaq = desiredFaq === item ? null : item;
    reconcileFaq();
  }));
  const stickyCta = document.querySelector('[data-sticky-cta]');
  const finalOffer = root.querySelector('#section-295-1043');
  function updateStickyCta() {
    const visible = window.scrollY > 8 && finalOffer.getBoundingClientRect().top >= window.innerHeight;
    stickyCta.classList.toggle('is-visible', visible);
    stickyCta.setAttribute('aria-hidden', String(!visible));
    stickyCta.inert = !visible;
  }
  stickyCta.querySelector('button').addEventListener('click', event => {
    event.preventDefault();
    pickerMode = true;
    dialog.querySelector('[data-modal-picker]').hidden = false;
    dialog.querySelector('[data-preview-title]').textContent = '商品を選択してください';
    dialog.querySelector('[data-preview-actions]').hidden = false;
    dialog.querySelector('[data-preview-close]').hidden = false;
    dialog.querySelector('[data-preview-notice]').hidden = true;
    renderPicker();
    dialog.showModal();
  });
  window.addEventListener('scroll', updateStickyCta, {passive:true});
  window.addEventListener('resize', updateStickyCta);
  if (typeof ResizeObserver !== 'undefined') new ResizeObserver(updateStickyCta).observe(root);
  updateStickyCta();
  render();
})();
