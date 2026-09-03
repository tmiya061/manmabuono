#!/usr/bin/env python3
"""同梱物のQR流入レポート（ShopifyQL・読み取り専用）

リーフレット／クーポンカードに刷った QR（`utm_medium=qr`）から
何人来て、何%が買ったかを QR ごとに出す。

  python3 scripts/qr_report.py                 # 直近30日
  python3 scripts/qr_report.py --since -90d
  python3 scripts/qr_report.py --daily         # 日別も出す

出るもの:
  1. 紙QR全体（セッション・CVR・直帰率・滞在時間）
  2. QR別（utm_content）… 表紙クーポン / 裏面ストア / 裏面料理教室 …
  3. 刷り物別（utm_campaign）… leaflet-b6 / coupon-card
  4. 着地ページ別（刷ったURLどおりに着地しているかの確認）
  5. 参考：ストア全体との比較

UTM規約（docs/lp-system.md §5 と同じ。刷り物側は leaflet_b6_v17.html / coupon_card_v7.html）:
  utm_source  = leaflet        紙の同梱物からの流入はすべてこれに寄せる
  utm_medium  = qr             広告(cpc)・SNS(social)と並べて比較するための軸
  utm_campaign= leaflet-b6     リーフレット / coupon-card = 独立クーポンカード
  utm_content = cover-coupon   表紙のクーポンQR ← 「20%OFFクーポンが何回読まれたか」はこれ
                back-store     裏面のオンラインストアQR
                back-class     裏面の料理教室QR
                card-back      独立クーポンカード裏のQR

⚠️ 限界（分かった上で使うこと）:
  - **ここで数えているのは「読み取り回数」ではなく「着地セッション数」**。読み取ったが
    ページを開かなかった／同じ人が同じセッション内で2回読んだ、は1にならない・数えられない。
    純粋なスキャン回数が要るなら間に自前のリダイレクタを挟むしかないが、
    知りたいのは「何人来て何人買ったか」なのでセッションで足りる。
  - QRを Shopify の割引リンク（/discount/<CODE>?redirect=/...）にした場合も、
    UTMは転送先に引き継がれるのでこのレポートはそのまま使える（2026-09-03 実測で確認）。
  - 「クーポンが実際に使われた数」はここには出ない。それは管理画面のディスカウント
    （マーケティング > ディスカウント > 該当コード）の使用回数を見る。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shopifyql  # noqa: E402


def q(query):
    d = shopifyql.gql(shopifyql.Q, {"q": query})["shopifyqlQuery"]
    if not d:
        return [], []
    if d.get("parseErrors"):
        print(f"  PARSE ERROR: {d['parseErrors']}")
        return [], []
    td = d.get("tableData") or {}
    cols = [c["name"] for c in td.get("columns", [])]
    return cols, td.get("rows", [])


def show(title, query, fmt=None):
    cols, rows = q(query)
    print(f"\n## {title}")
    if not rows:
        print("  （データなし）")
        return
    print("  " + " | ".join(cols))
    for r in rows:
        vals = []
        for c in cols:
            v = r.get(c) if isinstance(r, dict) else None
            vals.append(fmt[c](v) if fmt and c in fmt else str(v))
        print("  " + " | ".join(vals))


def pct(v):
    try:
        return f"{float(v) * 100:.2f}%"
    except (TypeError, ValueError):
        return str(v)


def sec(v):
    try:
        return f"{float(v):.0f}秒"
    except (TypeError, ValueError):
        return str(v)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--since", default="-30d", help="開始（既定: -30d）")
    p.add_argument("--until", default="today", help="終了（既定: today）")
    p.add_argument("--medium", default="qr", help="対象の utm_medium（既定: qr）")
    p.add_argument("--daily", action="store_true", help="日別も出す")

    # ShopifyQLの相対指定は "-30d" のようにハイフンで始まるため、argparse が
    # オプション名と誤認する。`--since -30d` と素直に書けるよう先に = 形へ寄せる。
    argv = []
    skip = False
    for i, tok in enumerate(sys.argv[1:]):
        if skip:
            skip = False
            continue
        if tok in ("--since", "--until", "--medium") and i + 1 < len(sys.argv) - 1:
            argv.append(f"{tok}={sys.argv[i + 2]}")
            skip = True
        else:
            argv.append(tok)
    a = p.parse_args(argv)

    shopifyql.load_env()
    window = f"SINCE {a.since} UNTIL {a.until}"
    where = f"WHERE utm_medium = '{a.medium}'"
    fmt = {"conversion_rate": pct, "bounce_rate": pct, "average_session_duration": sec}

    print(f"# 同梱物QRレポート（utm_medium={a.medium} / {a.since} 〜 {a.until}）")

    show(
        "紙QR全体",
        f"FROM sessions SHOW sessions, conversion_rate, bounce_rate, "
        f"average_session_duration {window} {where}",
        fmt,
    )
    show(
        "QR別（utm_content）",
        f"FROM sessions SHOW sessions, conversion_rate GROUP BY utm_content "
        f"{window} {where} ORDER BY sessions DESC LIMIT 20",
        fmt,
    )
    show(
        "刷り物別（utm_campaign）",
        f"FROM sessions SHOW sessions, conversion_rate GROUP BY utm_campaign "
        f"{window} {where} ORDER BY sessions DESC LIMIT 20",
        fmt,
    )
    show(
        "着地ページ別（刷ったURLどおりか確認）",
        f"FROM sessions SHOW sessions GROUP BY landing_page_path "
        f"{window} {where} ORDER BY sessions DESC LIMIT 20",
    )
    show(
        "参考：ストア全体（同じ期間）",
        f"FROM sessions SHOW sessions, conversion_rate, bounce_rate, "
        f"average_session_duration {window}",
        fmt,
    )

    if a.daily:
        show(
            "日別",
            f"FROM sessions SHOW sessions, conversion_rate {window} {where} TIMESERIES day",
            fmt,
        )


if __name__ == "__main__":
    main()
