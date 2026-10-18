# Deferred work requested by the user

**19 October implementation update:** the user authorized a deadline-focused expansion and basic inventory is now implemented. Sales import, approved NL→SQL translation, SQL analysis and optional Gemini integration are also implemented. Live provider verification awaits the user's key. See FINAL_REVIEW_DEMO.md and IMPLEMENTATION_STATUS.md. Earlier deferral/proposal notes below are historical and superseded for this accepted scope. No caching/optimizer advisor is to be added. Remaining work includes final PPT/report authoring, viva rehearsal, friend's-laptop rehearsal, and optional live AI verification. Advanced inventory (suppliers/purchasing, returns, reservations and warehouses) is not implemented.

## Inventory management

- Requested on 17 October 2026 during the evaluator discussion.
- Start only after the current review walkthrough is finished and the user is ready to proceed.
- Add inventory management to the existing retailer/reporting scenario.
- Scope, schema, stock movements, validation and UI are to be designed at that stage; no specific implementation is agreed yet.
- This is future work. Do not describe inventory management as implemented in the current review, PPT, report or viva.

Current status: all eleven planned DBMS walkthrough sections received a first explanation on 18 October 2026; cross-questions and rehearsal can continue. This is not approval to start inventory automatically. Wait until the user is ready to proceed. The final PPT/report and friend's-laptop rehearsal remain separate work.

## Expansion research — 18 October 2026

The user requested research into AI, caching and useful DBMS scope expansion. Recommendations are recorded in [DBMS_EXPANSION_RESEARCH.md](DBMS_EXPANSION_RESEARCH.md) and [AI_DBMS_FEATURE_RESEARCH.md](AI_DBMS_FEATURE_RESEARCH.md). These compare inventory/posting, change-aware result caching, historical report comparison, SQL-based alerts, an optional AI report assistant and extension alternatives. They are proposals, not implemented or accepted scope. No migrations, dependencies or application behavior were changed by this research.

## Latest scope direction — 19 October 2026

- The user declined caching. Do not include a new cache subsystem in the implementation plan unless they later change that preference. Existing materialized views and historical datasets remain implemented features.
- Prefer researching a free hosted AI API over provisioning a local LLM. Provider/model/account eligibility and quotas require verification; no provider account/key or live API call has been configured.
- Current new recommendations: AI-assisted CSV mapping plus deterministic staging/validation/import, SQL-backed exception alerts with optional AI explanation, and a later inventory-dependent what-if tool. These are proposed choices, not authorization to implement all of them.
- See [NOVELTY_OPTIONS_NO_CACHE.md](NOVELTY_OPTIONS_NO_CACHE.md) and [FREE_AI_API_OPTIONS.md](FREE_AI_API_OPTIONS.md). Inventory remains deferred until the user is ready to proceed.
