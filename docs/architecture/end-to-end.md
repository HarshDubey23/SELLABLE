# End to end

One mission, from a sentence to a settled payment, with every branch that
can actually happen.

## The happy path

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant I as Issuer<br/>(wallet / CLI)
    participant A as Buyer agent
    participant D as Discovery
    participant T as Storefront tools
    participant G as Gateway R1–R12
    participant B as Approval binding
    participant E as Execution machine
    participant P as Provider
    participant W as Webhook
    participant L as Audit chain

    U->>I: "cricket bat under ₹2,000"
    I->>A: signed mission (budget, categories, expiry)
    A->>D: gather market evidence
    D-->>A: listings, provenance-tagged, untrusted
    A->>T: proposal — SKUs and quantities only
    T->>T: reprice from server catalog
    T->>G: evaluate
    G->>L: verdict + full rule matrix
    G-->>T: APPROVE
    T->>B: register binding over every bound field
    U->>I: co-sign this exact cart
    I-->>T: intent mandate + cart mandate
    T->>B: verify + consume (atomic)
    T->>E: open execution, EXECUTION_PENDING
    E->>E: REMOTE_ATTEMPTED (on disk, before dispatch)
    E->>P: create order
    P-->>E: order id
    E->>E: EXECUTED
    E->>L: order_created
    P->>W: payment.captured (signed)
    W->>W: verify raw-body HMAC, persist, audit, APPLIED
    W->>L: payment_captured
```

## Every branch that can fire

```mermaid
flowchart TD
    Start([Proposal submitted]) --> Sig{"R9<br/>signature valid?"}
    Sig -->|no| Rej1["REJECT — forged mission<br/>0 provider calls"]
    Sig -->|yes| Exp{"R10<br/>mission live?"}
    Exp -->|no| Rej2["REJECT — expired"]
    Exp -->|yes| Rules{"R1 R2 R5 R4 R3<br/>R11 R12 R7 R6"}
    Rules -->|any fails| Rej3["REJECT — revisable or fatal<br/>agent may re-propose"]
    Rules -->|all pass| Mand{"mandates<br/>present and valid?"}
    Mand -->|no| Rej4["422 / 403 — no order"]
    Mand -->|yes| Bind{"binding matches<br/>and unconsumed?"}
    Bind -->|no| Rej5["403 — replay, drift,<br/>cart swap, expiry"]
    Bind -->|yes| Claim{"dispatch claim<br/>won?"}
    Claim -->|no| Rej6["409 EXECUTION_IN_PROGRESS<br/>concurrent caller backs off"]
    Claim -->|yes| Call["call provider"]
    Call -->|success| Done["EXECUTED"]
    Call -->|"4xx"| Fail["FAILED — definitive"]
    Call -->|"timeout · reset · 5xx"| Amb["RECONCILIATION_REQUIRED"]
    Call -->|"process dies"| Amb
    Amb --> Rec{"authoritative read"}
    Rec -->|order exists| Done
    Rec -->|no order| Fail
    Rec -->|provider down| Amb

    style Rej1 fill:#3a2222,color:#fff
    style Rej2 fill:#3a2222,color:#fff
    style Rej3 fill:#3a2222,color:#fff
    style Rej4 fill:#3a2222,color:#fff
    style Rej5 fill:#3a2222,color:#fff
    style Amb fill:#3a3222,color:#fff
    style Done fill:#1e3a2e,color:#fff
```

Every rejection path above appends to the audit chain with its rule id or
error code, so a refusal is as traceable as a success.

## Where each branch is tested

| Branch | Test |
|---|---|
| R9 forged signature | `tests/gateway/test_r9_signature.py` |
| R10 expiry | `tests/gateway/test_r10_expiry.py` |
| R1 budget, R3 drift, R2/R5 scope | `tests/gateway/test_matrix.py`, `tests/security/` |
| Every bound field of the binding | `tests/gateway/test_binding_field_matrix.py` |
| Replay of a consumed binding | `tests/gateway/test_binding_field_matrix.py` |
| Concurrent execution | `tests/execution/test_execution_e2e.py` |
| Timeout → reconcile → EXECUTED | `tests/execution/test_execution_e2e.py` |
| Lost request → reconcile → FAILED | `tests/execution/test_execution_e2e.py` |
| Crash mid-flight → recovery | `tests/execution/test_execution_state_machine.py` |
| Webhook duplicate, crash window | `tests/test_webhook_crash_recovery.py` |
| Chain tamper halts the money path | `tests/test_audit_chain_true_tamper.py` |
