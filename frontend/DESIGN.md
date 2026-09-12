# FinTwin Design Language

FinTwin is database performance engineering software. It is not an AI showcase or a marketing dashboard.

## Design adjectives

1. Technical
2. Calm
3. Precise
4. Data-driven
5. Professional

## Visual contract

Prefer strong typography, purposeful whitespace, solid surfaces, subtle dividers, restrained teal accents, readable tables, useful charts, inline status indicators, and familiar engineering controls.

Avoid gradient backgrounds, gradient text, neon glow, glassmorphism, excessive rounded cards, nested containers, giant heroes, decorative AI imagery, excessive pills, vague SaaS language, unnecessary animations, and decorative elements without a functional reason.

## Themes

Dark is the default and should feel like professional database observability software. Light is an intentional technical analytics theme, not an inverted dark mode. Both themes use the same semantic tokens for surfaces, borders, text, accents, status, charts, forms, drawers, and feedback states.

## Hierarchy

A page title explains the task. Section headings group related work. Labels describe controls. Metrics are prominent through type and alignment, not a grid of decorative cards. One container has one purpose; whitespace and dividers do most of the grouping.

FinTwin is a work surface, not a dashboard template. Charts and tables carry more visual weight than decorative metric cards. Metrics are grouped by analytical relationship, not by card count. Containers exist to establish functional grouping, not visual decoration. FinTwin should look increasingly like database tooling as the user moves deeper into Experiments, Prediction, Optimization, and Validation.

## Data integrity

All displayed performance values, experiments, predictions, recommendations, and validation results come from the existing FastAPI APIs. Missing data remains visibly unavailable. The UI never invents measurements or confidence values.
