# sample-repo

A tiny multi-language repo (Python + Java + JavaScript + Playwright TS) used
to demonstrate the scope intelligence toolkit end-to-end.

## Layout (3 source features, 1 e2e suite)

```
src/auth/         Python  — login + session
src/users/        Python  — user repository
src/checkout/     Python  — cart + checkout service (depends on auth + users)
src/billing/      Java    — payment controller + service
src/frontend/     JS      — login form + api client
tests/auth/       pytest
tests/checkout/   pytest
tests/billing/    JUnit
tests/e2e/        Playwright
```

## Walkthrough

Run from the toolkit root:

```bash
scope init  --repo examples/sample-repo --write-claude-md
scope index examples/sample-repo
```

Expected:

```
indexed: files=17  symbols=30  tests=4  features=6
```

### Repo overview

```bash
scope summary --repo examples/sample-repo
```

```
files=17  symbols=30  tests=4  features=6
languages: python=11, java=3, playwright=1, javascript=2
test frameworks: pytest=2, junit=1, playwright=1

top features:
  - auth       files=4  symbols=8  tests=2  langs=python
  - checkout   files=4  symbols=7  tests=1  langs=python
  - billing    files=3  symbols=9  tests=1  langs=java
  - frontend   files=2  symbols=4  tests=0  langs=javascript
  - users      files=2  symbols=2  tests=0  langs=python
  - e2e        files=1  symbols=0  tests=1  langs=playwright

most-imported files:
  - src/auth/session.py            imported_by=2
  - src/billing/PaymentService.java imported_by=2
  - src/checkout/cart.py            imported_by=2
  - src/users/repository.py         imported_by=2
```

### Feature scope

```bash
scope feature auth --repo examples/sample-repo
```

```
# feature: auth
languages: python
files: 4    symbols: 8
aliases: auth
depends on: users
entry points:
  - src/auth/login.py::handle_login

files:
  - src/auth/__init__.py
  - src/auth/login.py
  - src/auth/session.py
  - tests/auth/test_login.py

related tests:
  - tests/auth/test_login.py    (pytest, 2 cases)
  - tests/e2e/login.spec.ts     (playwright, 2 cases)
```

Note the cross-language linkage: the Playwright spec was attached to the
Python `auth` feature via the `login.*` naming heuristic.

### Impact analysis

```bash
scope impacted --file src/users/repository.py --repo examples/sample-repo
```

```
targets: src/users/repository.py
direct  (2):
  - src/auth/login.py
  - src/checkout/cart.py
transitive (3):
  - src/checkout/service.py
  - tests/auth/test_login.py
  - tests/checkout/test_service.py
features touched: auth, checkout
```

Same query on a Java symbol:

```bash
scope impacted --symbol charge --repo examples/sample-repo
```

```
targets: src/billing/PaymentService.java
direct  (2):
  - src/billing/PaymentController.java
  - tests/billing/PaymentControllerTest.java
features touched: billing
```

### Symbol context

```bash
scope symbol handle_login --repo examples/sample-repo
```

```
# src/auth/login.py::handle_login  (function, line 10)
  feature: auth    language: python
  params: email, password
  calls:
    - find_user_by_email
    - create_session
    - LoginError
    - _check_password
  called by:
    - tests/auth/test_login.py::test_login_succeeds_for_known_user
    - tests/auth/test_login.py::test_login_rejects_unknown_email
```

### Related tests

```bash
scope tests --feature checkout --repo examples/sample-repo
```

```
- tests/checkout/test_service.py  (pytest)
    cases: test_checkout_requires_auth, test_checkout_rejects_empty_cart
    covers: src/checkout/cart.py, src/checkout/service.py
```

### Incremental update

After editing one file, refresh just its slice instead of re-indexing the
repo:

```bash
scope update --files src/auth/login.py --repo examples/sample-repo
```

```
updated 1 file(s). totals: files=17  symbols=30  tests=4
```

## Index size

After `scope index`, the entire `.scope-intelligence/` folder is around
**~36 KB** of JSON for this 17-file multi-language repo — proportional to
real metadata, not raw source.
