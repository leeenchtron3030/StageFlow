# Shared Result

## Purpose

Contains a small explicit success/failure result type that can be used across bounded contexts.

## Current Scope

`Result` represents either success with a value or failure with a structured `StageFlowError`.

It is not intended to replace exceptions for programmer errors.
