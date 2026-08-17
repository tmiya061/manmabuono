#!/usr/bin/env python3
"""article_author に onlineStore / renderable capability を付与する。

- onlineStore: /pages/author/{handle} でエントリーごとにページが生える
- renderable : <title> に name、meta description に bio を供給する

退避: scripts/metaobject_defs/article_author.backup_20260817_pre_onlinestore.json
戻す: capabilities.onlineStore.enabled / renderable.enabled を false で再実行
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from shopifyql import load_env, gql

load_env()

M = """
mutation($id: ID!, $definition: MetaobjectDefinitionUpdateInput!) {
  metaobjectDefinitionUpdate(id: $id, definition: $definition) {
    metaobjectDefinition {
      type
      capabilities {
        renderable { enabled data { metaTitleKey metaDescriptionKey } }
        onlineStore { enabled data { urlHandle canCreateRedirects } }
      }
      fieldDefinitions { key }
    }
    userErrors { field message code }
  }
}
"""

VARS = {
    "id": "gid://shopify/MetaobjectDefinition/11262722109",
    "definition": {
        "capabilities": {
            "onlineStore": {
                "enabled": True,
                "data": {"urlHandle": "author", "createRedirects": True},
            },
            "renderable": {
                "enabled": True,
                "data": {"metaTitleKey": "name", "metaDescriptionKey": "bio"},
            },
        }
    },
}

d = gql(M, VARS)
print(json.dumps(d, ensure_ascii=False, indent=2))
