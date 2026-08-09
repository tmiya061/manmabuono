# LPシステム（広告の受け皿）

> 作成: 2026-08-09 ／ 用途: リスティング（Google広告）・Facebook広告の着地ページを量産するための土台
> 1本目の対象＝**ドライ×ウェット セット定期便**（オーナー決定 2026-08-09）

---

## 0. 3行まとめ

- LPは **`templates/page.lp-◯◯.json`** を作れば1本増える。`lp-` で始まるサフィックスにすると**グローバルヘッダー・フッター・パンくずが自動で消える**（`layout/theme.liquid`）。
- 部品は `c_lp-header` / `c_lp-fv` / `c_lp-cta` / `c_lp-footer` の4つ。CTAは `snippets/c_lp-cta-button.liquid` に集約してあり、**押された位置が計測できるよう `data-lp-cta` が入っている**。
- 🔴 **広告のコンバージョン計測は現状ゼロ**（§4）。LPだけ作っても「効いたか」は読めない。出稿前に §4 を必ず片付けること。

---

## 1. LPを1本作る手順

1. `templates/page.lp-◯◯.json` を作る（`page.lp-set-teiki.json` をコピーするのが早い）
2. Shopify管理画面で **ページを作成** → 右側の「テンプレート」で `page.lp-◯◯` を選ぶ
   - 中身が固まるまでは**非公開のまま**にしておく（公開＝西川さん確認が要る）
3. 文言・CTAの行き先はテンプレJSON か テーマエディタのどちらでも編集できる（JSON側がGit管理の正）
4. ローカル確認 → オーナー確認 → 西川さん確認 → 公開

### ローカルでの見方（非公開ページは404になる）

Shopifyは**非公開ページを直接開くと404**を返す。公開せずに見た目を確認するには、
`shopify theme dev` を立てて**既に公開されている適当なページに `?view=` でテンプレートを差し込む**。

```bash
shopify theme dev --store 007a21-4.myshopify.com
open "http://127.0.0.1:9292/pages/guide?view=lp-set-teiki"
```

`?view=lp-set-teiki` は `templates/page.lp-set-teiki.json` を使って描画する指定。
`template.suffix` も `lp-set-teiki` になるのでLPモード（ヘッダー・フッター非表示）も一緒に確認できる。
⚠️ ポート9292はオーナーが既に `theme dev` を動かしていることがある。**落とさずに相乗りする。**

### セクションの並べ方（基本形）

```
c_lp-header          ← ロゴだけ。リンクにしない（トップへ逃がさない）
c_lp-fv              ← 見出し・リード・要点3つ・CTA①
（本文セクション）      ← 既存の c_collection-lp / c_topVoices 等を流用してよい
c_lp-cta (middle)    ← CTA②
（本文セクション）
c_lp-cta (bottom)    ← CTA③
c_lp-cta (sticky)    ← 追従バー。**ページに1つだけ**
c_lp-footer          ← 特商法・プライバシー・返品・問い合わせ（広告審査で必要）
```

### 触ってはいけないところ

- **`c_lp-footer` の4リンクは消さない。** Google広告・Meta広告の審査は、販売者情報・特定商取引法に基づく表記・プライバシーポリシー・問い合わせ先へLPから辿れるかを見る。出口を絞るLPでもここは残す
- 特商法は独立ページが無く **`/pages/guide#guide-law`**（ご利用ガイド内）。リンクを変える時は `c_lp-footer` / `sections/footer.liquid` / `snippets/header-drawer.liquid` の3箇所

---

## 2. LPモードの仕組み（`layout/theme.liquid`）

```liquid
assign is_lp = false
if template.suffix contains 'lp-'
  assign is_lp = true
endif
```

`is_lp` が true のとき `header-group` / `footer-group` / パンくず を出力しない。
**サフィックスが無い従来のページは一切影響を受けない**（`unless is_lp` で囲っただけ）。

`main` に `c_lp-main` クラスが付くので、LP専用の上書きが要るときはここを起点にする。

---

## 3. 計測（今できること・できないこと）

### できる：LPに何人来て何%買ったか（Shopifyだけで読める）

```bash
python3 scripts/lp_report.py /pages/set-teiki --since -30d --daily
```

