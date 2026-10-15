# Starter list of banned AI defaults

These are the choices an AI makes when nobody told it otherwise. They make a product look generic. In section 11, show this list numbered, with the one-line reason, and let the user pick which to ban (for example "ban 1-8 and 12, keep 9"). Then ask for their own additions. Only what the user picks goes into banned.md.

For each banned item, ask what to do instead if the answer is not obvious from earlier sections. If the user does not say, leave "Instead" empty, which means the gap rule applies.

## Visual

1. **Purple or blue gradients** on buttons, heroes, or backgrounds. The single most recognizable sign of AI-generated UI.
2. **Gradient text** on headings. Hard to read, and a cliche of landing page templates.
3. **Inter, or the system font, picked as a fallback choice.** It is what an AI reaches for when it has no instruction, so the product ends up looking like every other one. (Using Inter on purpose, chosen in section 3, is fine; this bans it as a default.)
4. **Emoji used as icons** in headings, buttons, feature lists, or nav. Looks unserious and renders differently on every device.
5. **Glassmorphism and background blur** (frosted panels, `backdrop-filter: blur`). Hurts contrast and performance, and dates quickly.
6. **Large rounded cards with soft shadows everywhere.** When everything floats, nothing stands out, and every screen looks like a template.
7. **Decorative blobs, orbs, or wavy shapes** in the background. Visual noise with no meaning.
8. **Glowing or neon accents** (colored box-shadow glows around buttons or cards). Same template look as gradients.
9. **Every element centered.** Centered body text and forms are harder to scan than left-aligned ones.
10. **Pill-shaped everything** (fully round buttons, inputs, and tags by default). A default, not a decision.
11. **Thin gray text on white** for secondary content. Usually fails contrast.
12. **Animated everything** (fade-in on scroll for every block, bouncing buttons, hover lifts on all cards). Slow and distracting.

## Layout

13. **Centered hero with a big headline and two buttons** ("Get started" and "Learn more"). The default landing page shape.
14. **Generic three-column feature grid** of icon, title, and one line of text. Says nothing specific.
15. **Stat strips with made-up numbers** ("10k+ users, 99.9% uptime"). Fake proof.
16. **Testimonial carousels with placeholder people.** Fake proof.

## Copy

17. **"Get started" as the main call to action.** Says nothing about what the user will actually do.
18. **"Unlock the power of", "Supercharge", "Seamless", "Revolutionize", "Elevate", "Effortless".** Hype words that make every product sound the same.
19. **"Welcome to <product>!" or "Oops! Something went wrong."** Filler that does not help the user.
20. **Exclamation marks in UI text.** Reads as forced cheerfulness.
21. **Lorem ipsum or invented sample data left in shipped UI.**
