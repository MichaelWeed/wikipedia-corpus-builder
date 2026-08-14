# CorpusSieve — Test Strategy Specification (TEST_STRATEGY)

## Verification Philosophy

CorpusSieve mandates executable, empirical proof of correctness across all components.

## Coverage Requirements

- **Strict Modules (85% Coverage Floor)**:
  - `corpussieve.domain`
  - `corpussieve.safety`
  - `corpussieve.contracts`
- **Overall Engine Floor**: 70% unit and integration test coverage across `corpussieve`.

## Synthetic Golden Fixtures

All extraction, parsing, and compilation tests run against synthetic, seeded MediaWiki dumps (`fixwiki`):
- `fixwiki-20260801-pages-articles-multistream.xml.bz2`
- `fixwiki-20260801-page.sql.gz`
- `fixwiki-20260801-categorylinks.sql.gz`

## Automated CI Gates

1. Linting & Formatting: `ruff check` and `ruff format --check`
2. Static Type Analysis: `mypy --strict src`
3. Unit & Integration Testing: `pytest`
