"""Illustrative prompt and code-design sketches for the 52 POHE records.

These are teaching sketches, not excerpts from any repository. Names and APIs
are invented to make each record's proposed contract concrete. They do not
assert that a repository implements the pattern or that the sketch is
production-ready.
"""

EXAMPLES = {
    "P01": {
        "prompt": """Work in a bounded loop. On each turn: call the model, execute any requested tool actions, record each observation, then ask the termination policy whether to continue. Return exactly one terminal result, or stop with a typed exhaustion error.""",
        "code": """def run(task, model, tools, policy):
    history = [user_message(task)]
    for turn in range(policy.max_turns):
        reply = model.respond(history)
        history.append(reply.as_message())
        for action in reply.tool_calls:
            observation = tools.execute(action, turn=turn)
            history.append(observation.as_message())
        decision = policy.decide(history, turn)
        if decision.stop:
            return decision.result
    raise LoopExhausted(turns=policy.max_turns)""",
        "note": "The runner, not the prompt, owns turn identity and the terminal decision.",
    },
    "P02": {
        "prompt": """Dispatch independent invocations concurrently. Give every invocation a stable identity, stream results as they arrive, and do not declare the batch complete until each invocation has a result, a failure, or an explicit cancellation record.""",
        "code": """async def run_batch(invocations, runtime):
    pending = {inv.id: asyncio.create_task(runtime.invoke(inv)) for inv in invocations}
    results = {}
    for finished in asyncio.as_completed(pending.values()):
        result = await finished
        results[result.invocation_id] = result
        yield result
    missing = set(pending) - set(results)
    if missing:
        raise BatchIncomplete(sorted(missing))""",
        "note": "Correlation by invocation id is the contract; concurrency alone is not.",
    },
    "P03": {
        "prompt": """Treat a paused run as an explicit state, not a sleeping function. Persist the state token before waiting, accept only known events, and reject duplicate or illegal transitions with a typed error.""",
        "code": """TRANSITIONS = {
    "ready": {"start": "running"},
    "running": {"wait": "waiting", "finish": "done"},
    "waiting": {"resume": "running", "cancel": "cancelled"},
}

def apply(state, event, store):
    target = TRANSITIONS.get(state.status, {}).get(event.kind)
    if target is None:
        raise IllegalTransition(state.status, event.kind)
    next_state = state.with_status(target, event_id=event.id)
    store.save(next_state)
    return next_state""",
        "note": "The durable record, not an in-memory coroutine, is the resumable unit.",
    },
    "P04": {
        "prompt": """Apply model and tool calls through an ordered middleware chain. Each layer may inspect, annotate, redact, or reject a call, but the final handler must see the composed result exactly once.""",
        "code": """def compose(layers, handler):
    call = handler
    for layer in reversed(layers):
        call = layer(call)
    return call

pipeline = compose(
    [trace_calls, redact_secrets, enforce_budget, retry_transient],
    invoke_model,
)
result = pipeline(request)""",
        "note": "Order is part of the contract; record the resolved chain with the result.",
    },
    "P05": {
        "prompt": """Consume the producer as an async stream. Preserve event type and sequence context, propagate cancellation, and run cleanup on every exit path, including consumer failure.""",
        "code": """async def consume(producer, consumer):
    try:
        async for event in producer:
            await consumer.handle(event)
    except asyncio.CancelledError:
        await producer.aclose()
        raise
    finally:
        await consumer.close()""",
        "note": "The stream boundary owns cancellation and cleanup; buffering is an implementation choice.",
    },
    "P06": {
        "prompt": """Keep the transition core pure. Admit steering messages through a queue with stable identity, apply them as explicit inputs, and perform side effects only through declared effect handlers.""",
        "code": """def step(state, steering, effect_handler):
    message = steering.pop()
    if message is None:
        return state
    next_state, effects = reduce_transition(state, message)
    for effect in effects:
        effect_handler.request(effect)
    return next_state""",
        "note": "Replayability comes from the input log, not from mutating shared state in place.",
    },
    "P07": {
        "prompt": """Resolve the provider's cache dialect before dispatch. Attach cache keys and cache-control blocks without changing the semantic request content; if the dialect is unknown, send an uncached request and say so.""",
        "code": """def prepare(request, registry):
    dialect = registry.resolve(request.provider)
    if dialect is None:
        return request.without_cache(), "cache dialect unsupported"
    hint = dialect.cache_hint(request.prompt, ttl=request.ttl)
    return request.with_cache(hint), "cache hint attached\"""",
        "note": "Caching is an optimization layered on the request, not a semantic rewrite.",
    },
    "P08": {
        "prompt": """Resolve a provider through a common transport contract. Normalize results and errors, report unsupported capabilities explicitly, and never leak provider-specific objects into the loop.""",
        "code": """class Transport(Protocol):
    def invoke(self, request: Request) -> Result: ...
    def capabilities(self) -> set[str]: ...

def invoke(request, registry):
    transport = registry.resolve(request.provider)
    if not transport.capabilities() >= request.required:
        raise UnsupportedCapability(request.provider, request.required)
    return transport.invoke(request.normalized())""",
        "note": "The protocol defines substitutability; the registry selects an implementation.",
    },
    "P09": {
        "prompt": """Discover tools by metadata, then invoke only the selected tool with its own schema and current permissions. Do not load every tool definition into the prompt by default.""",
        "code": """def call_tool(query, catalog, permissions):
    match = catalog.search(query)
    if match is None:
        return UnsupportedTool(query)
    tool = catalog.load(match.id, scope=permissions.scope)
    arguments = tool.schema.validate(permissions.arguments)
    return tool.invoke(arguments)""",
        "note": "Discovery, loading, and authorization are separate steps with separate evidence.",
    },
    "P10": {
        "prompt": """Cap large observations at the boundary. Tell the consumer that truncation occurred and keep the full content addressable through a stable handle; never silently return a prefix as if it were complete.""",
        "code": """def cap_observation(observation, limit):
    if len(observation.content) <= limit:
        return observation
    handle = store.put(observation.content)
    preview = observation.content[:limit]
    return Observation(
        content=preview,
        truncated=True,
        full_ref=handle,
        repair_hint=f"read({handle}, offset=...)",
    )""",
        "note": "A truncation flag without a retrieval path turns a size limit into lost evidence.",
    },
    "P11": {
        "prompt": """Distinguish a primitive tool call from a multi-step workflow. Give each a separate descriptor and execution path, and bind retry, budget, and result accounting to the correct unit.""",
        "code": """@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict

@dataclass(frozen=True)
class WorkflowRun:
    name: str
    steps: list[ToolCall]

def execute(unit, runtime):
    if isinstance(unit, WorkflowRun):
        return runtime.run_workflow(unit)
    return runtime.invoke_tool(unit)""",
        "note": "One boundary with two units; shared accounting must not blur which unit failed.",
    },
    "P12": {
        "prompt": """Spawn workers with one task record each, bounded authority, and a parent correlation id. The parent must receive a result or a failure for every worker it accepted.""",
        "code": """def spawn(parent, task, authority):
    worker = parent.runtime.spawn(
        task=task,
        parent_id=parent.id,
        authority=authority.intersect(parent.authority),
        budget=task.budget,
    )
    parent.register(worker.id, task.id)
    return worker""",
        "note": "A child without a task record is an orphan; a parent without a result is incomplete.",
    },
    "P13": {
        "prompt": """Consume durable work records with stable identity. Claim a record before acting, acknowledge only after the effect is committed, and make retries idempotent.""",
        "code": """def consume_one(queue, handler):
    record = queue.claim(timeout=30)
    if record is None:
        return None
    if not queue.is_seen(record.id):
        handler.apply_once(record.id, record.payload)
        queue.mark_seen(record.id)
    queue.ack(record.id)
    return record.id""",
        "note": "The acknowledgement rule, not the transport name, makes the queue durable.",
    },
    "P14": {
        "prompt": """Project conversation state from immutable events. Replaying the same ordered events must produce the same semantic state, even when snapshots or schema migrations are used.""",
        "code": """def project(events, initial_state):
    state = initial_state
    for event in sorted(events, key=lambda item: item.seq):
        handler = HANDLERS.get(event.kind)
        if handler is None:
            raise UnknownEvent(event.kind)
        state = handler(state, event)
    return state""",
        "note": "State is a projection; an event with no handler is a contract violation, not a no-op.",
    },
    "P15": {
        "prompt": """Load a named skill from its source location for the current run only. Record the resolved version, scope it to the run, and detect stale or conflicting versions before use.""",
        "code": """def load_skill(name, registry, run):
    skill = registry.resolve(name)
    if skill.version in run.loaded_conflicts(name):
        raise SkillConflict(name, skill.version)
    run.record_skill(name, skill.version, skill.source)
    return skill.instructions""",
        "note": "Discoverability is not enough; scope and version identity are the protected parts.",
    },
    "P16": {
        "prompt": """Emit named lifecycle events with stable payload schemas. Run handlers in declared order, state whether a handler may modify the event, and make the final decision inspectable.""",
        "code": """def emit(bus, event):
    current = event
    for handler in bus.handlers(event.kind):
        outcome = handler(current)
        if outcome is None:
            continue
        if not handler.may_modify:
            raise ImmutableEvent(handler.name)
        current = outcome
    bus.record(event.kind, current)
    return current""",
        "note": "Hook order and mutation rights are part of the contract, not documentation trivia.",
    },
    "P17": {
        "prompt": """Do not accept completion until the artifact has passed the configured verification. A failed check must return actionable feedback or block the stop; an unavailable verifier is unknown, never success.""",
        "code": """def guarded_stop(agent, proposal, verifier):
    if not proposal.requests_stop:
        return agent.continue_run()
    verdict = verifier.check(proposal.artifact)
    if verdict.passed:
        return agent.accept(proposal, evidence=verdict.evidence)
    if verdict.unknown:
        return agent.block(proposal, reason="verification unavailable")
    return agent.continue_run(feedback=verdict.feedback)""",
        "note": "The gate, not the completed status, is the acceptance authority.",
    },
    "P18": {
        "prompt": """Watch for repetition using evidence you can name: repeated actions, near-identical observations, or a declared semantic signal. Attribute any intervention to that evidence and record it in the trace.""",
        "code": """def detect_loop(history, policy):
    window = history[-policy.window :]
    if action_repetition(window) >= policy.action_threshold:
        return Intervention("repeated action", window[-1].action)
    if observation_similarity(window) >= policy.similarity_threshold:
        return Intervention("similar observations", window[-1].observation)
    return None""",
        "note": "A loop detector without a recorded reason is indistinguishable from a random nudge.",
    },
    "P19": {
        "prompt": """Account for every bounded resource at the point of use, including delegated work. When a cap is exhausted, return a distinct terminal outcome that names the responsible budget.""",
        "code": """def before_step(budget, step):
    cost = budget.estimate(step)
    if not budget.can_spend(cost):
        raise BudgetExhausted(
            resource=budget.exhausted_resource,
            limit=budget.limit,
            spent=budget.spent,
            turn=step.turn,
        )
    budget.spend(cost)""",
        "note": "A generic timeout is not a budget record; the failed cap must be attributable.",
    },
    "P20": {
        "prompt": """After a failed attempt, attach the failure evidence to that attempt and make it visible to the next revision. Stop when the retry budget is exhausted rather than retrying without new information.""",
        "code": """def revise(task, attempt, budget):
    if not budget.remaining:
        return Failed(task, attempt, reason="retry budget exhausted")
    feedback = evaluator.diagnose(attempt)
    next_prompt = task.prompt.with_feedback(
        attempt_id=attempt.id,
        feedback=feedback,
    )
    return attempt.run(next_prompt, budget.decrement())""",
        "note": "Reflection is useful only when the feedback is linked to the attempt that produced it.",
    },
    "P21": {
        "prompt": """Parse shell commands before execution. Every subcommand, pipeline stage, and redirection must receive a policy decision; if the command cannot be parsed, reject it rather than guessing.""",
        "code": """def authorize(command, policy):
    try:
        tree = shell_parser.parse(command)
    except ParseError:
        return Decision.deny("unparseable command")
    decisions = [policy.decide(node) for node in walk(tree)]
    if any(decision.denied for decision in decisions):
        return Decision.deny(decisions)
    return Decision.allow(decisions)""",
        "note": "String matching on the full command cannot cover every nested effect.",
    },
    "P22": {
        "prompt": """Compose policy layers by intersection, not by last-writer-wins. The merged decision must be at least as restrictive as every floor obligation, and the effective rule must be attributable.""",
        "code": """def merge(layers):
    decisions = [layer.evaluate(request) for layer in layers]
    denied = [decision for decision in decisions if decision.denied]
    if denied:
        return Decision.deny(denied, source=denied[0].source)
    return Decision.allow(
        max(decisions, key=lambda decision: decision.restrictiveness)
    )""",
        "note": "A permissive override may add capability, but it must not erase a floor.",
    },
    "P23": {
        "prompt": """Check the approved operation against the environment that will enforce it. If approval and enforcement differ, fail closed or request escalation; never run with less isolation than the approval assumed.""",
        "code": """def verify_enforcement(request, approval, sandbox):
    effective = sandbox.describe(request.action)
    if not approval.covers(effective):
        return Escalation(
            reason="approval/enforcement mismatch",
            approved=approval.scope,
            enforced=effective,
        )
    return sandbox.execute(request.action)""",
        "note": "The sandbox is the enforcement evidence; the approval prompt is only intent.",
    },
    "P24": {
        "prompt": """Escalate risky actions to a reviewer with the exact action identity and risk context. Bind the approval to that action hash, record the decision, and resume only the approved call.""",
        "code": """def escalate(action, reviewer):
    ticket = reviewer.request(
        action_hash=action.digest(),
        context=action.risk_context(),
        authority=action.authority,
    )
    if ticket.decision != "approved":
        return Denied(action, ticket.reason)
    if ticket.action_hash != action.digest():
        return Denied(action, "approval bound to different action")
    return action.execute()""",
        "note": "Approval must name the action; a blanket yes is not an authorization record.",
    },
    "P25": {
        "prompt": """Resolve capabilities at the call boundary using the principal, requested scope, and active profile. Record the covering scope that authorized the call, or deny with the missing scope.""",
        "code": """def authorize_call(principal, capability, registry):
    scopes = registry.scopes_for(principal)
    covering = [scope for scope in scopes if scope.covers(capability)]
    if not covering:
        return Denied(capability, missing=capability.required_scope)
    decision = max(covering, key=lambda scope: scope.specificity)
    return Allowed(capability, scope=decision.id)""",
        "note": "A session grant is not a blanket capability; the covering scope belongs in the record.",
    },
    "P26": {
        "prompt": """Branch a conversation only at a stable event boundary. The new branch must record its parent, boundary, and provenance, and invalid or missing boundaries must be rejected.""",
        "code": """def branch(session, boundary_event_id):
    parent = session.events.by_id(boundary_event_id)
    if parent is None or not parent.is_boundary:
        raise InvalidBranch(boundary_event_id)
    child = session.fork(
        parent_id=session.id,
        boundary=parent.id,
        state=parent.snapshot(),
        provenance=session.provenance(),
    )
    return child""",
        "note": "A rewind without provenance destroys the audit trail that made it useful.",
    },
    "P27": {
        "prompt": """Compact context against a target budget while protecting declared items. Record which history was replaced by which summary, and keep the lineage queryable after compaction.""",
        "code": """def compact(history, policy, target_tokens):
    protected, evictable = history.split(policy.protected_ids)
    summary = summarize(evictable, max_tokens=target_tokens - protected.tokens)
    replacement = ContextSummary(
        text=summary,
        replaces=[item.id for item in evictable],
        protected=[item.id for item in protected],
    )
    return history.replace(evictable, replacement)""",
        "note": "Compaction is a provenance operation, not just a shorter string.",
    },
    "P28": {
        "prompt": """Write candidate memories with a source and intended scope. Consolidate without losing retrieval identity or revision history, and make memory retrievable only within its declared scope.""",
        "code": """def consolidate(candidate, store):
    existing = store.find(candidate.key, scope=candidate.scope)
    if existing and existing.source == candidate.source:
        return store.revise(existing.id, candidate.content)
    record = MemoryRecord(
        key=candidate.key,
        content=candidate.content,
        source=candidate.source,
        scope=candidate.scope,
        revision=1,
    )
    return store.insert(record)""",
        "note": "A memory without a source or scope cannot be audited or safely revoked.",
    },
    "P29": {
        "prompt": """Expose the harness through a declared compatibility protocol. Map capabilities explicitly, return protocol-shaped errors, and reject requests that the backend cannot satisfy.""",
        "code": """def handle(request, backend, protocol):
    if not protocol.supports(request.method):
        return protocol.error("method_not_supported", request.id)
    try:
        result = backend.invoke(protocol.to_backend(request))
    except BackendError as error:
        return protocol.error(error.code, request.id, detail=error.detail)
    return protocol.from_backend(result)""",
        "note": "Compatibility is a contract over requests, results, and errors, not a renamed endpoint.",
    },
    "W01": {
        "prompt": """Run the named stages in order. Validate each handoff against its declared schema, and make the final output identify the stage lineage that produced it.""",
        "code": """def run_chain(stages, initial_input):
    payload, lineage = initial_input, []
    for stage in stages:
        validated = stage.input_schema.validate(payload)
        payload = stage.run(validated)
        lineage.append(stage.id)
    return ChainResult(output=payload, lineage=lineage)""",
        "note": "A chain without validated handoffs is a sequence of unrelated prompts.",
    },
    "W02": {
        "prompt": """Select a route by declared capabilities and selection criteria. If no route can handle the input, return unsupported rather than silently falling back to a generic answer.""",
        "code": """def route(request, routes):
    candidates = [route for route in routes if route.can_handle(request)]
    if not candidates:
        return Unsupported(request.kind)
    chosen = max(candidates, key=lambda route: route.confidence(request))
    return chosen.dispatch(request)""",
        "note": "Routing evidence is the selected route's capability, not the router's confidence alone.",
    },
    "W03": {
        "prompt": """Partition only work that is independent enough to run concurrently. Fan in every expected result, record missing partitions explicitly, and do not aggregate a partial set as complete.""",
        "code": """def fan_out(partitions, worker):
    futures = [worker.submit(part) for part in partitions]
    results = {}
    for partition, future in zip(partitions, futures):
        try:
            results[partition.id] = future.result()
        except WorkerError as error:
            results[partition.id] = FailedPartition(partition.id, error)
    return Aggregation(results, expected=len(partitions))""",
        "note": "The aggregation contract includes absence; a shorter list is not a successful fan-in.",
    },
    "W04": {
        "prompt": """Decompose the task into worker-sized units, dispatch each with a task record, and require a result or failure for every dispatched task before composing the answer.""",
        "code": """def orchestrate(task, workers):
    tasks = planner.decompose(task)
    pending = {item.id: workers.dispatch(item) for item in tasks}
    results = {}
    for task_id, handle in pending.items():
        results[task_id] = handle.result_or_failure()
    if any(isinstance(result, Failure) for result in results.values()):
        return PartialResult(results)
    return composer.compose(results)""",
        "note": "Dynamic decomposition is bounded by the result ledger, not by the planner's confidence.",
    },
    "W05": {
        "prompt": """Generate candidates, evaluate them against declared criteria, and revise only within the revision budget. Select the passing candidate or the best recorded one, with its evaluation attached.""",
        "code": """def optimize(task, generator, evaluator, budget):
    best = None
    for revision in range(budget):
        candidate = generator.generate(task, feedback=best.feedback if best else None)
        score = evaluator.evaluate(candidate, task.criteria)
        best = Candidate(candidate, score, revision)
        if score.passed:
            break
    return Selection(best, criteria=task.criteria, revisions=revision + 1)""",
        "note": "The selected output must map to an evaluation record, not an unstated preference.",
    },
    "W06": {
        "prompt": """Let the manager own task assignment and integration. Specialists may propose outputs, but the manager must attribute each contribution and decide what enters the final result.""",
        "code": """def manage(task, specialists, manager):
    assignments = manager.assign(task, specialists)
    contributions = []
    for specialist, subtask in assignments:
        output = specialist.run(subtask)
        contributions.append(Attribution(specialist.id, subtask.id, output))
    return manager.integrate(task, contributions)""",
        "note": "Attribution is the manager's contract; unlabeled specialist text is not integration.",
    },
    "W07": {
        "prompt": """Hand off control only with an explicit target and trigger. Record the source, target, and transferred state, and enforce a cycle bound so a peer conversation can terminate.""",
        "code": """def handoff(session, target, trigger, state):
    if session.handoff_count >= session.max_handoffs:
        raise HandoffLimit(session.id)
    record = HandoffRecord(
        source=session.active_agent,
        target=target,
        trigger=trigger,
        state=state.redact_for(target),
    )
    session.apply(record)
    return target.resume(session)""",
        "note": "A transfer without state or a cycle bound is an unbounded conversation, not coordination.",
    },
    "C01": {
        "prompt": """Route participant messages through a mediator with stable identities and schemas. The mediator must record the routing decision and return a response or an explicit non-delivery.""",
        "code": """def mediate(message, participants):
    route = router.resolve(message.recipient, participants)
    if route is None:
        return NonDelivery(message.id, reason="unknown recipient")
    response = route.send(message)
    log.record(message.id, route.id, response.id)
    return response""",
        "note": "The mediator owns routing evidence; direct side channels defeat the pattern.",
    },
    "C02": {
        "prompt": """Notify subscribers after a subject change, within their declared subscription lifetime. An unsubscribed observer must not receive later notifications.""",
        "code": """class Subject:
    def __init__(self):
        self.observers = {}

    def subscribe(self, observer):
        self.observers[observer.id] = observer

    def unsubscribe(self, observer_id):
        self.observers.pop(observer_id, None)

    def publish(self, event):
        for observer in list(self.observers.values()):
            observer.notify(event)""",
        "note": "Subscription lifetime is the contract; notification order is secondary.",
    },
    "C03": {
        "prompt": """Deliver events by declared topic. Record whether a subscriber received or dropped an event, and make subscriber selection attributable to the topic and compatibility rules.""",
        "code": """def publish(event, bus):
    subscribers = bus.subscribers(event.topic)
    delivered = []
    for subscriber in subscribers:
        if not subscriber.accepts(event.schema):
            delivered.append(Dropped(subscriber.id, "schema mismatch"))
            continue
        subscriber.deliver(event)
        delivered.append(Delivered(subscriber.id))
    bus.record(event.id, event.topic, delivered)""",
        "note": "Publish-subscribe needs a delivery record; broadcast is not the same as delivery.",
    },
    "C04": {
        "prompt": """Resolve a provider by identity and versioned service description. The client and provider must agree on the schema or return an explicit incompatibility, never a guessed call.""",
        "code": """def invoke(service_id, request, registry):
    provider = registry.resolve(service_id)
    if provider is None:
        return Incompatible(service_id, reason="not registered")
    if not provider.schema.accepts(request):
        return Incompatible(service_id, reason="schema mismatch")
    return provider.call(request)""",
        "note": "Discovery without schema agreement is a lookup, not a broker contract.",
    },
    "R01": {
        "prompt": """Interleave reasoning and action through a parseable protocol. Every executed action must have an attributable observation or an execution error; unparsed output is not an action.""",
        "code": """def reason_act(task, model, tools):
    trace = []
    while not trace or trace[-1].kind != "final":
        raw = model.complete(task, trace)
        step = protocol.parse(raw)
        if step.kind == "action":
            try:
                observation = tools.execute(step.action)
            except ToolError as error:
                observation = Observation.error(step.action, error)
            trace.append(observation)
        else:
            trace.append(step)
    return trace""",
        "note": "The parser is the boundary between thought and effect; every effect gets an observation.",
    },
    "R02": {
        "prompt": """Store verbal reflections with links to the attempt and feedback that produced them. Retrieve a reflection only with its source, and keep it updateable or revocable when later evidence changes.""",
        "code": """def reflect(attempt, feedback, memory):
    note = Reflection(
        text=evaluator.explain(attempt, feedback),
        attempt_id=attempt.id,
        feedback_id=feedback.id,
        scope=attempt.task.scope,
    )
    memory.put(note)
    return note

def retrieve(task, memory):
    return [note for note in memory.search(task) if note.scope == task.scope]""",
        "note": "A reflection without provenance becomes an unfalsifiable instruction.",
    },
    "E01": {
        "prompt": """Specialize the base harness only through a substitutable contract. Dispatch to the intended subtype at the declared boundary, and keep base behavior legal for every override.""",
        "code": """class Harness(Protocol):
    def step(self, state: State) -> State: ...

class ToolHarness:
    def step(self, state):
        return state.with_action(self.tools.choose(state))

class WorkflowHarness:
    def step(self, state):
        return state.with_workflow(self.workflows.advance(state))

def run(harness: Harness, state):
    return harness.step(state)""",
        "note": "Inheritance is only a pattern when the base contract survives substitution.",
    },
    "E02": {
        "prompt": """Propose a harness edit, probe it on permitted cases, and compose only edits whose probe results support the change. Keep the proposed diff, probe evidence, and provenance together.""",
        "code": """def improve(harness, probes):
    proposal = proposer.edit(harness)
    results = [probe.run(proposal.candidate) for probe in probes]
    record = EditRecord(proposal.diff, results, harness.version)
    if not all(result.accepted for result in results):
        return Rejected(record)
    return Composed(harness.apply(proposal), record)""",
        "note": "A probe is evidence about this edit, not a universal guarantee for the next one.",
    },
    "E03": {
        "prompt": """Screen every candidate edit on separate acceptance data before it reaches final evaluation. Accepted edits must carry the screening evidence that justified them.""",
        "code": """def accept(candidate, screen, holdout):
    screening = screen.evaluate(candidate)
    if not screening.passed:
        return Rejected(candidate, screening)
    final = holdout.evaluate(candidate)
    return Accepted(
        candidate,
        screening=screening,
        final=final,
    ) if final.passed else Rejected(candidate, final)""",
        "note": "Final evaluation is not a second screening set; keep the roles distinct.",
    },
    "E04": {
        "prompt": """State objective direction, weights, and constraints before evaluating candidates. Record the candidate vectors and the dominance or scoring rationale behind the selection.""",
        "code": """def select(candidates, objectives):
    scored = [objectives.score(candidate) for candidate in candidates]
    frontier = pareto_front(scored)
    chosen = objectives.tie_break(frontier)
    return Selection(
        chosen,
        vectors=[item.vector for item in scored],
        frontier=[item.id for item in frontier],
    )""",
        "note": "A Pareto front explains trade-offs; a single unlabeled score hides them.",
    },
    "E05": {
        "prompt": """Compose harness components only through compatible contracts. Reject an invalid composition before execution, and keep the builder and component versions immutable.""",
        "code": """def compose(components):
    builder = HarnessBuilder()
    for component in components:
        if not builder.accepts(component.contract):
            raise IncompatibleComposition(component.id, builder.contract)
        builder = builder.add(component)
    return builder.freeze()""",
        "note": "A foundry's value is rejection before execution, not a larger configuration space.",
    },
    "E06": {
        "prompt": """Version policy and harness variants as a pair. Every result must identify the evaluated pair, and separate each objective's contribution where the design permits.""",
        "code": """def evaluate_pair(harness, policy, suite):
    result = suite.run(harness=harness, policy=policy)
    return PairResult(
        harness_version=harness.version,
        policy_version=policy.version,
        metrics=result.metrics,
        ablations=suite.ablate(harness, policy),
    )""",
        "note": "A score without the pair identity cannot support a joint-evolution claim.",
    },
    "E07": {
        "prompt": """Generate executable candidates in an isolated runtime, evaluate every selected candidate, and retain execution and fitness provenance for the archive.""",
        "code": """def search(task, evaluator, archive):
    candidate = generator.propose(task, archive)
    with sandbox.run(candidate) as run:
        result = run.output()
    fitness = evaluator.score(result, task)
    archive.add(CandidateRecord(candidate, result, fitness))
    return archive.best()""",
        "note": "Selection is only as trustworthy as the isolation and provenance of the run.",
    },
    "E08": {
        "prompt": """Observe the task state and the candidate adaptation targets. Choose a target that is compatible with the current environment, and record why that target was selected.""",
        "code": """def adapt(state, candidates, policy):
    viable = [
        candidate for candidate in candidates
        if candidate.compatible(state.environment)
    ]
    if not viable:
        return NoAdaptation("no compatible target")
    chosen = policy.choose(viable, state)
    return Adaptation(
        target=chosen.id,
        kind=chosen.kind,
        evidence=chosen.compatibility_record,
    )""",
        "note": "Harness and weight adaptation are different targets with different evidence.",
    },
    "E09": {
        "prompt": """Link planner and executor state with compatible identities and timing. Deliver corrective feedback before the affected action when the reactor's deadline requires it.""",
        "code": """def assist(plan, execution, reactor):
    for step in execution.pending():
        hint = reactor.observe(plan.state, step)
        if hint and hint.deadline <= step.start:
            plan = plan.with_hint(hint)
            execution = execution.revise(step, hint)
    return execution.finish(plan)""",
        "note": "Assistance is a timing contract; late feedback is a postmortem, not a correction.",
    },
    "E10": {
        "prompt": """Compare traces to identify an affected harness component, propose a change, and evaluate it before acceptance. Retain the observation, hypothesis, diff, and evaluation as one provenance chain.""",
        "code": """def evolve(trace_pair, harness):
    diagnosis = diagnose(trace_pair)
    if diagnosis.component is None:
        return NoChange(diagnosis)
    diff = propose_edit(harness, diagnosis)
    result = evaluate(harness.apply(diff))
    return EvolutionRecord(
        observation=trace_pair.evidence,
        hypothesis=diagnosis,
        diff=diff,
        evaluation=result,
    )""",
        "note": "Observability becomes evolution only when the trace is tied to an evaluated change.",
    },
}
