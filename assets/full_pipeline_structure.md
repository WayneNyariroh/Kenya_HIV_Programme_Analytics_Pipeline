Kenya Public Health Data Pipeline v2
Notebook Architecture

┌───────────────────────────────────────────────────────────────── ┐
│                     PUBLIC DATA SOURCES                          │
├────────────────┬────────────────┬────────────────┬───────────────┤
│ WHO GHO        │ World Bank     │ UNAIDS 2026    │ Global Fund   │
│ OData API      │ REST API       │ ZIP / CSV      │ OData v4.2    │
└────────────────┴────────────────┴────────────────┴───────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         EXTRACT LAYER                           │
│                                                                 │
│ • API requests and downloads                                    │
│ • WHO metadata validation                                       │
│ • World Bank pagination                                         │
│ • Chunked UNAIDS CSV reading                                    │
│ • Global Fund implementation-period expansion                   │
│ • Concurrent transaction retrieval                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  PYTHON / PANDAS DATAFRAMES                     │
│                                                                 │
│ df_who_raw   df_wb_raw   df_unaids_raw   df_gf_grants           │
│                                            df_gf_disb           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                         ┌────────────┐
                         │ LOAD LAYER │
                         └────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DUCKDB STAGING TABLES                        │
│                                                                 │
│ stg_who_hiv                                                     │
│ stg_worldbank                                                   │
│ stg_unaids_hiv                                                  │
│ stg_gf_grants                                                   │
│ stg_gf_disbursements                                            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                      ┌─────────────────┐
                      │ TRANSFORM LAYER │
                      └─────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         CLEAN TABLES                            │
│                                                                 │
│ clean_who_hiv                                                   │
│ clean_worldbank                                                 │
│ clean_unaids_hiv                                                │
│ clean_gf_grants                                                 │
│ clean_gf_disbursements                                          │
└─────────────────────────────────────────────────────────────────┘
                      │                     │
                      ▼                     ▼

        ┌───────────────────────┐   ┌────────────────────────┐
        │ FEATURE ENGINEERING   │   │ STAR SCHEMA            │
        │                       │   │                        │
        │ feat_hiv_cascade      │   │ dim_country            │
        │ feat_health_system    │   │ dim_time               │
        │ feat_gf_annual        │   │ dim_indicator          │
        │                       │   │ fact_health_indicators │
        │                       │   │ fact_gf_funding        │
        └───────────────────────┘   └────────────────────────┘
                      │                     │
                      └──────────┬──────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                       SQL QUERY LAYER                           │
│                                                                 │
│ df_cascade                                                      │
│ df_regional                                                     │
│ df_incidence                                                    │
│ df_gf_viz                                                       │
│ df_scatter                                                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ALTAIR VISUALIZATIONS                        │
│                                                                 │
│ • Kenya HIV burden                                              │
│ • East Africa ART coverage                                      │
│ • Kenya HIV incidence by programme era                          │
│ • Health expenditure vs ART coverage                            │
│ • Global Fund disbursements                                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      OUTPUTS / INSIGHTS                         │
│                                                                 │
│ • Kenya HIV programme snapshot                                  │
│ • Regional comparison                                           │
│ • Financing analysis                                            │
│ • Source comparison                                             │
│ • Reproducible notebook workflow                                │
└─────────────────────────────────────────────────────────────────┘