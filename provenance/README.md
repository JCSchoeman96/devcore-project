# Legacy provenance

`legacy-v1.0.0/` holds two historical artifacts that could be recovered from the workstation. Neither has a proven source commit, author, or canonical status. They are retained as evidence and must not be used as the canonical source without the baseline decision in [provenance documentation](../docs/provenance.md).

The ZIP is stored unchanged. The installed script copy preserves its exact bytes; Git does not preserve its original mode metadata. `legacy-v1.0.0/SHA256SUMS` records the ZIP and installed-script hashes. CI also verifies the archive's own checksum manifest and the bundled script hash.
