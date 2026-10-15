# Banned defaults: polaris-design

These are banned in this design system. If code would use one of these, use the "Instead" column. If "Instead" is empty, follow the gap rule in DESIGN.md section 12.

| Banned | Instead | Why |
|---|---|---|
| Purple or blue gradients on buttons, heroes, or backgrounds | Solid colors from section 2 | The most recognizable sign of AI-built UI; no flashy gradients (Trustworthy) |
| Gradient text on headings | Solid `color.text.primary` | Hard to read, a landing page cliche |
| Inter or the system font picked as a fallback choice | `font.family.body` | Every AI product ends up looking the same |
| Emoji used as icons in headings, buttons, lists, or nav | Lucide icons (section 9) | Looks unserious, renders differently on every device |
| Glassmorphism and background blur | Solid surfaces: `color.surface.raised`, `color.surface.overlay` | Hurts contrast and performance |
| Large rounded cards with soft shadows everywhere | Flat cards with a `color.border.default` border, no shadows (section 5) | When everything floats, nothing stands out |
| Decorative blobs, orbs, or wavy background shapes | Empty space | Visual noise with no meaning |
| Glowing or neon accents around buttons or cards | Nothing; the focus ring only shows focus | Template look |
| Every element centered | Left-aligned text and forms; only empty states are centered | Centered text and forms are harder to scan |
| Pill-shaped everything by default | Corners by element (5.4); fully round only for badges, avatars, radios, the progress bar, comment pins, and the sheet handle | A default, not a decision |
| Thin grey text on white that fails contrast | Text tokens from 2.1, all checked in 2.2 | Fails people with low vision |
| Animated everything: fade-in on scroll, bouncing, hover lifts | Only the motion listed in 8.2 | Slow and distracting |
| Centered hero with a big headline and two buttons | | Generic landing page shape |
| Generic three-column feature grid | | Says nothing specific |
| Stat strips with made-up numbers | Real numbers only, or none | Fake proof |
| Testimonial carousels with placeholder people | | Fake proof |
| "Get started" as the main action | The real action, such as "Start a session" | Says nothing about what happens |
| Hype words: Unlock, Supercharge, Seamless, Revolutionize, Elevate, Effortless | A plain description (10.3) | Every product sounds the same |
| "Welcome to Polaris!" or "Oops! Something went wrong." | The copy patterns in 10.2 | Filler that does not help |
| Exclamation marks in UI text | Full stops | Forced cheerfulness |
| Lorem ipsum or invented sample data in the shipped UI | Real content, or the empty state | Looks unfinished and misleads |
| Status and notification dots | A badge with text (Badge) | The user says dots look like AI design |
| The sparkle icon to mean "AI" | The Polaris star mark (section 9) | AI cliche |
| Bouncing three-dot "typing" animations | The thinking indicator's status text (Thinking indicator) | AI cliche, and it says nothing about what is happening |
| "As an AI..." phrasing, robot or brain icons for the tutor | The tutor speaks as Polaris (10.4); the Polaris star mark | AI cliche |
