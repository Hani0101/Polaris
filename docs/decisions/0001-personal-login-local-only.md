# Personal login, local only

v1 is one learner on one machine. Polaris reaches Claude through that person's Claude login. There is no accounts server. If an API key is present, v1 stops, so the local login cannot be silently replaced.

Hosting comes later, if there is time. That version signs learners in with Google OAuth, keeps an accounts server, and calls Claude with an API key. Extra backend copies, a load balancer, more Manim workers, a video cache, cloud video storage, and per-learner rate limits belong to that same later version.
