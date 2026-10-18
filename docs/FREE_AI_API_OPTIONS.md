# Free AI API options for Conduit

Checked: 19 October 2026. Research only: no accounts, credentials, live inference calls, application changes, migrations, commits or pushes were created.

User steering: caching is declined as a proposed expansion. The user prefers exploring a free cloud AI API and wants novelty beyond historical report replay. This note supersedes any assumption that local-model deployment is necessary for the AI option.

## Recommendation

Use **Gemini Developer API as the first trial**, with a configurable model ID, and keep **Groq as an alternative**. Test the account's actual free access before choosing. Both can remove the need to run a large model on an 8 GB laptop, but require internet and provider credentials. Neither free plan establishes guaranteed availability or quality.

For this project, make one short intent or explanation call per user action, not one call for every member of a 10,000-report batch. Existing report generation must still work when the provider is unavailable or its quota is exhausted. This is an architecture recommendation, not a measured capacity claim.

## Gemini Developer API

- **Verified model intersection:** Google's official model page identifies `gemini-3.5-flash-lite` as stable and explicitly supports structured outputs. The pricing page lists its standard input/output as free of charge in the Free Tier. This is a documentation-verified candidate, not a promise that every account currently has usable quota. [Model capabilities](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite).
- **India:** India appears on Google's supported-region list. Individual account eligibility and project status still require checking. [Available regions](https://ai.google.dev/gemini-api/docs/available-regions).
- **Key:** A Gemini API key is required; Google documents creating and managing it through AI Studio. Configure it on the server, outside Git and frontend code. [API keys](https://ai.google.dev/gemini-api/docs/api-key).
- **Quota:** Limits depend on project, model and usage tier, rather than the number of API keys. View the active limits in AI Studio. Google explicitly says advertised limits do not guarantee actual capacity. This note deliberately does not hardcode an unverified requests/day allowance. [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).
- **Data use:** The pricing page marks free-tier content as used to improve Google's products. Use fictional demo data and compact aggregate facts; do not upload real customer personal data for the demonstration. This is a practical recommendation based on that published distinction. [Pricing and data-use distinction](https://ai.google.dev/gemini-api/docs/pricing).

Structured output can represent a report code, dates, top-N and clarification state. It still needs application validation and PostgreSQL constraints: correctly shaped JSON is not proof of correct meaning. [Structured-output documentation](https://ai.google.dev/gemini-api/docs/structured-output).

## Groq Free Plan

- **Verified model intersection:** `qwen/qwen3.8-27b` appears in the current Free Plan rate-limit table and in the supported strict JSON-schema model list. Thus a free-plan candidate with documented structured-output support exists. Model access still needs confirmation for the actual organization. [Free Plan limits](https://console.groq.com/docs/rate-limits), [structured outputs](https://console.groq.com/docs/structured-outputs).
- **Structured-output distinctions:** `json_schema` support is model-specific; plain JSON Object mode is weaker. Groq's strict mode has schema requirements such as required properties and `additionalProperties: false`. Do not assume a quickstart's chosen example model has the same schema capabilities. [Structured outputs](https://console.groq.com/docs/structured-outputs).
- **Key and limits:** Create a Groq key and configure it as a server environment variable. Limits apply to the organization and include requests/tokens across time windows; Groq says the account Limits page is authoritative and returns rate-limit errors when a threshold is exceeded. [Quickstart](https://console.groq.com/docs/quickstart), [rate limits](https://console.groq.com/docs/rate-limits).
- **Region:** This research did not establish a definitive current official country-availability entry for India. Do not promise India account eligibility without checking Groq's actual signup/account access.

## What to demonstrate as the new feature

Candidate A: **Natural-language report requests with an inspectable plan.** “Show the top five products by revenue for January 2026” becomes validated fields for an existing approved query. Display and confirm the interpretation, then execute the ordinary reporting path. Record prompt, model, validated parameters and resulting run. No arbitrary generated SQL is executed.

Candidate B: **SQL exception investigations with AI-assisted explanation.** SQL detects, for example, a completed month's revenue decline beyond a configured threshold and calculates category contributions. The AI turns those retained figures into a short explanation; source figures and rule version remain visible. The detection is SQL/statistical rules, not a trained ML model. AI must not fabricate causes.

Candidate B expands the operational value more than a chat interface alone. Pairing an agreed inventory/purchase workflow with SQL exceptions such as stock-out risk or supplier delays could create a broader project, but those fields and workflows are not implemented or approved merely by this note.

The provider key is an implementation credential for the backend, not a return to the old broker API-key login. Users can retain the simple application login. On another laptop, the maintainer configures the secret privately; pushing source code does not transfer secrets.

Before implementation: check actual account/model availability and quota; choose the business workflow; define a small evaluation set of correct intents, ambiguous requests and grounded explanations; test network/quota failure without blocking the ordinary demo. No particular provider quota, answer quality, latency or novelty mark is guaranteed by this research.
