# Sanitization and export verification

This bundle is an abridged public record of measurements on one rig. Only documentation, result tables, short report excerpts and sanitized benchmark sources were exported. Raw evidence directories, archives, logs, request/response text, model fixtures and image files were excluded. The original local evidence remains outside this checkout.

## Scrub rules

- Remove network addresses, real machine names, account names, email addresses, forge identities, remote-login commands and connection details. Generic placeholders identify omitted local endpoints and paths.
- Remove absolute personal-directory paths and private deployment locations. Model-pack locations become `<model path>`; support-data locations and runtime configuration must be supplied by the reader.
- Remove credential values, device serials, hardware network identifiers and unrelated organizational or personal content. Keep only hardware models/capacities, measured topology, toolchain versions, public engine commit hashes, executable digests and performance numbers.
- Remove internal supervision, work-queue, resource-accounting and notification material, including identifying names. Advice reports use neutral review labels. Omit unrelated project material and private provenance beyond the public model name Qwen3.8-Flash-Next Heretic IQ4_XS.
- Preserve failed, censored and not-run cases. Distinguish source inspection, analytical bounds, historical measurements and new local export checks. Correct early hardware descriptions and link later findings that supersede early recommendations.
- Render the four-component engine version as `0.1.59 (patch 1)` so it cannot be mistaken for a network address. Engine commit and executable digests are retained exactly.
- Parse archived Python sources into syntax trees, omit comments/docstrings and embedded input content, redact string literals and disable fixture builders. Insert an unconditional exception before original code so importing or executing it cannot perform service operations. Do not copy evidence archives or create substitute historical fixtures.
- The new request adapter saves an explicit numeric timing allowlist and input/output digests. It does not save message content, response text, endpoint addresses or authorization values. Its newly written continuation generator is synthetic; no original prompt was copied.

## Verification commands

The final case-insensitive content scan used GNU grep over this directory. Character classes below spell the same literal search patterns while keeping this verification description from matching its own restricted terms. Paths are relative to the repository root.

```sh
grep -RniE '([0-9]{1,3}\.){3}[0-9]{1,3}' docs/rig-research
grep -RniE 'tu[k]ang|test[s]erver|[@]|ca[p]tain|first[m]ate|s[o]l |pe[l]vis|radio[l]og|s[b]a|pa[t]ient|p[h]i|ro[s]ter|the[s]is|bil[l]ing|pass[w]ord|to[k]en|se[c]ret|/ho[m]e/|fe[l]ix' docs/rig-research
```

The final scan returned 0 dotted-address matches and 153 matching lines in the combined literal scan. In the second scan, the retained matches are measurement vocabulary or code identifiers for model positions/counts, a source-table `at` notation, credential-name exclusion regexes, and the scan expression's own at-sign. They contain no identities, addresses or credential values. Every hit was reviewed; confidential hits were removed and every remaining hit is a false positive for confidential content.

Additional local scans checked private pack names, remote-copy commands, real personal paths, external URLs, reviewer names, operational identities and unrelated subject matter. These returned no confidential matches. The archive source digests are provenance checksums, not access credentials. No binary or raw evidence file is included.

## Local checks performed for this export

Passed:

- Every supplied Python source parsed and compiled in memory; archival modules were not executed.
- The portable request adapter passed a local synthetic streaming-service test: two sequential primes, three paired rounds, eight requests, numeric timing output and prefix-threshold validation.
- Failure cases for a prefix miss, short output and non-finite engine timing returned failure and saved bounded partial results. The successful case and all failure outputs excluded the supplied input/output sentinels, dummy authorization value, endpoint and arbitrary server metadata.
- Relative Markdown links resolved inside this bundle. Retained table rows were compared to the locally scrubbed source reports, including the production-application report added during export.
- The two final recipe settings were checked against X4/X5 source: 64 GiB, twelve entries, two/262144 versus four/131072, and the four-slot 828 MiB later-card reserve. The later deployed sixteen-entry setting is explicitly labelled as startup/short-prefix verified rather than long-context load-tested.
- The final change scope contained only this directory; whitespace checks passed.

Failed during preparation and corrected: the first link check found this page missing before it was written. The exporter initially lacked an entry for the production-application report that arrived during work; the report and its limits were then included. A table checker initially expected an empty header-only table after its private path rows had been omitted; the checker was corrected to compare populated tables. These preparation issues were not engine failures.

Not run for this export: GPU inference, model downloads, service lifecycle commands, backend builds, reboot tests, production rollback, remote publication or a validation pipeline. The hardware measurements are attributed to the historical reports, not to these local documentation checks.
