# Architecture

Four documents, each answering one question. They describe the code as it
is today; where the implementation is weaker than the idea, the document
says so rather than drawing the idea.

| Document | Question it answers |
|---|---|
| [system.md](system.md) | What are the parts, and which of them are trusted? |
| [money-safety.md](money-safety.md) | Why can't the AI spend money? |
| [execution-lifecycle.md](execution-lifecycle.md) | What happens when the payment API times out? |
| [trust-boundary.md](trust-boundary.md) | Where exactly does untrusted data stop being dangerous? |
| [security-claims.md](security-claims.md) | Claim-by-claim, what is proven and by what? |

Diagrams are Mermaid so they render on GitHub and stay editable in the
same file as the prose that explains them.
