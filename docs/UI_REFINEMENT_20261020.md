# UI refinement: automatic interpretation and Indian number display

Implemented20October2026. Presentation files were not edited in this task.

## Automatic behavior

- Sales import no longer shows an AI checkbox/configuration helper. Known aliases map locally. Only unresolved header mapping attempts Gemini when configured; valid known mappings remain authoritative. Suggestions cannot introduce unknown columns or reuse a header. Provider/validation failure leaves manual mapping available. Confirmation is still required before committing records.
- Ask your data no longer shows the checkbox, provider badge or Supported questions panel. Local interpretation runs first. Unresolved phrasing falls back to Gemini; writes and explicitly unsupported measures still fail validation. Only approved parameterized SQL can execute. An unavailable provider produces a normal clarification request for unresolved questions.
- Analysis no longer has AI controls or a prominent provider badge. SQL always calculates facts first. A configured key enables an automatic summary attempt; failure retains the deterministic summary. A small “With AI insights” note appears at the bottom only after an AI summary succeeds, not merely because a key exists.
- Internal source/model provenance is retained in database records. The previous optional use_ai argument remains for explicit programmatic/test overrides, but web forms no longer control it.

## Key configuration

Fresh settings read a configured key. The old API process started before `.env.local` was modified, explaining its disabled controls. The owned API and two report workers were restarted; PostgreSQL remained running. A minimal live Gemini request succeeded. No key was printed, added to Git or exposed to the browser.

## Numeric display

- Shared formatting uses Indian grouping, e.g.2,16,01,654.00.
- Amounts/quantities at least1lakh display a rounded Lakh label, and at least1crore display Cr., with exact grouped values visible underneath. Example:2.16Cr. with(2,16,01,654.00).
- Analysis, assistant results, SQL results, Data explorer, import previews, inventory and report data previews use the shared formatter. Existing count displays use Indian grouping. Identity fields remain unchanged.
- Newly generated HTML report files use the same formatter. CSV values remain unrounded, ungrouped numeric export data suitable for spreadsheets. Old saved HTML files and their checksums were not rewritten; generate a new report for newly formatted file output.
- SQL calculations, stored facts and template versions are unaffected by display formatting.

## Verification

-37tests passed across tests/test_operations.py, tests/test_reporting.py, tests/test_formatting.py and tests/test_operations_templates.py. An existing Pydantic schema_json naming warning remains.
- Live authenticated HTTP checks confirmed all affected pages load, removed controls are absent, unfamiliar question/header interpretation uses Gemini, and analysis succeeds with the subtle AI credit.
- A fresh top3product report completed via the running workers; HTML contains formatted values and CSV retains numeric values. New run:78f7d49f-5399-4714-b053-73f2da66c00b.
- The live CSV test created only an uncommitted preview; it did not insert a business sale. The new report/query/analysis evidence is retained normally.
- Private live verification is stored under `.local/ui_refinement_20261020/`. No fresh browser screenshot verification was available because local browser automation is disabled; UI structure was checked through rendered templates and HTTP responses.
