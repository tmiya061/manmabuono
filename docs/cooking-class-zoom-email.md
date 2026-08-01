# お料理教室：注文確認メールへのZoom案内差し込み

オンライン料理教室（`online-cooking-class`）を購入した注文の**注文確認メールにだけ**、Zoomの参加案内を自動表示する。Flow・アプリ不要。

## 前提（運用方針・2026-08-02 オーナー決定）

- Zoomは**定期ミーティング＝毎回同じURL**で運用する（B案）。
- URLはメール内のみに記載し、サイト上には載せない。**待機室 or パスコードを必ず有効化**する（URL拡散対策）。
- 西川さんに定期ミーティングを1本発行してもらい、URL・ID・パスコードを下記プレースホルダに入れる。

## 設定手順（管理画面・2分）

1. Shopify管理画面 → **設定 → 通知 → 注文の確認** → 「コードを編集」
2. 本文HTML内、挨拶ブロック（`<p>ご注文いただきありがとうございます...` 付近）の**直後**に下記スニペットを貼る
3. プレースホルダ3箇所（`ZOOM_URL` / `MEETING_ID` / `PASSCODE`）を実物に置換
4. 「プレビュー」で通常商品の注文に出ないことを確認 → 保存
5. テスト注文（¥500・決済直前まで、または実注文して即返金）で実メールを確認

> ⚠️ 通知テンプレートはAPIで編集できないため手作業。テーマのGitでも追えないので、**変更したら docs/admin-changelog.md に1行残す**こと。

## スニペット

```liquid
{% assign has_cooking_class = false %}
{% assign class_dates = "" %}
{% for line in subtotal_line_items %}
  {% if line.product.handle == 'online-cooking-class' %}
    {% assign has_cooking_class = true %}
    {% assign class_dates = class_dates | append: line.variant.title | append: "／" %}
  {% endif %}
{% endfor %}
{% if has_cooking_class %}
<table width="100%" cellpadding="0" cellspacing="0" style="margin: 24px 0; border: 1px solid #e5e5e5; border-radius: 8px;">
  <tr>
    <td style="padding: 20px 24px;">
      <p style="margin: 0 0 12px; color: #FF7B5E; font-weight: bold; font-size: 15px;">オンライン料理教室のご参加方法</p>
      <p style="margin: 0 0 8px; color: #3C3C3C; font-size: 14px; line-height: 1.8;">
        ご参加日時：{{ class_dates | split: "／" | join: "、" }}
      </p>
      <p style="margin: 0 0 8px; color: #3C3C3C; font-size: 14px; line-height: 1.8;">
        当日は開始5分前より、こちらのZoomからご入室ください。<br>
        <a href="ZOOM_URL" style="color: #FF7B5E;">ZOOM_URL</a><br>
        ミーティングID：MEETING_ID ／ パスコード：PASSCODE
      </p>
      <p style="margin: 0; color: #3C3C3C; font-size: 13px; line-height: 1.8;">
        食材リストと分量表は、開催前日までに別途メールでお送りします。<br>
        このメールは大切に保管してください。
      </p>
    </td>
  </tr>
</table>
{% endif %}
```

## 補足

- 開催日はバリアント名（例：8月9日（日）10:00〜11:30）をそのまま表示する。複数回まとめ買いにも対応（「、」区切りで並ぶ）。
- URLを変えたくなったら（漏れた等）、Zoom側で定期ミーティングを作り直し、このテンプレの1箇所を差し替えるだけ。
- 「食材リストは前日までに別途メール」の一文は運用に合わせて調整（不要なら削除）。
