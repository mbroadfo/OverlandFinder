# OverlandFinder Architecture

```mermaid
flowchart TD
    subgraph GHA["GitHub Actions"]
        direction TB
        D["🚀 deploy.yml\non push to main"]
        S["⏰ scraper.yml\n6 AM & 6 PM UTC"]
        SMS["📱 sms-digest.yml\n8 AM MDT daily"]
    end

    subgraph AZ["Azure"]
        direction TB
        KV["🔐 Key Vault\nkv-overland-finder-dev\n─────────────────\nmongodb-uri\nsmtp-username / password\nanthropics-api-key\nebay-app-id / cert-id"]
        TF["📦 Terraform State\nstoverlandtfstate\nrg-tf-state"]
    end

    subgraph SRC["Data Sources"]
        direction TB
        CL["🗺️ Craigslist\nDenver · Boulder · COS\nprivate sellers"]
        EB["🛒 eBay Motors\nnationwide\nstructured API"]
    end

    subgraph DB["MongoDB Atlas\noverland_finder"]
        direction TB
        RL[("raw_listings\npending → evaluated")]
        DL[("deals\nscored + notified")]
        PO[("price_observations\nmarket history")]
    end

    subgraph EVAL["AI Evaluation"]
        CL_EVAL["🔍 DealEvaluator\nenrich detail page\nfilter mileage"]
        CLAUDE["🤖 Claude Haiku\nformula-based scoring\n0–100 + action"]
    end

    PHONE["📲 Verizon SMS\nemail-to-SMS gateway"]

    %% Deploy flow
    D -->|"terraform apply\nresource group + KV"| AZ
    D -->|"az keyvault secret set\n6 secrets"| KV
    TF -.->|"state backend"| D

    %% Scraper flow
    S -->|scrape listings| CL
    S -->|Browse API| EB
    CL -->|"upsert raw_listings\nsource=craigslist"| RL
    EB -->|"upsert raw_listings\nsource=ebay, VIN"| RL

    %% Evaluation flow
    RL -->|"pending listings\nbatch of 50"| CL_EVAL
    CL_EVAL -->|"skip: high mileage\nskip: off-target title"| RL
    CL_EVAL -->|evaluate| CLAUDE
    CLAUDE -->|"value_score\nrecommended_action\nmarket_value_est"| DL
    CLAUDE -->|price data point| PO

    %% Notification flow
    DL -->|"top N unnotified\nscore ≥ 40"| SMS
    SMS -->|"[CL]/[eBay] deal\nprice · score · URL"| PHONE

    %% Secrets flow
    KV -.->|"secrets at runtime"| S
    KV -.->|"secrets at runtime"| SMS

    %% Styling
    classDef azure fill:#0078d4,color:#fff,stroke:#005a9e
    classDef github fill:#24292e,color:#fff,stroke:#444
    classDef mongo fill:#13aa52,color:#fff,stroke:#0d7a3a
    classDef ai fill:#d97706,color:#fff,stroke:#b45309
    classDef source fill:#7c3aed,color:#fff,stroke:#5b21b6

    class KV,TF azure
    class D,S,SMS github
    class RL,DL,PO mongo
    class CL_EVAL,CLAUDE ai
    class CL,EB source
```

## Component Summary

| Component | Role |
|-----------|------|
| **deploy.yml** | Terraform provisions RG + Key Vault; pipeline pushes all secret values |
| **scraper.yml** | Runs Craigslist + eBay scrapers twice daily, then evaluator until queue empty |
| **sms-digest.yml** | Sends top 3 unnotified deals via Verizon email-to-SMS at 8 AM MDT |
| **Key Vault** | Single source of truth for all secrets; never in Terraform state |
| **Craigslist scraper** | HTML scrape across Denver/Boulder/COS; pre-filters off-target titles |
| **eBay scraper** | Browse API; nationwide reach; VIN + mileage in structured response |
| **DealEvaluator** | Enriches detail pages, filters high-mileage, calls Claude per listing |
| **Claude Haiku** | Formula-based 0–100 scoring anchored to estimated market value |
| **MongoDB Atlas** | raw_listings → deals pipeline; price_observations for market history |
