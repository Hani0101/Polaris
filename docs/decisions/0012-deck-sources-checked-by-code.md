---
status: accepted
---

# A deck's sources are checked by code

A flashcard deck is a revision aid, so a wrong card does more harm than a missing one: the learner memorises it. The first defence is that every card must have a source in the session's turns or resources (FC-04, FC-05), and when none covers the topic no deck is made (FC-07). Writing cards from the model's memory is not allowed.

The second defence is a check in code before the deck is stored (FC-06). A cited PDF page must exist, a quoted phrase must appear in that resource's extracted text, and a cited turn must exist. A deck with one failing card is refused whole, and the agent may send it once more.

The quiz uses a second model to answer the questions without the key (QZ-12). Flashcards do not. The check is mechanical, costs no model call, and catches the failure that matters most, an invented citation. The cost is that it does not prove a card's claim matches the text it cites. A card can quote a real phrase and still summarise it badly. That gap is accepted for v1. A check that asks a model whether the claim follows from the quote is parked in `later.md`.

The check applies to the sources v1 has. Fetching from the internet is a later source ([product](../product.md)); until it ships, the agent says it is not available (FC-07). When it does, a fetched page becomes a source the same code can check, and this decision is revisited then.
