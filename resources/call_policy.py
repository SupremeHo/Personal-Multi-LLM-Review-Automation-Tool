# Resource limits for the paid call path, defined once instead of scattered as
# magic numbers across the service and provider layers.
#
# These are deliberate trade-offs, not SDK defaults. Each one exists because the
# default is wrong for a personal CLI that spends real money per call, and the
# reasoning is kept next to the number so it can be revised knowingly.

from __future__ import annotations

import httpx

MAX_PARALLEL_CALLS = 5
"""
Ceiling on simultaneous provider calls in one `compare`.

`--target` is repeatable with no limit, so an unbounded pool turns a typo into a
burst of concurrent requests and a wall of 429s. Five keeps every realistic
comparison fully parallel (the tool has three providers) while capping the burst.
"""

CONNECT_TIMEOUT_SEC = 10.0
"""
How long to wait for the TCP/TLS handshake.

Short on purpose: nothing has been billed yet, so giving up costs nothing, and an
unreachable host is exactly the case where the SDK default (10 minutes) would hold
a whole comparison hostage.
"""

READ_TIMEOUT_SEC = 300.0
"""
How long to wait for the response body once the request is in.

Generous on purpose, and for the opposite reason: by this point the provider is
generating and the call will be billed, so a timeout here throws away a response
we pay for. This must only fire on a genuinely stuck connection, never on a slow
long answer - lower it and it starts breaking the "never discard a billed
response" invariant from the outside.
"""

MAX_RETRIES = 2
"""
Retries the SDK may perform after the first attempt (connection errors, 408, 409,
429, 5xx).

This is the SDKs' own default, written down rather than inherited, because the
decision that matters is that the retry budget lives *here and only here*: adding
an application-level retry on top would silently double it. Nothing after billing
is ever retried - see runner.run_chat.

NOTE: this records the budget, not the spend. The SDKs do not report how many
attempts a call actually took, so the audit log stores the policy that was in
effect, not the retry count.
"""

HTTP_TIMEOUT = httpx.Timeout(READ_TIMEOUT_SEC, connect=CONNECT_TIMEOUT_SEC)
"""
Timeout object for SDKs that accept an httpx timeout (OpenAI, Anthropic).

Only the connect phase is split out; read, write and pool all take the read budget.
Write and pool never bind here - the requests are small and the pool is capped well
under httpx's connection limit - so giving them their own knobs would be noise.
"""

TOTAL_TIMEOUT_MS = int(READ_TIMEOUT_SEC * 1000)
"""
Single-number timeout, in milliseconds, for SDKs that take no connect/read split.

google-genai's HttpOptions only accepts one value, so it gets the read budget -
the safe direction, since it errs toward waiting rather than discarding a billed
response.
"""
