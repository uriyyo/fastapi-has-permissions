# Testing Permissions

A permission resolves dependencies, so calling `check_permissions()` directly stops working as
soon as a rule needs a repository or an actor. `fastapi_has_permissions.testing` evaluates rules
the way the library does, and reports what happened when the assertion fails.

```python
from fastapi_has_permissions.testing import assert_allowed, assert_denied, assert_skipped
```

All three are coroutines. Each returns the result it asserted, so a test can keep inspecting it.

## Asserting an Outcome

```python
@pytest.mark.asyncio
async def test_a_teacher_owns_their_student():
    async with evaluate.scope({ActorDep: teacher}):
        await assert_allowed(OwnsStudent(Given(student.id)))
        await assert_denied(OwnsStudent(Given(other_student.id)))
```

[`evaluate.scope()`](evaluating.md#scopes) supplies the actor and any other dependency the rule
needs, exactly as a background job would. The assertions pick up the surrounding scope on their
own, so there is nothing to thread through.

## Asserting the Error

`assert_denied` checks any part of the error configuration you name, and ignores the rest:

```python
await assert_denied(
    OwnsStudent(Given(student.id)),
    status_code=404,
    code="student_inactive",
)
```

It returns the [`Failed`](skip_and_fail.md#result-types), so anything it does not cover is still
available:

```python
failed = await assert_denied(OwnsStudent(Given(student.id)))

assert "student" in failed.reason
```

## Asserting an Abstention

A rule that does not apply is a third outcome, distinct from allow and deny -- see
[`When`](wrappers.md#when-say-a-rule-does-not-apply):

```python
async def test_a_teacher_rule_ignores_a_student():
    async with evaluate.scope({ActorDep: student_actor}):
        await assert_skipped(When(IsTeacherActor(), OwnsStudent(Given(student.id))))
```

!!! warning

    `assert_denied` rejects an abstention rather than accepting it. A skip *does* deny once it
    reaches the root, so the two are easy to confuse -- but a rule that stopped applying and a
    rule that refused are different bugs, and a test that cannot tell them apart will keep
    passing when a guard starts matching the wrong actor.

    ```
    OwnsStudent was expected to deny, but it abstained - a skip denies at the root,
    but it is not a denial - use `assert_skipped` to assert an abstention
    ```

## Failure Messages

Each assertion says what it expected and what it got, so a failure is readable without dropping
into a debugger:

```
Deny was expected to allow, but it denied with 403 'Permission denied'
NotFound denied, but its status_code was 404 rather than the expected 403
Deny was expected to abstain, but it denied with 403 'Permission denied'
```

## Testing Through a Route

None of this replaces an end-to-end check. Where you want to assert the *response* rather than
the decision, use FastAPI's `TestClient` as usual -- the permission raises
[`PermissionDeniedError`](custom_errors.md#the-error-a-denial-raises) and the installed handler
turns it into a response:

```python
def test_the_route_is_guarded(client):
    assert client.get("/students/1").status_code == 404
```
