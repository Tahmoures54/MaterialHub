# MaterialHub Unified UX & Role Workspace System

## Design principle
One platform, one language, role-specific focus.

## Shared design system
- Tokens: color, spacing, radius, elevation
- Components: cards, KPI blocks, action rows, workspace navigation
- Responsive grid rules
- Shared status and risk semantics

## Role workspaces
Project Manager, Engineering, Procurement, Warehouse, Quality, Supplier and Administrator each receive a focused landing workspace.

## UX rules
1. Show the next best action before secondary information.
2. Show operational risk in context.
3. Preserve traceability from requirement to issue.
4. Avoid duplicate navigation and role-irrelevant screens.
5. Use progressive disclosure for complex workflows.

## Recommended rollout
Replace legacy page-specific styles incrementally with `design-system.css`, then connect each workspace KPI to the existing APIs and domain services.
