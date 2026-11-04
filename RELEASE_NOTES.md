# WorkCert 0.3.0

WorkCert provides force-displacement tables, work queries and reconstruction-error
metadata relative to supplied numerical references.

This version adds compensated integration, local range queries, cancellation
controls, field-local metadata checks and consistent overflow diagnostics. A
consumer workflow requests finer tables for overlapping candidates, while a
separate inverse query maps a prescribed quasi-static work capacity to a stroke
interval. The decision example distinguishes curve resolution from mass precision:
configurations 26 and 35 separate at reported masses but remain unresolved under
the +/-0.05 g mass-rounding scenario, including with full source curves.

Directed branches preserve cyclic paths and zero-work events. The standalone
summary consumer requires extrema to contain zero and the terminal error without
a unit-dependent tolerance. Its sequential binary64 composition implements the
real-arithmetic identities without enclosing arithmetic rounding.

Both local distribution formats passed 81 installed-package tests with Windows
Python 3.10, 3.12 and 3.14; archived evidence records actual dependency isolation.
Twelve additional standalone summary tests cover unit scaling, invalid envelopes,
descending branches, cancellation and overflow. The supplied workflow tests the
current source on Linux, macOS and Windows with Python 3.10-3.14, then builds,
installs and tests the exact tagged distributions before publishing a Release.
Actual remote conclusions are recorded by GitHub Actions.

The complete source contains credited public data, preparation and benchmark
programs, numerical outputs, plotting code and pinned article-building inputs.
The article identity manifest binds the accompanying PDF and editable sources to
their scientific inputs and runtime modules. Earlier author-verification records
retain their original dates and scope.

Install with `python -m pip install ./software` from the complete source or use a
tested distribution. See `REPRODUCE.md` for verification and recomputation. Code
uses the MIT License; credited experimental inputs retain CC BY 4.0.
