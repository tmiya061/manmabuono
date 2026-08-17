#!/usr/bin/env python3
"""article_author の定義を capabilities 込みで取得して退避する（読み取りのみ）"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from shopifyql import load_env, gql

load_env()

Q = """
query {
  metaobjectDefinitionByType(type: "article_author") {
    id
    type
    name
    displayNameKey
    access { storefront admin }
    capabilities {
      publishable { enabled }
      translatable { enabled }
      renderable { enabled data { metaTitleKey metaDescriptionKey } }
      onlineStore { enabled data { urlHandle createRedirects } }
    }
    fieldDefinitions {
      key name description required
      type { name }
      validations { name value }
    }
  }
}
"""

data = gql(Q)
print(json.dumps(data, ensure_ascii=False, indent=2))
