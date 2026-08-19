#!/usr/bin/env python3
"""ローカルの画像を Shopify のファイルへアップして公開URLを返す

用途: 生成AI（fal）に参照画像を渡すには公開URLが要る。手元の素材を
一時的に置く先として Shopify のファイルを使う。

  python3 scripts/upload_file.py path/to/a.jpg path/to/b.jpg

⚠️ アップしたファイルは cdn.shopify.com で**誰でも見られる**。
   他社の著作物・人物写真は上げないこと。自社の素材のみ。
⚠️ 書き込み操作なので docs/admin-changelog.md に記録する。

削除: python3 scripts/upload_file.py --delete <gid>
"""
import json
import mimetypes
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shopifyql  # noqa: E402

Q_STAGED = """
mutation($input: [StagedUploadInput!]!) {
  stagedUploadsCreate(input: $input) {
    stagedTargets { url resourceUrl parameters { name value } }
    userErrors { field message }
  }
}
"""

Q_CREATE = """
mutation($files: [FileCreateInput!]!) {
  fileCreate(files: $files) {
    files { id fileStatus alt ... on MediaImage { image { url width height } } }
    userErrors { field message }
  }
}
"""

Q_READY = """
query($ids: [ID!]!) {
  nodes(ids: $ids) {
    ... on MediaImage { id fileStatus image { url width height } }
  }
}
"""

Q_DELETE = """
mutation($ids: [ID!]!) {
  fileDelete(fileIds: $ids) { deletedFileIds userErrors { field message } }
}
"""


def upload(paths):
    inputs = []
    for p in paths:
        inputs.append({
            "filename": os.path.basename(p),
            "mimeType": mimetypes.guess_type(p)[0] or "image/jpeg",
            "resource": "FILE",
            "httpMethod": "POST",
            "fileSize": str(os.path.getsize(p)),
        })
    d = shopifyql.gql(Q_STAGED, {"input": inputs})["stagedUploadsCreate"]
    if d["userErrors"]:
        print("ERROR:", d["userErrors"]); sys.exit(1)

    resources = []
    for p, target in zip(paths, d["stagedTargets"]):
        # multipart/form-data を手で組む（外部依存を足さないため）
        boundary = "----shopifyupload7f3a9"
        body = b""
        for param in target["parameters"]:
            body += (
                f'--{boundary}\r\nContent-Disposition: form-data; name="{param["name"]}"'
                f'\r\n\r\n{param["value"]}\r\n'
            ).encode()
        with open(p, "rb") as f:
            data = f.read()
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            f'filename="{os.path.basename(p)}"\r\nContent-Type: application/octet-stream\r\n\r\n'
        ).encode() + data + f"\r\n--{boundary}--\r\n".encode()

        req = urllib.request.Request(
            target["url"], data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        urllib.request.urlopen(req)
        resources.append(target["resourceUrl"])
        print(f"  staged: {os.path.basename(p)}")

    files = [{"originalSource": r, "contentType": "IMAGE"} for r in resources]
    c = shopifyql.gql(Q_CREATE, {"files": files})["fileCreate"]
    if c["userErrors"]:
        print("ERROR:", c["userErrors"]); sys.exit(1)

    ids = [f["id"] for f in c["files"]]
    # 処理完了までポーリング（直後は image が null）
    import time
    for _ in range(30):
        nodes = shopifyql.gql(Q_READY, {"ids": ids})["nodes"]
        if all(n and n.get("image") for n in nodes):
            for n in nodes:
                print(f'{n["id"]}\t{n["image"]["url"]}')
            return nodes
        time.sleep(2)
    print("タイムアウト（処理中）:", ids)
    return []


if __name__ == "__main__":
    shopifyql.load_env()
    if sys.argv[1] == "--delete":
        r = shopifyql.gql(Q_DELETE, {"ids": sys.argv[2:]})["fileDelete"]
        print(json.dumps(r, ensure_ascii=False))
    else:
        upload(sys.argv[1:])
