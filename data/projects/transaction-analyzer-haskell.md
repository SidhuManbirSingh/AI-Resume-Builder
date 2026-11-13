---
id: haskell_transaction_analyzer
title: E-Commerce Functional Transaction Analyzer
github_repo: Transaction-Analyser-Haskell
github_url: https://github.com/SidhuManbirSingh/Transaction-Analyser-Haskell
technologies:
  - Haskell
  - GHC
  - Functional Programming
  - Data.Foldable
  - Text.Printf
domain: Functional Programming & High-Performance Data Processing
status: completed
summary: High-performance transaction processing engine written in Haskell, demonstrating algebraic data types, higher-order filtering functions, and strict left-fold evaluation.
metrics: Stack-safe aggregation on large transaction datasets using foldl' strict evaluation; formatted fixed-width tabular terminal outputs.
---

### E-Commerce Functional Transaction Analyzer | [GitHub](https://github.com/SidhuManbirSingh/Transaction-Analyser-Haskell)
*Haskell | GHC | Functional Programming | Data Pipelines*

- Designed a pure functional transaction processing system in Haskell utilizing custom algebraic data types with record syntax.
- Implemented composable higher-order filtering operations allowing multi-criteria filtering by category, date range, and spending threshold.
- Utilized strict left-fold evaluation (foldl') to compute categorical spending totals, preventing space leaks and stack overflows on large datasets.
- Engineered formatted tabular output generators using Text.Printf for fixed-width, aligned terminal reports.
- Leveraged strong type safety with typeclass derivations (Show, Eq) and function composition operators ($) for clean, modular code.

