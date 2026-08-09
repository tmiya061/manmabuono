#!/usr/bin/env python3
"""LPの成績レポート（ShopifyQL・読み取り専用）

広告を回す前提の土台。GA4の権限がまだ無くても、
「LPに何人来て・何%が買ったか」だけは Shopify 側で読める。

  python3 scripts/lp_report.py /pages/set-teiki                # 直近30日
  python3 scripts/lp_report.py /pages/set-teiki --since -90d
  python3 scripts/lp_report.py /pages/set-teiki --daily        # 日別も出す

出るもの:
  1. LP全体（セッション・CVR・直帰率・滞在時間）
  2. utm_source 別（google / facebook / ig …）
  3. utm_campaign 別
  4. 参考：ストア全体との比較（LPが平均より良いか悪いか）

⚠️ 限界（分かった上で使うこと）:
  - ここで言う「セッション」は **そのURLに着地した** セッション。サイト内から回遊して
    LPを見た人は入らない。広告の受け皿としては着地＝ほぼ全部なので実用上は問題ない。
  - conversion_rate は「着地セッションのうち注文に至った割合」。LPで買わず後日サブスク更新で
    買った人などは拾えない。
  - **LP内のどのボタンが押されたか（クリック率）はここでは取れない。** それは GA4 側。
    LPのCTAには data-lp-cta を仕込んであるので、GTMでイベントを作れば読めるようになる。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shopifyql  # noqa: E402


def q(query):
    """1クエリ投げて (columns, rows) を返す。rows は列名をキーにした dict のリスト。"""
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
            if fmt and c in fmt:
                vals.append(fmt[c](v))
            else:
                vals.append(str(v))
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
    p.add_argument("path", help="LPのパス（例: /pages/set-teiki）")
    p.add_argument("--since", default="-30d", help="開始（既定: -30d）")
    p.add_argument("--until", default="today", help="終了（既定: today）")
    p.add_argument("--daily", action="store_true", help="日別も出す")

    # ShopifyQLの相対指定は "-30d" のようにハイフンで始まるため、argparse が
    # オプション名と誤認する。`--since -30d` と素直に書けるよう先に = 形へ寄せる。
    argv = []
    skip = False
    for i, tok in enumerate(sys.argv[1:]):
        if skip:
            skip = False
            continue
        if tok in ("--since", "--until") and i + 1 < len(sys.argv) - 1:
            argv.append(f"{tok}={sys.argv[i + 2]}")
            skip = True
        else:
            argv.append(tok)
    a = p.parse_args(argv)

    shopifyql.load_env()
    window = f"SINCE {a.since} UNTIL {a.until}"
    where = f"WHERE landing_page_path = '{a.path}'"

    print(f"# LPレポート: {a.path}（{a.since} 〜 {a.until}）")

    fmt = {"conversion_rate": pct, "bounce_rate": pct, "average_session_duration": sec}

    show(
        "LP全体",
        f"FROM sessions SHOW sessions, conversion_rate, bounce_rate, "
        f"average_session_duration {window} {where}",
        fmt,
    )
    show(
        "utm_source 別",
        f"FROM sessions SHOW sessions, conversion_rate GROUP BY utm_source "
        f"{window} {where} ORDER BY sessions DESC LIMIT 20",
        fmt,
    )
    show(
        "utm_campaign 別",
        f"FROM sessions SHOW sessions, conversion_rate GROUP BY utm_campaign "
        f"{window} {where} ORDER BY sessions DESC LIMIT 20",
        fmt,
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