utm_source別・utm_campaign別のセッションとCVRが出る。ストア全体との比較も一緒に出る。

### できる（仕込み済み・GTM設定待ち）：LP内のどのボタンが押されたか

CTAボタンには以下が入っている（`snippets/c_lp-cta-button.liquid` ＋ `assets/c_lp.js`）。

```js
dataLayer.push({ event: 'lp_cta_click', lp_id: 'set-teiki', cta_position: 'fv', cta_url: '…' })
```

GTM（`GTM-KJXQSLRX`）で「カスタムイベント `lp_cta_click`」のトリガーを作り、GA4イベントに繋げば
**FV / 中盤 / 最後 / 追従バー のどれが押されているか＝LP内のクリック率**が読める。
→ **GA4（`G-60GQ78JQF4`）の権限が無いため未設定。** 仕込みだけ先に入れてある。

### できない：広告のコンバージョン計測（→ §4）

---

## 4. 🔴 出稿前に必要なもの（2026-08-09 時点で全部欠けている）

storefront の `webPixelsConfigList` を確認したところ、入っているのは Shopify 標準の2つだけ。
GTMコンテナの中身も GA4（googtag）3つのみで、広告用のタグは1つも無い。

| 何が要るか | 現状 | 無いとどうなるか |
|---|---|---|
| **GA4の閲覧・編集権限**（`G-60GQ78JQF4`） | ❌ 権限なし（タグは7/5から稼働・データは溜まっている） | LP内クリック率が読めない。Google広告へのコンバージョン連携もできない |
| **Google広告のコンバージョン計測** | ❌ 未導入（GTMに `awct` タグ無し） | リスティングが「表示・クリック」までしか分からない。入札最適化も効かない |
| **Meta Pixel**（Facebook広告） | ❌ 未導入（web pixel にFacebookのエントリ無し） | Facebook広告のCVが1件も計測されない。リターゲティングも不可 |
| **特商法・販売者情報のLPからの導線** | ✅ `c_lp-footer` で対応済み | 広告審査で落ちる |

**順番**：GA4権限 → GTMでGA4コンバージョン定義 → Google広告へインポート ／ Meta Pixel は Facebook販売チャネル（またはGTM）で追加。

---

## 5. UTM規約（ここを守らないとレポートが読めなくなる）

広告のリンクには必ず付ける。`lp_report.py` はこの規約前提で集計する。

| パラメータ | 入れる値 | 例 |
|---|---|---|
| `utm_source` | 媒体 | `google` / `facebook` / `ig` / `yahoo` |
| `utm_medium` | 種別 | `cpc`（広告）/ `social`（SNS投稿）/ `qr`（同梱チラシ） |
| `utm_campaign` | 何の訴求か | `set-teiki` / `set-teiki-mizubun` |
| `utm_content` | A/Bの区別 | `fv-a` / `fv-b` |

```
https://manmabuono.jp/pages/set-teiki?utm_source=google&utm_medium=cpc&utm_campaign=set-teiki&utm_content=fv-a
```

- **`utm_campaign` はLPごとに1つ**。同じLPに複数キャンペーンを当てると、どのLPが効いたか分からなくなる
- 京都駅の同梱チラシQRも同じ規約で（`utm_medium=qr`）。広告と同じ土俵で比較できる

---

## 6. 1本目（セット定期便）の状態

`templates/page.lp-set-teiki.json` は**枠だけ**作ってある。文言は `＜要・西川さん確認＞` のまま。

🔴 **そもそも「セット定期便」という商品がまだ存在しない。**
Shopifyの販売プラングループ `定期購入` は既存31商品に紐づく**単品の定期便**で、
「ドライ＋ウェットを◯週間分にまとめたセット」は商品として作られていない。

決まっていないのは設計シート（`.company/projects/clients/manmabuono/set_teiki_design_sheet.md`）の①〜⑥：
サイズ帯の区切り／給餌量→セット内容／おまかせ構成／選べるウェット候補／価格／西川さんのコメント。

**この6つが埋まらない限り、LPの文言もCTAの行き先も決まらない。** LPの枠と計測は先に作ったので、
埋まった時点で流し込むだけの状態になっている。
