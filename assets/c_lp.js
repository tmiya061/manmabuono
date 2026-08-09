/* LP共通のスクリプト（2026-08-09 追加）
 *
 * やっていることは2つだけ。
 *   1. CTAクリックを dataLayer に流す（GTM経由でGA4へ。LP内のクリック率を測るため）
 *   2. 追従CTAバーの出し入れ（FVを過ぎたら出す。最初から出すとFVを隠すので）
 *
 * GA4の権限がまだ無いので今は「溜める」だけ。GTM側でトリガーを作れば読めるようになる。
 * 依存ライブラリなし・LPテンプレート以外では読み込まれない。
 */
(function () {
  'use strict';

  /* このファイルはLPの各セクションから読み込まれる（テーマの既存作法に合わせている）。
     同じsrcのscriptタグが複数あると**実行も複数回**走り、CTAのクリックが
     押した回数×セクション数だけ dataLayer に積まれてしまう。計測が壊れるので初回だけ動かす。 */
  if (window.__cLpInit) return;
  window.__cLpInit = true;

  window.dataLayer = window.dataLayer || [];

  /* 1. CTAクリック計測 --------------------------------------------------- */
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-lp-cta]');
    if (!btn) return;

    window.dataLayer.push({
      event: 'lp_cta_click',
      lp_id: btn.getAttribute('data-lp-id') || 'unknown',
      cta_position: btn.getAttribute('data-lp-cta') || 'unknown',
      cta_url: btn.getAttribute('href') || ''
    });
  });

  /* 2. 追従CTAバー ------------------------------------------------------- */
  var sticky = document.querySelector('[data-lp-sticky]');
  if (!sticky) return;

  /* 基準はFV。FVが無いLPもあり得るので、その時は素直に常時表示にする */
  var fv = document.querySelector('[data-lp-fv]');
  if (!fv) {
    sticky.classList.add('is-shown');
    return;
  }

  /* スクロール量を毎フレーム見るのは無駄なので IntersectionObserver で判定する。
     FVが画面から出たら表示、戻ったら隠す。 */
  if (!('IntersectionObserver' in window)) {
    sticky.classList.add('is-shown');
    return;
  }

  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        sticky.classList.toggle('is-shown', !entry.isIntersecting);
      });
    },
    { rootMargin: '0px', threshold: 0 }
  );
  observer.observe(fv);
})();
