# Test Data Schema Version 1

This directory defines the first public test-data format. The generated JSON
Schemas describe individual documents; runtime consumers live in
`backend/test_support/test_data/formats/v1/` so schema assets remain
language-neutral.

The example has four layers:

1. `catalog.json` indexes independently loadable documents by stable ID.
2. `configs/` contains reusable tool and model configurations.
3. `novels/` contains independent novel datasets with chapter metadata,
   immutable content versions, and artifacts derived from exact versions.
4. `relations/` combines novel datasets into scenarios without copying their
   content.

All IDs are stable fixture-local identifiers. Database loaders should generate
database UUIDs and maintain an ID map while materializing a scenario.

## Folder Structure

```text
v1/
├── README.md
├── json/
│   └── <document-kind>.schema.json
└── examples/
    ├── catalog.json
    ├── configs/
    │   └── <config-id>.json
    ├── novels/
    │   └── <novel-id>/
    │       ├── manifest.json
    │       └── chapters/
    │           └── <chapter-directory>/
    │               ├── manifest.json
    │               └── versions/
    │                   └── <version-directory>/
    │                       ├── manifest.json
    │                       ├── text.txt
    │                       └── <artifact>.json
    └── relations/
        └── <relation-id>.json
```

Concrete, loadable instances live in `tests/test_data/datasets/`, outside this
schema package. `synthetic-smoke/` is the small default fixture corpus used by
backend tests.

- `catalog.json` is the only discovery root. It maps stable config, novel, and
  relation IDs to documents beneath this directory.
- `configs/` stores reusable tool inputs such as NER model parameters.
- Each directory under `novels/` contains one independently loadable novel
  dataset. Its `manifest.json` explicitly references its chapters.
- Each chapter directory contains chapter metadata and explicitly references
  immutable content-version manifests.
- Each content-version directory contains its text snapshot and any artifacts
  derived from that exact text. Its manifest explicitly lists both the text
  file and artifacts.
- `relations/` stores independently loadable bundles connecting cataloged
  novels through domain relationships such as source-work membership.

The names `catalog.json` and `manifest.json` are fixed conventions. Directory
names and artifact filenames are organizational only: loaders resolve the
explicit relative paths and stable IDs declared in manifests. The zero-padded
chapter and version directory names in this example are recommended for human
sorting but are not identifiers and carry no schema meaning.

## Invariants

- Manifests and artifacts have an explicit `schemaVersion`.
- Paths are relative to the manifest that declares them.
- Catalog IDs must match the IDs declared by their referenced documents.
- Chapter-content version numbers are positive, unique, and contiguous.
- The latest content is the version with the greatest number.
- Chapter manifests reference explicit content-version manifests; loaders do
  not discover version artifacts from filenames.
- Positional artifacts live with the exact content version they describe.
- Artifact loaders validate every label range and label text against `text.txt`.
- Relation bundles reference stable IDs rather than filesystem paths.
- Documents are loaded lazily; reading the catalog does not load every corpus.
- Provenance is required before a novel dataset is committed as public data.
- Logical IDs are globally unique within a catalog.
- Public JSON uses camel-case field names. Python models may expose snake-case
  names through validation aliases.

## Generated Schemas And Locks

Generate or verify the version 1 schemas from `backend/`:

```console
.venv/bin/python -m scripts.generate_test_data_schema --version 1
.venv/bin/python -m scripts.generate_test_data_schema --version 1 --check
```

Each concrete dataset commits a `catalog.lock.json` containing the size and
SHA-256 digest of every reachable document and content file. Derived artifacts
also record their text and config input hashes. Generate the complete lock, or
update/check selected catalog folders, with:

```console
.venv/bin/python -m scripts.lock_test_data tests/test_data/datasets/synthetic-smoke --all
.venv/bin/python -m scripts.lock_test_data tests/test_data/datasets/synthetic-smoke --all --check
.venv/bin/python -m scripts.lock_test_data tests/test_data/datasets/synthetic-smoke novels/xianxia-source
```

## Version 1 Decisions

- `catalog.json` is the only discovery root.
- Every independently parsed JSON document declares `kind` and
  `schemaVersion`.
- Content-version manifests explicitly reference `text.txt` and all derived
  artifacts.
- Artifact documents identify their producer and model configuration. File,
  input, and configuration hashes belong in the generated catalog lock.
- Novel manifests include database-relevant metadata, including visibility.
- Relation bundles include source-work metadata and membership.
- Language codes are resolved through Python fixtures that seed supported
  languages; version 1 has no language catalog.
- Contributors, permissions, and database UUIDs remain the responsibility of
  Python materializers and fixtures.
- Raw autolabel artifacts represent model output, not database transport or
  human-review state.

## Deferred Questions

- How translation provenance, glossary expectations, and filter expectations
  should be represented as additional artifact kinds.
- How chapter alignment should represent one-to-one, split, merged, and
  reordered translations after chapter relationships exist in the domain
  model. Schema version 1 intentionally does not model chapter alignment.
- Whether chapter-version transitions should be stored as text operations.
