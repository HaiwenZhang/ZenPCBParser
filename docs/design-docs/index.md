# Design Docs Index

## Purpose

This folder holds durable design decisions and operating principles. Use it for
cross-cutting reasoning that is more specific than `docs/DESIGN.md` but broader
than an execution plan.

## Documents

- `core-beliefs.md`: agent-readable beliefs for maintaining this repository.

## When To Add A Design Doc

Add a focused design doc when a decision affects more than one package, changes
how future agents should reason about the codebase, or explains a tradeoff that
is likely to recur.

Do not store temporary debug notes here. Use `docs/exec-plans/active/` for live
work and move completed plans when done.
