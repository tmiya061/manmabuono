/* 画像積み上げ型LP：固定背景の切り替え（2026-08-10 追加）
 *
 * 引用元（ペトコト）は position:fixed の全画面背景を3枚重ね、
 * スクロールで opacity を入れ替えて「背景だけが変わる」演出をしていた。
 * PCで390pxの細いカラムを見せるとき、左右の余白が寂しくならないようにする仕掛け。
 *
 * スクロール量を毎フレーム測ると重いので IntersectionObserver で判定する。
 * data-lp-bg-trigger="N" を持つブロックが画面中央付近に来たら背景Nに切り替える。
 */
(function () {
  'use strict';

  if (window.__cLpStackInit) return;
  window.__cLpStackInit = true;

  var items = document.querySelectorAll('[data-lp-bg]');
  var triggers = document.querySelectorAll('[data-lp-bg-trigger]');
  if (!items.length || !triggers.length) return;

  if (!('IntersectionObserver' in window)) return;

  function activate(no) {
    for (var i = 0; i < items.length; i++) {
      items[i].classList.toggle('is-active', items[i].getAttribute('data-lp-bg') === no);
    }
  }

  /* 画面の上下40%を無視して、真ん中20%の帯に入ったものだけを「今見ているブロック」とみなす。
     こうしないと、短いブロックが並ぶ箇所で背景がチカチカ切り替わる。 */
  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          activate(entry.target.getAttribute('data-lp-bg-trigger'));
        }
      });
    },
    { rootMargin: '-40% 0px -40% 0px', threshold: 0 }
  );

  for (var i = 0; i < triggers.length; i++) observer.observe(triggers[i]);
})();
